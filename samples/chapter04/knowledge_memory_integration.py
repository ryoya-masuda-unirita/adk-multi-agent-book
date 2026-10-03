# samples/chapter04/knowledge_memory_integration.py
"""静的知識（RAG）と動的記憶（AgentCore Memory）の統合構成例（4-7-1節）

Bedrock Knowledge Basesに静的知識（製品ドキュメント・ポリシー）を置き、
AgentCore Memoryにユーザー固有の動的記憶を置く分離設計を、
Runnerで1つの構成に統合する。

必要な環境変数:
  AGENTCORE_MEMORY_ID : AgentCore MemoryのID
  PRODUCT_KB_ID       : 製品ドキュメント用Knowledge BaseのID
  POLICY_KB_ID        : ポリシー・規約用Knowledge BaseのID
  DATABASE_URL        : Sessionを保存するデータベースの接続URL
                        （省略時はローカルのSQLiteファイル）
"""
import os

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from memory_agent.agentcore_memory import AgentCoreMemoryService
from memory_agent.knowledge_base import create_kb_retrieval_tool

# 各リソースのIDは環境変数から取得する
AGENTCORE_MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "YOUR_MEMORY_ID")
PRODUCT_KB_ID = os.environ.get("PRODUCT_KB_ID", "PRODUCT_KB_ID")
POLICY_KB_ID = os.environ.get("POLICY_KB_ID", "POLICY_KB_ID")

# RAGツール: 静的知識の検索
product_docs = create_kb_retrieval_tool(
    name="product_docs",
    description="製品ドキュメント、FAQ、利用規約を検索します。"
                "製品の仕様や手続きについての質問に回答する際に使用してください。",
    knowledge_base_id=PRODUCT_KB_ID,
    number_of_results=5,
    score_threshold=0.5,
)

policy_docs = create_kb_retrieval_tool(
    name="policy_docs",
    description="返品ポリシー、配送規定、保証規定を検索します。"
                "ポリシーや規定に関する質問に回答する際に使用してください。",
    knowledge_base_id=POLICY_KB_ID,
    number_of_results=3,
    score_threshold=0.7,  # 規約は高精度が必須
)

async def save_session_to_memory(callback_context: CallbackContext) -> None:
    """対話後に現在のSessionをAgentCore Memoryへ取り込む"""
    await callback_context.add_session_to_memory()


# エージェントの定義: RAGツールとMemory検索ツールを装備
agent = Agent(
    name="support_agent",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""カスタマーサポートエージェントです。

    ## 情報の使い分け
    - 製品の仕様や手続きに関する質問: product_docs を検索してください
    - ポリシーや規定に関する質問: policy_docs を検索してください
    - ユーザーの過去の問い合わせや嗜好: AgentCore Memoryから先読みされた記憶を参照してください

    ## 回答ルール
    - 検索結果に基づいて回答してください
    - 情報が見つからない場合は、正直にその旨を伝えてください
    - ユーザーの過去のやり取りを踏まえて、パーソナライズした応答を心がけてください""",
    tools=[product_docs, policy_docs, PreloadMemoryTool()],
    after_agent_callback=save_session_to_memory,
)

# AgentCore Memory: 動的記憶の管理
memory_service = AgentCoreMemoryService(memory_id=AGENTCORE_MEMORY_ID)

# SessionService: Session管理（本番ではAmazon RDSなどのデータベースに保存する）
session_service = DatabaseSessionService(
    db_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///sessions.db"),
)

# Runnerで統合（Compactionなしの構成例。本番ではApp経由で有効化する。4-4節参照）
runner = Runner(
    agent=agent,
    app_name="customer_support",
    session_service=session_service,
    memory_service=memory_service,  # AgentCore MemoryをRunnerへ接続
)


if __name__ == "__main__":
    # 構成の確認（API呼び出しは行わない）
    print(f"エージェント: {agent.name}")
    print(f"RAGツール: {[tool.name for tool in agent.tools]}")
    print(f"SessionService: {type(session_service).__name__}")
    print(f"MemoryService: {type(memory_service).__name__}")
