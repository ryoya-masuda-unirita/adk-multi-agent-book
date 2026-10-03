# 5-5-7. 発展: 承認ダッシュボードの設計
# 実行には boto3 パッケージと、DynamoDBのテーブル（パーティションキー: request_id）が必要
"""承認ダッシュボードのデータ取得"""
from datetime import datetime, timedelta

import boto3
from boto3.dynamodb.conditions import Attr


class ApprovalDashboard:
    """承認ダッシュボードのデータを提供するクラス"""

    def __init__(
        self,
        table_name: str = "approval_requests",
        region_name: str | None = None,
    ):
        dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table = dynamodb.Table(table_name)

    def _scan_recent(self, since: datetime) -> list[dict]:
        """指定時刻以降に作成されたリクエストを取得する"""
        # created_atはISO 8601形式の文字列のため、文字列の大小で時刻を比較できる
        scan_kwargs = {
            "FilterExpression": Attr("created_at").gte(since.isoformat()),
        }
        items = []
        while True:
            response = self.table.scan(**scan_kwargs)
            items.extend(response["Items"])
            # 1回のscanで返るのは最大1MBのため、続きがあれば取得を繰り返す
            if "LastEvaluatedKey" not in response:
                return items
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    def get_summary(self) -> dict:
        """ダッシュボードサマリーを取得する"""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)

        # 過去24時間のリクエスト
        recent_items = self._scan_recent(last_24h)

        summary = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "expired": 0,
            "avg_response_time_minutes": 0,
            "by_tool": {},
        }

        response_times = []

        for data in recent_items:
            status = data["status"]
            summary[status] = summary.get(status, 0) + 1

            # ツール別の集計
            tool_name = data["tool_name"]
            if tool_name not in summary["by_tool"]:
                summary["by_tool"][tool_name] = {
                    "pending": 0,
                    "approved": 0,
                    "rejected": 0,
                }
            summary["by_tool"][tool_name][status] += 1

            # 応答時間の計算
            if data["decisions"]:
                first_decision = data["decisions"][0]
                response_time = (
                    datetime.fromisoformat(first_decision["timestamp"])
                    - datetime.fromisoformat(data["created_at"])
                ).total_seconds() / 60
                response_times.append(response_time)

        if response_times:
            summary["avg_response_time_minutes"] = (
                sum(response_times) / len(response_times)
            )

        return summary
