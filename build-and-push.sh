#!/bin/bash
set -e

PROJECT_ID="gen-lang-client-0044574038"
REGION="us-east1"
REPO="pdf-agent-repo"
IMAGE="pdf-agent"
TAG="${1:-latest}"

FULL_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:${TAG}"

echo "=== Building image: ${FULL_IMAGE} ==="

# 確保 Artifact Registry repo 存在
gcloud artifacts repositories describe "${REPO}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" 2>/dev/null || \
gcloud artifacts repositories create "${REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --description="PDF Agent Docker images"

# Cloud Build 雲端建置 (amd64，不需本地 Docker)
gcloud builds submit --tag "${FULL_IMAGE}" --project="${PROJECT_ID}" --region="${REGION}" .

echo "=== Done! Image pushed to ${FULL_IMAGE} ==="

echo "=== Cleaning up old images (keeping latest 3) ==="
IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}"

# List all digests sorted by creation time (newest first), skip top 3, and delete the rest
# List all digests sorted by creation time (newest first)
echo "Fetching image list..."
DIGESTS=$(gcloud artifacts docker images list "${IMAGE_PATH}" \
  --sort-by=~create_time \
  --format="value(digest)")

COUNT=0
for digest in $DIGESTS; do
  COUNT=$((COUNT + 1))
  if [ "$COUNT" -gt 3 ]; then
    echo "Deleting old image digest (${COUNT}): ${digest}"
    gcloud artifacts docker images delete "${IMAGE_PATH}@${digest}" --delete-tags --quiet
  else
    echo "Keeping image digest (${COUNT}): ${digest}"
  fi
done

echo "=== Cleanup complete ==="

echo "=== Restarting PDF Agent Pods ==="
kubectl rollout restart deployment/pdf-agent
echo "=== Rollout initiated ==="
