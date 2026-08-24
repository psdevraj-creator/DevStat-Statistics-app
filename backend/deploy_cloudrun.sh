#!/usr/bin/env bash
# Deploy DevStat to Cloud Run (project devstat-499409), replacing the service.
# Builds via Cloud Build (no local Docker needed), pushes to Artifact Registry,
# then `gcloud run deploy` with env vars sourced from backend/.env (not shown).
set -euo pipefail

PROJECT="devstat-499409"
REGION="europe-west1"
SERVICE="devstat-statistics-app"
IMAGE="gcr.io/${PROJECT}/devstat:latest"
BACKEND="$(cd "$(dirname "$0")/.." && pwd)/backend"

cd "$BACKEND"

echo "==> Building image with Cloud Build..."
gcloud builds submit --project "${PROJECT}" --tag "${IMAGE}" --quiet

# Compose env vars from backend/.env (values never printed).
ENV_FILE="$BACKEND/.env"
ENV_VARS=""
while IFS= read -r line; do
  s="$(echo "$line" | tr -d '\r')"
  case "$s" in
    ""|"#"*) continue ;;
  esac
  key="${s%%=*}"
  val="${s#*=}"
  [ -z "$key" ] && continue
  [ -z "$ENV_VARS" ] && ENV_VARS="${key}=${val}" || ENV_VARS="${ENV_VARS},${key}=${val}"
done < "$ENV_FILE"

echo "==> Deploying ${SERVICE} to ${REGION}..."
gcloud run deploy "${SERVICE}" \
  --project "${PROJECT}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars "${ENV_VARS}"

echo "==> Done. URL:"
gcloud run services describe "${SERVICE}" --project "${PROJECT}" --region "${REGION}" --format="value(status.url)"
