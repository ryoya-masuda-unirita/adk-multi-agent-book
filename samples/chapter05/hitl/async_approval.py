# 5-5-4. 非同期承認フロー
# 実行には boto3 パッケージと、DynamoDBのテーブル（パーティションキー: request_id）が必要
"""非同期承認フローの実装"""
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import boto3


class AsyncApprovalManager:
    """DynamoDBを使用した非同期承認フロー"""

    def __init__(
        self,
        table_name: str = "approval_requests",
        region_name: str | None = None,
    ):
        dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table = dynamodb.Table(table_name)

    def create_request(
        self,
        tool_name: str,
        tool_input: dict,
        requested_by: str,
        approvers: list[str],
    ) -> str:
        """承認リクエストを作成する"""
        request_id = str(uuid.uuid4())

        # DynamoDBは日時型を持たないため、ISO 8601形式の文字列で保存する
        self.table.put_item(Item={
            "request_id": request_id,
            "tool_name": tool_name,
            # DynamoDBはfloatを保存できないため、小数をDecimalに変換する
            "tool_input": json.loads(json.dumps(tool_input), parse_float=Decimal),
            "requested_by": requested_by,
            "approvers": approvers,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "decisions": [],
        })

        # 承認者に通知（実装は通知システムに依存）
        self._notify_approvers(request_id, approvers, tool_name, tool_input)

        return request_id

    def approve(
        self,
        request_id: str,
        approver_id: str,
        comment: str = "",
    ) -> bool:
        """承認リクエストを承認する"""
        data = self.table.get_item(Key={"request_id": request_id}).get("Item")

        if data is None:
            return False

        if data["status"] != "pending":
            return False

        if approver_id not in data["approvers"]:
            return False

        data["decisions"].append({
            "approver_id": approver_id,
            "decision": "approved",
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        })

        self._update_decision(request_id, "approved", data["decisions"])
        return True

    def reject(
        self,
        request_id: str,
        approver_id: str,
        reason: str,
    ) -> bool:
        """承認リクエストを拒否する"""
        data = self.table.get_item(Key={"request_id": request_id}).get("Item")

        if data is None:
            return False

        if data["status"] != "pending":
            return False

        data["decisions"].append({
            "approver_id": approver_id,
            "decision": "rejected",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

        self._update_decision(request_id, "rejected", data["decisions"])
        return True

    def check_status(self, request_id: str) -> dict:
        """承認リクエストのステータスを確認する"""
        data = self.table.get_item(Key={"request_id": request_id}).get("Item")

        if data is None:
            return {"status": "not_found"}

        return data

    def _update_decision(
        self,
        request_id: str,
        status: str,
        decisions: list[dict],
    ):
        """ステータスと判断履歴を更新する"""
        # statusはDynamoDBの予約語のため、#statusという別名で指定する
        self.table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #status = :status, decisions = :decisions",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":decisions": decisions,
            },
        )

    def _notify_approvers(
        self,
        request_id: str,
        approvers: list[str],
        tool_name: str,
        tool_input: dict,
    ):
        """承認者に通知を送信する（実装例）"""
        # SNS、Slack、メール等の通知チャネルと統合
        pass
