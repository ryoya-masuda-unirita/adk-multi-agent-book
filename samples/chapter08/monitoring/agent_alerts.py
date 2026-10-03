# samples/chapter08/monitoring/agent_alerts.py
"""エージェント層アラートの作成（8-6-5節の完全版）

Python SDK（boto3のCloudWatchクライアント）で、メトリクスを閾値・持続時間付きで
監視するアラームを作成する。
本文表8-12のエージェント層アラート（エラー率5%超、ツール呼び出し失敗率10%超）を
プログラム的に登録する。AWS CLIで同等の設定を行う場合は、同ディレクトリの
setup_alerts.sh を参照。

エラー率は、AgentCore Runtimeが自動で出力するメトリクス（呼び出し回数とエラー数）から
計算する。ツール呼び出し失敗率は、アプリケーションが出力するカスタムメトリクスを監視する。

使い方:
  export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:ap-northeast-1:123456789012:runtime/my_agent-abc123
  export NOTIFICATION_TOPIC_ARN=arn:aws:sns:ap-northeast-1:123456789012:agent-alerts
  python agent_alerts.py
"""
import os
import sys

import boto3

# AgentCore Runtimeが自動で出力するメトリクスの名前空間
AGENTCORE_NAMESPACE = "AWS/Bedrock-AgentCore"
# アプリケーションが出力するカスタムメトリクスの名前空間
CUSTOM_NAMESPACE = "Custom/Agent"


def runtime_dimensions(runtime_arn: str) -> list[dict]:
    """ランタイムのメトリクスを特定するディメンションを組み立てる"""
    # ランタイムIDは「ランタイム名-ランダムな文字列」の形式
    runtime_name = runtime_arn.rsplit("/", 1)[-1].rsplit("-", 1)[0]
    return [
        {"Name": "Resource", "Value": runtime_arn},
        {"Name": "Operation", "Value": "InvokeAgentRuntime"},
        # DEFAULTは、最新バージョンを指す既定のエンドポイント
        {"Name": "Name", "Value": f"{runtime_name}::DEFAULT"},
    ]


def _runtime_metric(
    metric_id: str,
    metric_name: str,
    runtime_arn: str,
    period_seconds: int,
) -> dict:
    """エラー率の計算に使う、ランタイムのメトリクス（合計値）の定義を組み立てる"""
    return {
        "Id": metric_id,
        "MetricStat": {
            "Metric": {
                "Namespace": AGENTCORE_NAMESPACE,
                "MetricName": metric_name,
                "Dimensions": runtime_dimensions(runtime_arn),
            },
            "Period": period_seconds,
            "Stat": "Sum",
        },
        "ReturnData": False,
    }


def create_agent_layer_alerts(
    runtime_arn: str,
    notification_topic_arn: str,
    duration_seconds: int = 300,
) -> list[str]:
    """エージェント層のアラームを作成し、作成したアラーム名を返す"""
    client = boto3.client("cloudwatch")

    # 表8-12のエージェント層アラートに対応する2つのアラームを定義する
    alarms = [
        {
            "AlarmName": "AgentCore Runtime - Error Rate > 5%",
            "AlarmDescription": (
                "エージェントのエラー率が5%を超えました。ログを確認してください。"
            ),
            # エラー率 =（利用者起因のエラー + システム起因のエラー）÷ 呼び出し回数
            "Metrics": [
                _runtime_metric(
                    "invocations", "Invocations", runtime_arn, duration_seconds
                ),
                _runtime_metric(
                    "user_errors", "UserErrors", runtime_arn, duration_seconds
                ),
                _runtime_metric(
                    "system_errors", "SystemErrors", runtime_arn, duration_seconds
                ),
                {
                    "Id": "error_rate",
                    "Expression": "(user_errors + system_errors) / invocations",
                    "Label": "Error Rate",
                    "ReturnData": True,
                },
            ],
            "Threshold": 0.05,
        },
        {
            "AlarmName": "AgentCore Runtime - Tool Failure Rate > 10%",
            "AlarmDescription": (
                "ツール呼び出しの失敗率が10%を超えました。"
                "外部API断を確認してください。"
            ),
            "Namespace": CUSTOM_NAMESPACE,
            "MetricName": "ToolFailureRate",
            "Statistic": "Average",
            # 持続時間: 一時的なスパイクをノイズとして除外する
            "Period": duration_seconds,
            "Threshold": 0.10,
        },
    ]

    created_names: list[str] = []
    for alarm in alarms:
        client.put_metric_alarm(
            ComparisonOperator="GreaterThanThreshold",
            EvaluationPeriods=1,
            # 呼び出しが無い時間帯（データなし）はアラーム状態にしない
            TreatMissingData="notBreaching",
            AlarmActions=[notification_topic_arn],
            **alarm,
        )
        print(f"Alarm created: {alarm['AlarmName']}")
        created_names.append(alarm["AlarmName"])

    return created_names


if __name__ == "__main__":
    runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
    topic_arn = os.environ.get("NOTIFICATION_TOPIC_ARN")
    if not runtime_arn or not topic_arn:
        print(
            "環境変数 AGENT_RUNTIME_ARN と NOTIFICATION_TOPIC_ARN を"
            "設定してください。"
        )
        sys.exit(2)

    create_agent_layer_alerts(runtime_arn, topic_arn)
