# knowledge_base_setup.py: Knowledge Baseの初期セットアップ
"""Amazon Bedrock Knowledge Bases を作成し、ドキュメントを取り込むスクリプト（4-6-4節）。

Knowledge Baseの作成とドキュメントの取り込みを1回だけ実行するセットアップ用途。
ハンズオン（4-7節）のStep 4は、このスクリプトでKnowledge Baseを準備してから
環境変数 KNOWLEDGE_BASE_ID を設定してエージェントを起動する前提。

ベクトルの保存先にはAmazon S3 Vectorsを使う。次のリソースは事前に用意しておく。
  - S3 Vectorsのベクトルバケットとインデックス（次元数1024、距離の計算方法はcosine）
  - Knowledge Base用のIAMロール（埋め込みモデルの呼び出し、ドキュメントの読み取り、
    インデックスの読み書きを許可したもの）

必要な環境変数:
  KB_ROLE_ARN        : Knowledge Base用IAMロールのARN（必須）
  VECTOR_INDEX_ARN   : S3 VectorsのインデックスのARN（必須）
  RAG_IMPORT_BUCKET  : 取り込むドキュメントを置いたS3バケット名（必須）
  RAG_IMPORT_PREFIX  : 取り込み対象のプレフィックス（省略時はバケット全体）
                       例: docs/
  KB_NAME            : 作成するKnowledge Baseの名前（デフォルト: product_documentation）

実行例:
  export KB_ROLE_ARN="arn:aws:iam::123456789012:role/your-kb-role"
  export VECTOR_INDEX_ARN="arn:aws:s3vectors:ap-northeast-1:123456789012:bucket/your-vectors/index/your-index"
  export RAG_IMPORT_BUCKET="your-bucket"
  python knowledge_base_setup.py
"""
from __future__ import annotations

import os
import time

import boto3

# 埋め込みモデル（文章をベクトルに変換するモデル）。出力は1024次元
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"

# チャンク設定の既定値（4-6-4節「チャンク戦略の設計」参照）
DEFAULT_CHUNK_SIZE = 512            # チャンクサイズ（トークン数）。精度と文脈のバランスが良い
DEFAULT_CHUNK_OVERLAP_PERCENT = 20  # チャンク間のオーバーラップ（チャンクサイズの20〜30%が目安）


def create_knowledge_base(
    client,
    name: str,
    description: str,
    role_arn: str,
    vector_index_arn: str,
) -> str:
    """Knowledge Baseを新規作成し、IDを返す。"""
    region = client.meta.region_name
    response = client.create_knowledge_base(
        name=name,
        description=description,
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": (
                    f"arn:aws:bedrock:{region}::foundation-model/{EMBEDDING_MODEL_ID}"
                ),
            },
        },
        storageConfiguration={
            "type": "S3_VECTORS",
            "s3VectorsConfiguration": {"indexArn": vector_index_arn},
        },
    )
    knowledge_base_id = response["knowledgeBase"]["knowledgeBaseId"]

    # 作成は非同期で進むため、利用可能（ACTIVE）になるまで待つ
    while True:
        status = client.get_knowledge_base(
            knowledgeBaseId=knowledge_base_id
        )["knowledgeBase"]["status"]
        if status != "CREATING":
            break
        time.sleep(2)
    if status != "ACTIVE":
        raise RuntimeError(f"Knowledge Baseの作成に失敗しました: {status}")

    print(f"Knowledge Baseを作成しました: {knowledge_base_id}")
    return knowledge_base_id


def import_documents(
    client,
    knowledge_base_id: str,
    bucket: str,
    prefix: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap_percent: int = DEFAULT_CHUNK_OVERLAP_PERCENT,
) -> None:
    """指定したS3バケットのドキュメントをKnowledge Baseへ取り込む。

    チャンク設定は、データソースの vectorIngestionConfiguration に
    固定サイズ（FIXED_SIZE）のチャンク戦略として渡す。
    """
    s3_configuration = {"bucketArn": f"arn:aws:s3:::{bucket}"}
    if prefix:
        s3_configuration["inclusionPrefixes"] = [prefix]

    data_source_id = client.create_data_source(
        knowledgeBaseId=knowledge_base_id,
        name="documents",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": s3_configuration,
        },
        vectorIngestionConfiguration={
            "chunkingConfiguration": {
                "chunkingStrategy": "FIXED_SIZE",
                "fixedSizeChunkingConfiguration": {
                    "maxTokens": chunk_size,
                    "overlapPercentage": chunk_overlap_percent,
                },
            },
        },
    )["dataSource"]["dataSourceId"]

    # 取り込み（ドキュメントの分割とベクトル化）を開始し、完了まで待つ
    job = client.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id,
    )["ingestionJob"]
    while job["status"] in ("STARTING", "IN_PROGRESS"):
        time.sleep(5)
        job = client.get_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            ingestionJobId=job["ingestionJobId"],
        )["ingestionJob"]
    if job["status"] != "COMPLETE":
        raise RuntimeError(f"ドキュメントの取り込みに失敗しました: {job['status']}")

    indexed = job["statistics"]["numberOfNewDocumentsIndexed"]
    print(f"{indexed} 件のドキュメントを取り込みました: {knowledge_base_id}")


def main() -> None:
    """環境変数を読み取り、Knowledge Baseの作成とドキュメント取り込みを実行する。"""
    role_arn = os.environ.get("KB_ROLE_ARN")
    if not role_arn:
        raise ValueError("環境変数 KB_ROLE_ARN の設定が必要です")

    vector_index_arn = os.environ.get("VECTOR_INDEX_ARN")
    if not vector_index_arn:
        raise ValueError("環境変数 VECTOR_INDEX_ARN の設定が必要です")

    bucket = os.environ.get("RAG_IMPORT_BUCKET")
    if not bucket:
        raise ValueError(
            "環境変数 RAG_IMPORT_BUCKET（取り込むドキュメントを置いたS3バケット名）の設定が必要です"
        )

    name = os.environ.get("KB_NAME", "product_documentation")

    client = boto3.client("bedrock-agent")

    knowledge_base_id = create_knowledge_base(
        client,
        name=name,
        description="製品ドキュメントとFAQのKnowledge Base",
        role_arn=role_arn,
        vector_index_arn=vector_index_arn,
    )
    import_documents(
        client,
        knowledge_base_id=knowledge_base_id,
        bucket=bucket,
        prefix=os.environ.get("RAG_IMPORT_PREFIX"),
    )

    # エージェント側（memory_agent/agent.py・rag_knowledge_bases.py）は
    # このIDを環境変数から受け取って検索ツールを組み立てる
    print(f"エージェントに設定する KNOWLEDGE_BASE_ID: {knowledge_base_id}")


if __name__ == "__main__":
    main()
