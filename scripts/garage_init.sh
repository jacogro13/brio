#!/bin/sh
# Idempotent Garage initialisation for local dev: layout → key → bucket →
# permissions. Safe to run on every container start. Adapted from the Blibiobot
# app's scripts/garage_init.sh.
set -e

GARAGE_ADMIN="http://garage:3903"
GARAGE_ACCESS_KEY_ID="${GARAGE_ACCESS_KEY_ID:?GARAGE_ACCESS_KEY_ID is required}"
GARAGE_SECRET_ACCESS_KEY="${GARAGE_SECRET_ACCESS_KEY:?GARAGE_SECRET_ACCESS_KEY is required}"
GARAGE_ADMIN_TOKEN="${GARAGE_ADMIN_TOKEN:?GARAGE_ADMIN_TOKEN is required}"
GARAGE_BUCKET="${GARAGE_BUCKET:-chatbot}"

# Wrapper so every curl call carries the auth header
gcurl() {
  curl -H "Authorization: Bearer ${GARAGE_ADMIN_TOKEN}" "$@"
}

# ── 1. Wait for Garage admin API ──────────────────────────────────────────────
echo "[garage-init] Waiting for Garage admin API..."
n=0
until gcurl -sf "${GARAGE_ADMIN}/health" > /dev/null 2>&1; do
  n=$((n+1))
  if [ "$n" -ge 30 ]; then
    echo "[garage-init] ERROR: Garage did not become ready in time"
    exit 1
  fi
  sleep 2
done
echo "[garage-init] Garage is up."

# ── 2. Get node ID ────────────────────────────────────────────────────────────
STATUS_JSON=$(gcurl -sf "${GARAGE_ADMIN}/v1/status")
NODE_ID=$(echo "$STATUS_JSON" | jq -r '.node')
echo "[garage-init] Node ID: ${NODE_ID}"

# ── 3. Assign layout (skip if already applied) ───────────────────────────────
LAYOUT_JSON=$(gcurl -sf "${GARAGE_ADMIN}/v1/layout")
LAYOUT_VERSION=$(echo "$LAYOUT_JSON" | jq -r '.version')
HAS_ROLE=$(echo "$LAYOUT_JSON" | jq -r --arg id "$NODE_ID" '[.roles[] | select(.id == $id)] | length > 0')

if [ "$HAS_ROLE" = "true" ]; then
  echo "[garage-init] Layout already configured (version ${LAYOUT_VERSION}), skipping."
else
  echo "[garage-init] Assigning node to dc1..."
  gcurl -sf -X POST "${GARAGE_ADMIN}/v1/layout" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg id "$NODE_ID" '[{id:$id,zone:"dc1",capacity:1073741824,tags:[]}]')" > /dev/null
  NEXT_VERSION=$((LAYOUT_VERSION + 1))
  gcurl -sf -X POST "${GARAGE_ADMIN}/v1/layout/apply" \
    -H "Content-Type: application/json" \
    -d "{\"version\":${NEXT_VERSION}}" > /dev/null
  echo "[garage-init] Layout applied."
  sleep 2
fi

# ── 4. Import key (idempotent) ────────────────────────────────────────────────
echo "[garage-init] Importing access key..."
gcurl -s -o /tmp/key_resp.json -w "%{http_code}" -X POST "${GARAGE_ADMIN}/v1/key/import" \
  -H "Content-Type: application/json" \
  -d "{\"accessKeyId\":\"${GARAGE_ACCESS_KEY_ID}\",\"secretAccessKey\":\"${GARAGE_SECRET_ACCESS_KEY}\",\"name\":\"chatbot\"}" > /dev/null

# ── 5. Create bucket (idempotent: 409 = already exists) ──────────────────────
echo "[garage-init] Creating bucket '${GARAGE_BUCKET}'..."
gcurl -s -o /tmp/bucket_resp.json -w "%{http_code}" -X POST "${GARAGE_ADMIN}/v1/bucket" \
  -H "Content-Type: application/json" \
  -d "{\"globalAlias\":\"${GARAGE_BUCKET}\"}" > /dev/null

BUCKET_ID=$(gcurl -sf "${GARAGE_ADMIN}/v1/bucket?globalAlias=${GARAGE_BUCKET}" | jq -r '.id')
echo "[garage-init] Bucket ID: ${BUCKET_ID}"

# ── 6. Grant key read+write on bucket ────────────────────────────────────────
echo "[garage-init] Granting bucket permissions..."
gcurl -s -o /dev/null -X POST "${GARAGE_ADMIN}/v1/bucket/allow" \
  -H "Content-Type: application/json" \
  -d "{\"bucketId\":\"${BUCKET_ID}\",\"accessKeyId\":\"${GARAGE_ACCESS_KEY_ID}\",\"permissions\":{\"read\":true,\"write\":true,\"owner\":false}}"

echo "[garage-init] Done."
