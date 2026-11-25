#!/bin/bash
set -e

REMOTE_USER="${1:?Usage: ./deploy.sh <user> <host> <path>}"
REMOTE_HOST="${2:?Usage: ./deploy.sh <user> <host> <path>}"
REMOTE_PATH="${3:?Usage: ./deploy.sh <user> <host> <path>}"

echo "Copying deployment files to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}..."

ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_PATH}"

scp docker-compose.yml "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/docker-compose.yml"
scp .env.example "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/.env.example"

ssh "${REMOTE_USER}@${REMOTE_HOST}" "
  if [ ! -f '${REMOTE_PATH}/.env' ]; then
    echo '.env not found on remote, copying .env.example as a starting point...'
    cp ${REMOTE_PATH}/.env.example ${REMOTE_PATH}/.env
    echo 'Fill in DB credentials and LLM_MODEL in ${REMOTE_PATH}/.env before starting the stack.'
  else
    echo '.env already exists on remote, skipping.'
  fi
"

echo "Done. To apply changes on the remote, run:"
echo "  ssh ${REMOTE_USER}@${REMOTE_HOST}"
echo "  cd ${REMOTE_PATH} && docker compose pull && docker compose up -d"
