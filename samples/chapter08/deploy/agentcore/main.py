# samples/chapter08/deploy/agentcore/main.py
"""AgentCore Runtime用のエントリポイント

ADKエージェントをBedrockAgentCoreAppでラップし、AgentCore Runtimeが呼び出す
HTTPサーバー（ポート8080の /invocations と /ping）として公開する。
デプロイ時は、このファイルと support_agent/ を同じ階層に置いてzipにまとめる
（deploy_sdk.py の build_package を参照）。

AgentCore Runtimeは、runtimeSessionIdごとに独立した実行環境を割り当てる。
同じセッションIDの呼び出しは同じ実行環境に届くため、Sessionはメモリ上に保持する。
実行環境が破棄された後も会話を引き継ぐ場合は、DatabaseSessionServiceに差し替える。
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from support_agent.agent import root_agent

APP_NAME = "customer_support"

app = BedrockAgentCoreApp()
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


@app.entrypoint
async def invoke(payload: dict, context) -> dict:
    """エージェントとの対話エンドポイント

    payloadの形式: {"message": "問い合わせ内容", "user_id": "ユーザーID"}
    セッションIDは、呼び出し時に指定された runtimeSessionId を使う。
    """
    message = payload.get("message")
    if not message:
        # 不正なリクエストは例外にせず、エラー内容を応答として返す
        return {"error": "message を指定してください"}

    user_id = payload.get("user_id", "anonymous")
    session_id = context.session_id

    # 指定されたSessionがなければ作成する
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    # Runnerを実行し、最後のエージェント応答を取得
    final_response = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=message)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text or ""

    return {"response": final_response, "session_id": session_id}


if __name__ == "__main__":
    app.run()
