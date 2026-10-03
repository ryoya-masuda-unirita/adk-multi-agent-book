# samples/chapter08/test_alert.py
"""アラート動作確認用のエラー発生スクリプト（8-7 ハンズオン ステップ5）

JSONとして読めないリクエストで invoke_agent_runtime を呼び出して意図的にエラーを
発生させ、agent_alerts.py で登録したエージェント層アラート（エラー率5%超）の
発火を確認する。デプロイ済みランタイムのARNは環境変数
AGENT_RUNTIME_ARN で指定する。

使い方:
  export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:ap-northeast-1:123456789012:runtime/my_agent-abc123
  python test_alert.py
"""
import asyncio
import os
import sys
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def get_agentcore_client() -> object:
    """AgentCore Runtimeを呼び出すクライアントを取得する"""
    # 意図的に発生させたエラーをboto3が自動でリトライしないようにする
    return boto3.client(
        "bedrock-agentcore",
        config=Config(retries={"max_attempts": 1}),
    )


async def trigger_errors(
    error_count: int = 5,
    agentcore_client: object | None = None,
) -> int:
    """JSONとして読めないリクエストを送り、意図的にエラーを発生させる"""
    client = agentcore_client or get_agentcore_client()
    runtime_arn = os.environ["AGENT_RUNTIME_ARN"]

    triggered = 0
    for i in range(error_count):
        try:
            # ペイロードを不正な形式にして、エージェント側のエラー（4xx）を誘発する
            await asyncio.to_thread(
                client.invoke_agent_runtime,
                agentRuntimeArn=runtime_arn,
                runtimeSessionId=f"alert-test-session-{uuid.uuid4().hex}",
                contentType="application/json",
                payload=b"alert test: this is not json",
            )
            print(f"[{i}] エラーが発生しませんでした（想定外）")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            triggered += 1
            if error_code == "RuntimeClientError":
                # 想定どおりのエラー。アラートの集計対象になる
                print(f"[{i}] RuntimeClientError を発生させました（アラート集計対象）")
            else:
                # それ以外のAPIエラーもエラー率に計上される
                print(f"[{i}] APIエラーを発生させました: {error_code}")

    return triggered


async def main() -> None:
    """指定回数のエラーを発生させ、アラート確認の案内を表示する"""
    error_count = int(os.environ.get("ERROR_COUNT", "5"))
    triggered = await trigger_errors(error_count=error_count)

    print(f"合計 {triggered} 件のエラーを発生させました。")
    print(
        "数分後に CloudWatch のアラーム"
        "（AgentCore Runtime - Error Rate > 5%）が発火することを確認してください。"
    )


if __name__ == "__main__":
    if not os.environ.get("AGENT_RUNTIME_ARN"):
        print(
            "環境変数 AGENT_RUNTIME_ARN を"
            "デプロイ済みランタイムのARNに設定してください。"
        )
        sys.exit(2)

    asyncio.run(main())
