# samples/chapter10/secure_agent/cloud_audit_integration.py
"""CloudWatch Logs統合（10-5-2節）

エージェントの監査イベントを Amazon CloudWatch Logs に構造化ログ（JSON）として送出する。
AWSのサービス管理操作・データアクセスを記録する AWS CloudTrail とは別物だが、
CloudWatch Logs Insights から横断検索することで統合的に分析できる。

実行時依存: boto3 パッケージが必要
認証はboto3の標準認証チェーン（環境変数 AWS_PROFILE など）を使用する。
送出先のロググループ（既定: /agent/audit）は事前に作成しておく。
"""
import json
import time
from datetime import datetime, timedelta, timezone

import boto3

JST = timezone(timedelta(hours=9))


class CloudAuditLogger:
    """CloudWatch Logsに監査ログを送信する"""

    def __init__(
        self,
        log_group: str = "/agent/audit",
        log_stream: str = "agent-audit",
        region_name: str | None = None,
    ):
        self.client = boto3.client("logs", region_name=region_name)
        self.log_group = log_group
        self.log_stream = log_stream
        # ログストリーム（ロググループ内の送出単位）が無ければ作成する
        try:
            self.client.create_log_stream(
                logGroupName=log_group, logStreamName=log_stream
            )
        except self.client.exceptions.ResourceAlreadyExistsException:
            pass

    def log_agent_action(
        self,
        action: str,
        agent_name: str,
        user_id: str,
        session_id: str,
        details: dict | None = None,
        severity: str = "INFO",
    ) -> None:
        """エージェントのアクションを監査ログとして記録する"""
        entry = {
            "action": action,
            "agent_name": agent_name,
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.now(JST).isoformat(),
            "details": details or {},
            # CloudWatch Logsには重要度やラベルの専用欄が無いため、JSONの項目として持たせる
            "severity": severity,
            "component": "agent-system",
        }
        self.client.put_log_events(
            logGroupName=self.log_group,
            logStreamName=self.log_stream,
            logEvents=[{
                "timestamp": int(time.time() * 1000),
                "message": json.dumps(entry, ensure_ascii=False),
            }],
        )

    def log_security_event(
        self,
        session_id: str,
        user_id: str,
        event_type: str,
        details: dict,
        agent_name: str = "",
    ) -> None:
        """セキュリティイベントを記録する

        引数順は10-5-1節の `AuditLogger.log_security_event` と揃えている。
        ローカル監査（`AuditLogger`）と Cloud 連携（`CloudAuditLogger`）を
        用途に応じて使い分けられる。
        ただし `details` の型は CloudWatch Logs に構造化データとして送るため
        `dict` とし、`AuditLogger`（JSON 文字列化した `str`）とは異なる。
        呼び出し側は送信先に合わせて型を組み立てる。
        """
        self.log_agent_action(
            action=f"security:{event_type}",
            agent_name=agent_name,
            user_id=user_id,
            session_id=session_id,
            details=details,
            severity="WARNING",
        )
