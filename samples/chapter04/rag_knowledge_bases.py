# samples/chapter04/rag_knowledge_bases.py
"""複数のKnowledge Baseの使い分け例（4-6-3節）

情報の種類ごとにKnowledge Baseを分離し、name / description と
検索パラメータ（number_of_results / score_threshold）を
Knowledge Baseごとに最適化する。

必要な環境変数:
  PRODUCT_KB_ID  : 製品ドキュメント用Knowledge BaseのID
  FAQ_KB_ID      : FAQ用Knowledge BaseのID
  POLICY_KB_ID   : ポリシー・規約用Knowledge BaseのID
"""
import os

from google.adk import Agent

from memory_agent.knowledge_base import create_kb_retrieval_tool

# Knowledge BaseのIDは環境変数から取得する
PRODUCT_KB_ID = os.environ.get("PRODUCT_KB_ID", "PRODUCT_KB_ID")
FAQ_KB_ID = os.environ.get("FAQ_KB_ID", "FAQ_KB_ID")
POLICY_KB_ID = os.environ.get("POLICY_KB_ID", "POLICY_KB_ID")

# 製品ドキュメント用のRAGツール
product_docs = create_kb_retrieval_tool(
    name="product_docs",
    description="製品の仕様、機能、互換性情報を検索します。"
                "製品についての技術的な質問に回答する際に使用してください。",
    knowledge_base_id=PRODUCT_KB_ID,
    number_of_results=5,
    score_threshold=0.5,
)

# FAQ用のRAGツール
faq_docs = create_kb_retrieval_tool(
    name="faq_docs",
    description="よくある質問と回答を検索します。"
                "一般的な問い合わせに対する標準的な回答を取得する際に使用してください。",
    knowledge_base_id=FAQ_KB_ID,
    number_of_results=3,
    score_threshold=0.6,  # FAQは精度重視
)

# ポリシー・規約用のRAGツール
policy_docs = create_kb_retrieval_tool(
    name="policy_docs",
    description="返品ポリシー、利用規約、保証規定を検索します。"
                "ポリシーや法的な質問に回答する際に使用してください。",
    knowledge_base_id=POLICY_KB_ID,
    number_of_results=3,
    score_threshold=0.7,  # 規約は高精度が必須
)

# エージェントに3つのRAGツールを装備
agent = Agent(
    name="support_agent",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""カスタマーサポートエージェントです。

    ## ツールの使い分け
    - 製品の仕様や技術的な質問 → product_docs
    - 一般的な問い合わせ → faq_docs
    - 返品・保証・規約に関する質問 → policy_docs

    回答には検索結果を根拠として使用してください。""",
    tools=[product_docs, faq_docs, policy_docs],
)


if __name__ == "__main__":
    # ツール構成の確認（API呼び出しは行わない）
    for tool in (product_docs, faq_docs, policy_docs):
        print(f"RAGツール: {tool.name}")
    print(f"エージェント: {agent.name}（ツール数: {len(agent.tools)}）")
