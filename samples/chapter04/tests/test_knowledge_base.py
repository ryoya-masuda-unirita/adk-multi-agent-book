# samples/chapter04/tests/test_knowledge_base.py
"""Knowledge Base検索ツールのテスト

AWSへの接続は不要。boto3のクライアントをモックに差し替えて、
検索結果の整形とスコアによる絞り込みを検証する。
"""
from unittest.mock import MagicMock, patch

from memory_agent.knowledge_base import create_kb_retrieval_tool


def _fake_client() -> MagicMock:
    """Retrieve APIの応答を返すモッククライアントを生成する"""
    client = MagicMock()
    client.retrieve.return_value = {
        "retrievalResults": [
            {
                "content": {"text": "返品は14日以内です。"},
                "score": 0.82,
                "location": {"s3Location": {"uri": "s3://docs/return_policy.md"}},
            },
            {
                "content": {"text": "関連の薄い文書"},
                "score": 0.31,
                "location": {},
            },
        ]
    }
    return client


def test_tool_uses_given_name_and_description():
    """指定したnameとdescriptionがツールに反映されること"""
    tool = create_kb_retrieval_tool(
        name="policy_docs",
        description="返品ポリシーを検索します。",
        knowledge_base_id="KB123",
    )
    assert tool.name == "policy_docs"
    assert "返品ポリシーを検索します。" in tool.description


def test_retrieve_filters_by_score_threshold():
    """score_threshold未満の検索結果が除外されること"""
    client = _fake_client()
    tool = create_kb_retrieval_tool(
        name="policy_docs",
        description="返品ポリシーを検索します。",
        knowledge_base_id="KB123",
        number_of_results=3,
        score_threshold=0.5,
    )

    with patch("memory_agent.knowledge_base.boto3.client", return_value=client):
        result = tool.func(query="返品期間は？")

    assert result["status"] == "success"
    assert result["results"] == [
        {
            "text": "返品は14日以内です。",
            "score": 0.82,
            "source": "s3://docs/return_policy.md",
        }
    ]
    client.retrieve.assert_called_once_with(
        knowledgeBaseId="KB123",
        retrievalQuery={"text": "返品期間は？"},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": 3},
        },
    )
