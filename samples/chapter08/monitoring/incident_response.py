# samples/chapter08/monitoring/incident_response.py
"""インシデント調査スクリプト（8-6-6節の完全版）

エージェントのエラー率が急上昇したインシデントの初動調査を行う。
1. CloudWatch Logsからエラーログを収集し、error_type別に件数を集計する
2. AWS X-Rayから異常に遅いトレース（30秒超）を抽出する

使い方:
  export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:ap-northeast-1:123456789012:runtime/my_agent-abc123
  python incident_response.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import boto3

# エラーとして扱うログの重要度。アプリケーションの構造化ログ（severity）と
# AgentCore Runtimeが出力するログ（level）の両方を対象にする
ERROR_LEVELS = {"ERROR", "CRITICAL"}


def investigate_error_spike(
    runtime_arn: str,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """エラースパイクの調査"""
    # 1. エラーログの収集
    logs_client = boto3.client("logs")
    runtime_id = runtime_arn.rsplit("/", 1)[-1]
    # アプリケーションのログが入るロググループ（DEFAULTは既定のエンドポイント）
    log_group = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"

    print("=== エラーログの分析 ===")
    response = logs_client.filter_log_events(
        logGroupName=log_group,
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000),
        # JSON形式のログのうち、重要度がERRORのものに絞り込む
        filterPattern='{ ($.severity = "ERROR") || ($.level = "ERROR") }',
        limit=100,
    )

    # error_type別に件数を集計する
    error_counts: dict[str, int] = {}
    for event in response["events"]:
        try:
            payload = json.loads(event["message"])
        except json.JSONDecodeError:
            payload = {}
        error_type = payload.get("error_type", "unknown")
        error_counts[error_type] = error_counts.get(error_type, 0) + 1

    # 件数の多い順に表示する
    for error_type, count in sorted(
        error_counts.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {error_type}: {count}件")

    # 2. トレースの確認
    print("\n=== 失敗トレースの分析 ===")
    xray_client = boto3.client("xray")
    # 所要時間が30秒を超えるトレースを抽出する
    # （X-Rayにトレースを記録するには、CloudWatchのTransaction Searchを有効にしておく）
    summaries = xray_client.get_trace_summaries(
        StartTime=start_time,
        EndTime=end_time,
        FilterExpression="duration > 30",
    )["TraceSummaries"]

    slow_traces: list[dict] = []
    for summary in summaries:
        # 異常に遅いトレースを収集
        slow_traces.append(
            {
                "trace_id": summary["Id"],
                "entry_point": summary.get("EntryPoint", {}).get("Name", "unknown"),
                "duration": summary["Duration"],
            }
        )

    # 上位10件を表示する
    for st in slow_traces[:10]:
        print(
            f"  Trace: {st['trace_id']}, "
            f"EntryPoint: {st['entry_point']}, "
            f"Duration: {st['duration']:.1f}s"
        )


if __name__ == "__main__":
    runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
    if not runtime_arn:
        print("環境変数 AGENT_RUNTIME_ARN を設定してください。")
        sys.exit(2)

    # 調査の実行（直近1時間を対象とする）
    investigate_error_spike(
        runtime_arn=runtime_arn,
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        end_time=datetime.now(timezone.utc),
    )
