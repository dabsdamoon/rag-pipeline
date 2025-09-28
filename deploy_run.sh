#!/usr/bin/env bash
set -euo pipefail

# Build and deploy the Houmy Cloud Run service.

# Load deployment configuration overrides if present
if [[ -f "deploy.env" ]]; then
  # shellcheck disable=SC1091
  source deploy.env
fi

PROJECT="${PROJECT_ID:-relays-cloud}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-houmy-api}"
REPOSITORY_PATH="${ARTIFACT_REPOSITORY:-us-central1-docker.pkg.dev/${PROJECT}/houmy-repo}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_URI="${IMAGE_URI:-${REPOSITORY_PATH}/${SERVICE_NAME}:${IMAGE_TAG}}"
SOURCE_DIR="${SOURCE_DIR:-.}"
ENV_FILE="${ENV_FILE:-cloudrun.env}"
SKIP_BUILD="${SKIP_BUILD:-0}"

CONCURRENCY="${CLOUD_RUN_CONCURRENCY:-10}"
TIMEOUT="${CLOUD_RUN_TIMEOUT:-300}"
MEMORY="${CLOUD_RUN_MEMORY:-512Mi}"
CPU="${CLOUD_RUN_CPU:-1}"
SERVICE_ACCOUNT="${CLOUD_RUN_SERVICE_ACCOUNT:-932784017415-compute@developer.gserviceaccount.com}"

DEPLOY_ARGS=(
  "--project=${PROJECT}"
  "--region=${REGION}"
  "--platform=managed"
  "--image=${IMAGE_URI}"
  "--concurrency=${CONCURRENCY}"
  "--timeout=${TIMEOUT}"
  "--memory=${MEMORY}"
  "--cpu=${CPU}"
  "--service-account=${SERVICE_ACCOUNT}"
  "--allow-unauthenticated"
  "--quiet"
)

if [[ -f "${ENV_FILE}" ]]; then
  DEPLOY_ARGS+=("--env-vars-file=${ENV_FILE}")
fi

if [[ -n "${EXTRA_DEPLOY_ARGS:-}" ]]; then
  # Allow callers to pass additional flags, e.g. --min-instances=1
  # shellcheck disable=SC2206
  DEPLOY_ARGS+=(${EXTRA_DEPLOY_ARGS})
fi

echo "Using source directory: ${SOURCE_DIR}"
echo "Using project: ${PROJECT}"
echo "Using region: ${REGION}"
echo "Service name: ${SERVICE_NAME}"
echo "Artifact URI: ${IMAGE_URI}"
echo "Service account: ${SERVICE_ACCOUNT}"
echo "Active gcloud account: $(gcloud config get-value account 2>/dev/null)"

if [[ "${SKIP_BUILD}" != "1" ]]; then
  echo "Building container image via Cloud Build..."
  gcloud builds submit "${SOURCE_DIR}" \
    --project="${PROJECT}" \
    --tag="${IMAGE_URI}"
else
  echo "Skipping build step (SKIP_BUILD=${SKIP_BUILD})."
fi

echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" "${DEPLOY_ARGS[@]}"

echo "Deployment complete."
