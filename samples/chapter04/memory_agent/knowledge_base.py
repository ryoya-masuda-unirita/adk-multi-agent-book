# samples/chapter04/memory_agent/knowledge_base.py
"""Amazon Bedrock Knowledge BasesをADKのツールとして使うための部品

ADKにはBedrock Knowledge Bases用のツールが用意されていないため、
検索API（Retrieve）を呼び出す関数をFunctionToolとして公開する。
"""
import boto3
from google.adk.tools import FunctionTool


def create_kb_retrieval_tool(
    name: str,
    description: str,
    knowledge_base_id: str,
    number_of_results: int = 5,
    score_threshold: float = 0.5,
    region_name: str | None = None,
) -> FunctionTool:
    """Knowledge Baseを検索するツールを生成する

    Args:
        name: ツール名（エージェントがツールを選ぶときの識別名）
        description: ツールの説明（エージェントがツールを選ぶ判断材料）
        knowledge_base_id: 検索対象のKnowledge BaseのID
        number_of_results: 取得する検索結果の最大件数
        score_threshold: この関連度スコア（0〜1、高いほど関連が強い）未満の結果を除外する
        region_name: Knowledge Baseのリージョン（省略時はAWSプロファイルの設定）
    """

    def retrieve(query: str) -> dict:
        client = boto3.client("bedrock-agent-runtime", region_name=region_name)
        response = client.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": number_of_results,
                },
            },
        )
        results = [
            {
                "text": result["content"]["text"],
                "score": result["score"],
                "source": result.get("location", {})
                .get("s3Location", {})
                .get("uri", ""),
            }
            for result in response["retrievalResults"]
            if result["score"] >= score_threshold
        ]
        return {"status": "success", "results": results}

    # FunctionToolは関数名とdocstringをツール名と説明として使う
    retrieve.__name__ = name
    retrieve.__doc__ = f"""{description}

    Args:
        query: 検索したい内容を表す文章

    Returns:
        関連度の高い順に並んだ検索結果"""
    return FunctionTool(func=retrieve)
