#!/bin/bash
# samples/chapter08/deploy/deploy.sh
# AgentCore Runtimeへのデプロイスクリプト
#
# エージェントのコードと依存パッケージをzipにまとめ、S3に置いてからランタイムを作成する。
# 実行には aws / uv / python3 の各コマンドが必要。
#
# 使い方:
#   export AGENTCORE_ROLE_ARN=arn:aws:iam::123456789012:role/your-agentcore-role
#   export CODE_BUCKET=your-code-bucket
#   bash deploy.sh

set -euo pipefail

# --- 環境変数チェック ---
: "${AGENTCORE_ROLE_ARN:?環境変数 AGENTCORE_ROLE_ARN を設定してください}"
: "${CODE_BUCKET:?環境変数 CODE_BUCKET を設定してください}"
AWS_REGION="${AWS_REGION:-$(aws configure get region)}"

CHAPTER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="${CHAPTER_DIR}/support_agent"
# ランタイム名は英字で始まる英数字とアンダースコア（ハイフンは使えない）
DISPLAY_NAME="${DISPLAY_NAME:-customer_support_agent}"

echo "=== AgentCore Runtime デプロイ ==="
echo "  Region:   ${AWS_REGION}"
echo "  Agent:    ${AGENT_DIR}"
echo "  Name:     ${DISPLAY_NAME}"
echo ""

# --- パッケージの作成 ---
echo "1. デプロイ用のzipを作成中..."
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

# 依存パッケージをLinux ARM64向けに取得する（AgentCore Runtimeの実行環境に合わせる）
uv pip install --quiet \
  --python-platform aarch64-manylinux_2_28 \
  --python-version 3.12 \
  --only-binary=:all: \
  --target "${WORK_DIR}/package" \
  -r "${CHAPTER_DIR}/deploy/agentcore/requirements.txt"

# エージェントのコードを配置する（.envは含めない）
cp "${CHAPTER_DIR}/deploy/agentcore/main.py" "${WORK_DIR}/package/main.py"
cp -r "${AGENT_DIR}" "${WORK_DIR}/package/support_agent"
rm -f "${WORK_DIR}/package/support_agent/.env"

python3 -c "import shutil; shutil.make_archive('${WORK_DIR}/agent', 'zip', '${WORK_DIR}/package')"

echo "2. zipをS3にアップロード中..."
aws s3 cp "${WORK_DIR}/agent.zip" "s3://${CODE_BUCKET}/${DISPLAY_NAME}/agent.zip" --only-show-errors

# --- デプロイ実行 ---
echo "3. AgentCore Runtimeにデプロイ中..."
aws bedrock-agentcore-control create-agent-runtime \
  --region "${AWS_REGION}" \
  --agent-runtime-name "${DISPLAY_NAME}" \
  --agent-runtime-artifact "codeConfiguration={code={s3={bucket=${CODE_BUCKET},prefix=${DISPLAY_NAME}/agent.zip}},runtime=PYTHON_3_12,entryPoint=[main.py]}" \
  --role-arn "${AGENTCORE_ROLE_ARN}" \
  --network-configuration "networkMode=PUBLIC" \
  --protocol-configuration "serverProtocol=HTTP" \
  --query "agentRuntimeArn" \
  --output text

echo ""
echo "=== デプロイ完了 ==="
echo "コンソールで確認: https://${AWS_REGION}.console.aws.amazon.com/bedrock-agentcore/agents?region=${AWS_REGION}"
