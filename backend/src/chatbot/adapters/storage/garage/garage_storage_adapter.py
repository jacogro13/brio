import logging
from functools import partial

import boto3
from anyio import to_thread

from chatbot.domain.conversation.ports.attachment_storage import AbstractAttachmentStorage

logger = logging.getLogger(__name__)


class GarageStorageAdapter(AbstractAttachmentStorage):
    """S3 client wired to Garage (S3-compatible). All boto3 calls are pushed onto
    the anyio thread pool so they don't block the event loop. Shape copied from
    the Blibiobot app's ``GarageStorageAdapter``."""

    def __init__(
        self,
        endpoint_url: str | None,  # None = AWS default (tests with moto)
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region_name: str,
    ) -> None:
        self._bucket = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )
        logger.debug(
            "GarageStorageAdapter initialised endpoint=%s bucket=%s",
            endpoint_url,
            bucket_name,
        )

    async def upload_file(self, key: str, data: bytes, content_type: str) -> None:
        logger.debug("S3 put_object key=%r size=%d B", key, len(data))
        fn = partial(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        await to_thread.run_sync(fn)

    async def get_file(self, key: str) -> bytes:
        logger.debug("S3 get_object key=%r", key)
        fn = partial(self._client.get_object, Bucket=self._bucket, Key=key)
        response = await to_thread.run_sync(fn)
        return response["Body"].read()

    async def delete_prefix(self, prefix: str) -> None:
        logger.debug("S3 delete prefix=%r", prefix)
        deleted = await to_thread.run_sync(self._delete_prefix_sync, prefix)
        logger.debug("S3 delete prefix complete prefix=%r deleted=%d", prefix, deleted)

    def _delete_prefix_sync(self, prefix: str) -> int:
        """List and batch-delete every object under ``prefix`` (runs in a thread).

        Paginates ``list_objects_v2`` (max 1000 keys/page) and issues one
        ``delete_objects`` per page, so it stays within S3's 1000-key batch
        limit. Returns the number of objects deleted.
        """
        paginator = self._client.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if not objects:
                continue
            self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": objects})
            deleted += len(objects)
        return deleted
