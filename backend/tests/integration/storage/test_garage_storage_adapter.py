import boto3
import pytest
from moto import mock_aws

from chatbot.adapters.storage.garage.garage_storage_adapter import GarageStorageAdapter

BUCKET = "test-chatbot"
REGION = "us-east-1"


@pytest.fixture
def adapter():
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        yield GarageStorageAdapter(
            endpoint_url=None,
            access_key_id="test",
            secret_access_key="test",
            bucket_name=BUCKET,
            region_name=REGION,
        )


@pytest.fixture
def s3(adapter):
    return boto3.client("s3", region_name=REGION)


class TestGarageStorageAdapter:
    async def test_upload_and_get_round_trip(self, adapter, s3):
        key = "conversations/c1/a1/notes.md"
        await adapter.upload_file(key, b"# Hello", "text/markdown")

        response = s3.get_object(Bucket=BUCKET, Key=key)
        assert response["ContentType"] == "text/markdown"
        assert await adapter.get_file(key) == b"# Hello"

    async def test_delete_prefix_removes_conversation_blobs(self, adapter, s3):
        prefix = "conversations/c1/"
        for name in ("a1/one.md", "a2/two.pdf"):
            s3.put_object(Bucket=BUCKET, Key=prefix + name, Body=b"data")
        # A sibling conversation's blobs must survive.
        s3.put_object(Bucket=BUCKET, Key="conversations/c2/keep.md", Body=b"keep")

        await adapter.delete_prefix(prefix)

        remaining = [obj["Key"] for obj in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])]
        assert remaining == ["conversations/c2/keep.md"]

    async def test_delete_prefix_no_matches_does_not_raise(self, adapter):
        await adapter.delete_prefix("conversations/missing/")
