#!/bin/bash
# samples/chapter08/deploy/app_runner/deploy_app_runner.sh
# AWS App Runnerへのデプロイスクリプト（8-2-5節の完全版）
#
# コンテナイメージをAWS CodeBuildでビルドしてAmazon ECRに置き、App Runnerのサービスを作成する。
# ビルドはAWSの中で行うため、手元のPCにDockerは要らない（手元から送るのはソースのzipだけ）。
# 実行には aws / python3 の各コマンドと、次のリソースが必要。
#   - ソースのzipを置くS3バケット
#   - CodeBuildのサービスロール: S3からソースを読み、ECRにイメージをプッシュし、ログを書くためのロール
#   - アクセスロール: App RunnerがECRからイメージを取得するためのロール
#   - インスタンスロール: コンテナがAmazon Bedrockを呼び出すためのロール
#
# 使い方:
#   export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
#   export CODE_BUCKET=your-code-bucket
#   export CODEBUILD_ROLE_ARN=arn:aws:iam::123456789012:role/your-codebuild-role
#   export APP_RUNNER_ACCESS_ROLE_ARN=arn:aws:iam::123456789012:role/your-apprunner-ecr-access-role
#   export APP_RUNNER_INSTANCE_ROLE_ARN=arn:aws:iam::123456789012:role/your-apprunner-instance-role
#   bash deploy_app_runner.sh

set -euo pipefail

# --- 環境変数チェック ---
: "${DATABASE_URL:?環境変数 DATABASE_URL を設定してください}"
: "${CODE_BUCKET:?環境変数 CODE_BUCKET を設定してください}"
: "${CODEBUILD_ROLE_ARN:?環境変数 CODEBUILD_ROLE_ARN を設定してください}"
: "${APP_RUNNER_ACCESS_ROLE_ARN:?環境変数 APP_RUNNER_ACCESS_ROLE_ARN を設定してください}"
: "${APP_RUNNER_INSTANCE_ROLE_ARN:?環境変数 APP_RUNNER_INSTANCE_ROLE_ARN を設定してください}"
REGION="${AWS_REGION:-$(aws configure get region)}"
SERVICE_NAME="${SERVICE_NAME:-my-agent}"

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REGISTRY}/${SERVICE_NAME}:latest"
BUILD_PROJECT="${SERVICE_NAME}-build"
SOURCE_KEY="${SERVICE_NAME}/source.zip"

echo "=== App Runner デプロイ ==="
echo "  Region:  ${REGION}"
echo "  Service: ${SERVICE_NAME}"
echo ""

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

# --- ソースのアップロード ---
echo "1. ソースをzipにまとめてS3にアップロード中..."
# Dockerfile・buildspec.yml・アプリのコードをまとめる（.envと__pycache__は含めない）
python3 - "${SOURCE_DIR}" "${WORK_DIR}/source.zip" <<'PYTHON'
import sys
import zipfile
from pathlib import Path

source_dir, zip_path = Path(sys.argv[1]), sys.argv[2]
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.name != ".env" and "__pycache__" not in path.parts:
            archive.write(path, path.relative_to(source_dir))
PYTHON
aws s3 cp "${WORK_DIR}/source.zip" "s3://${CODE_BUCKET}/${SOURCE_KEY}" --only-show-errors

# --- CodeBuildでコンテナイメージをビルドしてECRにプッシュ ---
echo "2. CodeBuildでコンテナイメージをビルド中..."
aws ecr describe-repositories --repository-names "${SERVICE_NAME}" --region "${REGION}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${SERVICE_NAME}" --region "${REGION}" >/dev/null

# ビルドプロジェクトが無ければ作成する。ビルド手順は同じディレクトリの buildspec.yml に書いてある
# privilegedMode=true は、ビルド用のマシンの中でDockerを使うために必要
if [ "$(aws codebuild batch-get-projects --names "${BUILD_PROJECT}" --region "${REGION}" --query 'length(projects)' --output text)" = "0" ]; then
  aws codebuild create-project \
    --region "${REGION}" \
    --name "${BUILD_PROJECT}" \
    --source "type=S3,location=${CODE_BUCKET}/${SOURCE_KEY}" \
    --artifacts "type=NO_ARTIFACTS" \
    --environment "type=LINUX_CONTAINER,image=aws/codebuild/amazonlinux-x86_64-standard:5.0,computeType=BUILD_GENERAL1_SMALL,privilegedMode=true,environmentVariables=[{name=REGISTRY,value=${REGISTRY}},{name=IMAGE,value=${IMAGE}}]" \
    --service-role "${CODEBUILD_ROLE_ARN}" >/dev/null
fi

BUILD_ID="$(aws codebuild start-build --region "${REGION}" --project-name "${BUILD_PROJECT}" --query 'build.id' --output text)"
# ビルドは非同期で進むため、完了まで状態を確認する
while true; do
  BUILD_STATUS="$(aws codebuild batch-get-builds --region "${REGION}" --ids "${BUILD_ID}" --query 'builds[0].buildStatus' --output text)"
  [ "${BUILD_STATUS}" != "IN_PROGRESS" ] && break
  sleep 10
done
if [ "${BUILD_STATUS}" != "SUCCEEDED" ]; then
  echo "ビルドに失敗しました: ${BUILD_STATUS}" >&2
  echo "ログを確認: aws logs tail /aws/codebuild/${BUILD_PROJECT} --since 30m" >&2
  exit 1
fi

# --- App Runnerへのデプロイ ---
# 注: App Runnerのサービスは既定でインターネットに公開される。本番では認証を構成すること
echo "3. App Runnerにデプロイ中..."
# DB接続文字列などの設定は、JSONファイルにまとめて渡す
CONFIG_FILE="${WORK_DIR}/source-configuration.json"
cat > "${CONFIG_FILE}" <<JSON
{
  "AuthenticationConfiguration": {"AccessRoleArn": "${APP_RUNNER_ACCESS_ROLE_ARN}"},
  "AutoDeploymentsEnabled": false,
  "ImageRepository": {
    "ImageIdentifier": "${IMAGE}",
    "ImageRepositoryType": "ECR",
    "ImageConfiguration": {
      "Port": "8080",
      "RuntimeEnvironmentVariables": {
        "AWS_REGION": "${REGION}",
        "DATABASE_URL": "${DATABASE_URL}"
      }
    }
  }
}
JSON

aws apprunner create-service \
  --region "${REGION}" \
  --service-name "${SERVICE_NAME}" \
  --source-configuration "file://${CONFIG_FILE}" \
  --instance-configuration "InstanceRoleArn=${APP_RUNNER_INSTANCE_ROLE_ARN}" \
  --health-check-configuration "Protocol=HTTP,Path=/health" \
  --query "Service.[ServiceArn,ServiceUrl]" \
  --output text

echo ""
echo "=== デプロイ完了 ==="
echo "コンソールで確認: https://${REGION}.console.aws.amazon.com/apprunner/home?region=${REGION}#/services"
