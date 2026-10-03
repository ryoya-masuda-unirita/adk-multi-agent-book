# samples/chapter08/monitoring/dashboard_setup.py
"""CloudWatch ダッシュボードの作成（8-6-7 完全版）

Python SDK（boto3のCloudWatchクライアント）でダッシュボードをプログラム的に作成する例。
宣言的に定義する場合の同等構成は同ディレクトリの dashboard.json を参照
（aws cloudwatch put-dashboard --dashboard-name agent-operations
  --dashboard-body file://dashboard.json で適用できる）。
紙面で省略したエラー率ウィジェットの定義を含む完全版。
"""
import json
import os
import sys

import boto3

try:
    from .agent_alerts import AGENTCORE_NAMESPACE, runtime_dimensions
except ImportError:
    from agent_alerts import AGENTCORE_NAMESPACE, runtime_dimensions


def _metric(runtime_arn: str, metric_name: str, **options) -> list:
    """ダッシュボードのウィジェットに渡すメトリクス定義を組み立てる

    CloudWatchのダッシュボードは、メトリクスを
    [名前空間, メトリクス名, ディメンション名, 値, ..., オプション] の配列で表す。
    """
    dimensions: list = []
    for dimension in runtime_dimensions(runtime_arn):
        dimensions += [dimension["Name"], dimension["Value"]]
    return [AGENTCORE_NAMESPACE, metric_name, *dimensions, options]


def create_agent_dashboard(runtime_arn: str, dashboard_name: str = "agent-operations"):
    """エージェント運用ダッシュボードを作成する"""
    client = boto3.client("cloudwatch")
    region = client.meta.region_name

    dashboard_body = {
        "widgets": [
            # リクエスト数ウィジェット
            {
                "type": "metric",
                "x": 0, "y": 0, "width": 12, "height": 6,
                "properties": {
                    "title": "Requests per Minute",
                    "region": region,
                    "view": "timeSeries",
                    "stat": "Sum",
                    "period": 60,
                    "metrics": [_metric(runtime_arn, "Invocations")],
                },
            },
            # エラー率ウィジェット
            {
                "type": "metric",
                "x": 12, "y": 0, "width": 12, "height": 6,
                "properties": {
                    "title": "Error Rate",
                    "region": region,
                    "view": "timeSeries",
                    "stat": "Sum",
                    "period": 300,
                    "metrics": [
                        _metric(runtime_arn, "Invocations", id="invocations", visible=False),
                        _metric(runtime_arn, "UserErrors", id="user_errors", visible=False),
                        _metric(runtime_arn, "SystemErrors", id="system_errors", visible=False),
                        [{
                            "expression": "(user_errors + system_errors) / invocations",
                            "label": "Error Rate",
                            "id": "error_rate",
                        }],
                    ],
                },
            },
        ],
    }

    result = client.put_dashboard(
        DashboardName=dashboard_name,
        DashboardBody=json.dumps(dashboard_body),
    )
    # 定義に問題がある場合は、検証メッセージが返る
    for message in result.get("DashboardValidationMessages", []):
        print(f"Validation: {message['Message']}")
    print(f"Dashboard created: {dashboard_name}")


if __name__ == "__main__":
    # 実行例（紙面では省略。ランタイムのARNは環境変数から取得する）
    runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
    if not runtime_arn:
        print("環境変数 AGENT_RUNTIME_ARN を設定してください。")
        sys.exit(2)

    create_agent_dashboard(runtime_arn)
