#!/bin/bash
# samples/chapter08/monitoring/setup_alerts.sh
# CloudWatchのアラート設定スクリプト
#
# 使い方:
#   export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:ap-northeast-1:123456789012:runtime/my_agent-abc123
#   export NOTIFICATION_TOPIC_ARN=arn:aws:sns:ap-northeast-1:123456789012:agent-alerts
#   bash setup_alerts.sh

set -euo pipefail

: "${AGENT_RUNTIME_ARN:?環境変数 AGENT_RUNTIME_ARN を設定してください}"
: "${NOTIFICATION_TOPIC_ARN:?環境変数 NOTIFICATION_TOPIC_ARN を設定してください}"
AWS_REGION="${AWS_REGION:-$(aws configure get region)}"

# ランタイムIDは「ランタイム名-ランダムな文字列」の形式
RUNTIME_ID="${AGENT_RUNTIME_ARN##*/}"
RUNTIME_NAME="${RUNTIME_ID%-*}"
# アプリケーションのログが入るロググループ（DEFAULTは既定のエンドポイント）
LOG_GROUP="/aws/bedrock-agentcore/runtimes/${RUNTIME_ID}-DEFAULT"

# ランタイムのメトリクスを特定するディメンション
DIMENSIONS="Name=Resource,Value=${AGENT_RUNTIME_ARN} Name=Operation,Value=InvokeAgentRuntime Name=Name,Value=${RUNTIME_NAME}::DEFAULT"
DIMENSIONS_JSON="[{\"Name\":\"Resource\",\"Value\":\"${AGENT_RUNTIME_ARN}\"},{\"Name\":\"Operation\",\"Value\":\"InvokeAgentRuntime\"},{\"Name\":\"Name\",\"Value\":\"${RUNTIME_NAME}::DEFAULT\"}]"

echo "=== CloudWatch アラート設定 ==="
echo "  Runtime: ${RUNTIME_ID}"
echo ""

# --- 1. レイテンシアラート ---
echo "1. レイテンシアラートを作成中..."
# shellcheck disable=SC2086
aws cloudwatch put-metric-alarm \
  --alarm-name "AgentCore Runtime - P99 Latency > 30s" \
  --alarm-description "AgentCore RuntimeのP99レイテンシが30秒を超えました。トレースを確認してください。" \
  --namespace "AWS/Bedrock-AgentCore" \
  --metric-name "Latency" \
  --dimensions ${DIMENSIONS} \
  --extended-statistic p99 \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 30000 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "${NOTIFICATION_TOPIC_ARN}"

# --- 2. エラーレートアラート ---
echo "2. エラーレートアラートを作成中..."
# エラー率 =（利用者起因のエラー + システム起因のエラー）÷ 呼び出し回数
metric() {
  echo "{\"Id\":\"$1\",\"ReturnData\":false,\"MetricStat\":{\"Metric\":{\"Namespace\":\"AWS/Bedrock-AgentCore\",\"MetricName\":\"$2\",\"Dimensions\":${DIMENSIONS_JSON}},\"Period\":300,\"Stat\":\"Sum\"}}"
}
aws cloudwatch put-metric-alarm \
  --alarm-name "AgentCore Runtime - Error Rate > 5%" \
  --alarm-description "エージェントのエラー率が5%を超えました。ログを確認してください。" \
  --metrics "[$(metric invocations Invocations),$(metric user_errors UserErrors),$(metric system_errors SystemErrors),{\"Id\":\"error_rate\",\"Expression\":\"(user_errors + system_errors) / invocations\",\"Label\":\"Error Rate\",\"ReturnData\":true}]" \
  --evaluation-periods 1 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "${NOTIFICATION_TOPIC_ARN}"

# --- 3. エスカレーション数アラート ---
echo "3. エスカレーション数のログベースメトリクスを作成中..."
# ログの event が escalation の行を数えて、カスタムメトリクスにする
aws logs put-metric-filter \
  --log-group-name "${LOG_GROUP}" \
  --filter-name "agent_escalation_count" \
  --filter-pattern '{ $.event = "escalation" }' \
  --metric-transformations "metricName=AgentEscalationCount,metricNamespace=Custom/Agent,metricValue=1,defaultValue=0"

echo ""
echo "=== アラート設定完了 ==="
echo "コンソールで確認: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#alarmsV2:"
