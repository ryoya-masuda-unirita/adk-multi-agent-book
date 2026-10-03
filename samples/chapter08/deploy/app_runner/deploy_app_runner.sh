#!/bin/bash
# samples/chapter08/deploy/app_runner/deploy_app_runner.sh
# AWS App Runnerへのデプロイスクリプト（8-2-5節の完全版）
#
# コンテナイメージをビルドしてAmazon ECRに置き、App Runnerのサービスを作成する。
# 実行には aws / docker の各コマンドと、次の2つのIAMロールが必要。
#   - アクセスロール: App RunnerがECRからイメージを取得するためのロール
#   - インスタンスロール: コンテナがAmazon Bedrockを呼び出すためのロール
#
# 使い方:
#   export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
#   export APP_RUNNER_ACCESS_ROLE_ARN=arn:aws:iam::123456789012:role/your-apprunner-ecr-access-role
#   export APP_RUNNER_INSTANCE_ROLE_ARN=arn:aws:iam::123456789012:role/your-apprunner-instance-role
#   bash deploy_app_runner.sh

set -euo pipefail

# --- 環境変数チェック ---
: "${DATABASE_URL:?環境変数 DATABASE_URL を設定してください}"
: "${APP_RUNNER_ACCESS_ROLE_ARN:?環境変数 APP_RUNNER_ACCESS_ROLE_ARN を設定してください}"
: "${APP_RUNNER_INSTANCE_ROLE_ARN:?環境変数 APP_RUNNER_INSTANCE_ROLE_ARN を設定してください}"
REGION="${AWS_REGION:-$(aws configure get region)}"
SERVICE_NAME="${SERVICE_NAME:-my-agent}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REGISTRY}/${SERVICE_NAME}:latest"

echo "=== App Runner デプロイ ==="
echo "  Region:  ${REGION}"
echo "  Service: ${SERVICE_NAME}"
echo ""

# --- コンテナイメージのビルドとECRへのプッシュ ---
echo "1. コンテナイメージをビルドしてECRにプッシュ中..."
aws ecr describe-repositories --repository-names "${SERVICE_NAME}" --region "${REGION}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${SERVICE_NAME}" --region "${REGION}" >/dev/null
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"
# App Runnerはx86_64（amd64）のイメージを実行する
docker build --platform linux/amd64 -t "${IMAGE}" "$(dirname "$0")"
docker push "${IMAGE}"

# --- App Runnerへのデプロイ ---
# 注: App Runnerのサービスは既定でインターネットに公開される。本番では認証を構成すること
echo "2. App Runnerにデプロイ中..."
# DB接続文字列などの設定は、JSONファイルにまとめて渡す
CONFIG_FILE="$(mktemp)"
trap 'rm -f "${CONFIG_FILE}"' EXIT
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
