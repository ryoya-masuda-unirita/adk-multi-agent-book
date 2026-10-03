# samples/chapter08/query_with_retry.py
"""AgentCore Runtime呼び出しのエラーハンドリング実装例（8-4-6 完全版）

レート制限（ThrottlingException）・サービス一時停止（InternalServerException）は
指数バックオフでリトライし、不正リクエスト（ValidationException など）・リソース不在
（ResourceNotFoundException）はリトライせずに呼び出し元へ通知する。
紙面で省略したサービス一時停止 / リソース不在のハンドリングを含む完全版。
"""
import asyncio
import json
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ParamValidationError

# レート制限として扱うエラーコード
THROTTLING_ERRORS = {"ThrottlingException", "ServiceQuotaExceededException"}
# サービス側の一時的な障害として扱うエラーコード
UNAVAILABLE_ERRORS = {"InternalServerException", "ServiceException"}
# リクエストの内容が不正な場合のエラーコード（RuntimeClientErrorはエージェント側が4xxを返した場合）
INVALID_REQUEST_ERRORS = {"ValidationException", "RuntimeClientError"}


def get_agentcore_client() -> object:
    """AgentCore Runtimeを呼び出すクライアントを取得する"""
    # リトライはこのモジュールで制御するため、boto3の自動リトライは無効にする。
    # エージェントの応答には時間がかかるため、読み取りのタイムアウトは長めにする
    return boto3.client(
        "bedrock-agentcore",
        config=Config(read_timeout=300, retries={"max_attempts": 1}),
    )


def get_agent_runtime_arn() -> str:
    """環境変数で指定されたランタイムのARNを取得する"""
    return os.environ.get(
        "AGENT_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:ap-northeast-1:123456789012:runtime/my_agent-abc123",
    )


async def query_with_retry(
    user_id: str,
    session_id: str,
    message: str,
    max_retries: int = 3,
    agentcore_client: object | None = None,
) -> object:
    """リトライ付きのクエリ実行

    session_id は33文字以上が必要（AgentCore RuntimeのruntimeSessionIdの制約）。
    """
    client = agentcore_client or get_agentcore_client()
    payload = json.dumps({"message": message, "user_id": user_id}).encode()

    for attempt in range(max_retries):
        try:
            # boto3は同期APIのため、イベントループを止めないよう別スレッドで呼び出す
            response = await asyncio.to_thread(
                client.invoke_agent_runtime,
                agentRuntimeArn=get_agent_runtime_arn(),
                runtimeSessionId=session_id,
                contentType="application/json",
                payload=payload,
            )
            return json.loads(response["response"].read())

        except ParamValidationError as e:
            # 送信前の検査で不正と判定されたリクエスト（セッションIDが短いなど）: リトライ不要
            raise ValueError(f"リクエストが不正です: {e}") from e

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code in THROTTLING_ERRORS:
                # レート制限: 指数バックオフで待機
                wait_time = 2 ** attempt
                print(f"レート制限。{wait_time}秒後にリトライします...")
                await asyncio.sleep(wait_time)

            elif error_code in UNAVAILABLE_ERRORS:
                # サービス一時停止: リトライ
                wait_time = 2 ** attempt
                print(f"サービス一時停止。{wait_time}秒後にリトライします...")
                await asyncio.sleep(wait_time)

            elif error_code in INVALID_REQUEST_ERRORS:
                # 不正なリクエスト: リトライ不要
                raise ValueError(f"リクエストが不正です: {e}") from e

            elif error_code == "ResourceNotFoundException":
                # リソースが見つからない: デプロイ先の指定を確認する
                raise ValueError(
                    "ランタイムが見つかりません。"
                    "AGENT_RUNTIME_ARN の指定を確認してください。"
                ) from e

            else:
                raise

    raise RuntimeError(f"{max_retries}回のリトライ後も失敗しました")
