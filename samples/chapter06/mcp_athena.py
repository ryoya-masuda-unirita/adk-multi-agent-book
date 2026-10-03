# samples/chapter06/mcp_athena.py
"""Athena MCPサーバー（AWS Labs）とADKの統合例"""

import os

from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters


# AWS LabsのData Processing MCPサーバーを起動してAthenaのツールを公開
athena_server = StdioConnectionParams(
    server_params=StdioServerParameters(
        command="uvx",
        args=[
            "awslabs.aws-dataprocessing-mcp-server@latest",
            # クエリ結果の読み取りに必要
            "--allow-sensitive-data-access",
        ],
        # AWS_PROFILE / AWS_REGION などの認証設定をMCPサーバーに引き継ぐ
        env={k: v for k, v in os.environ.items() if k.startswith("AWS_")},
    ),
    timeout=60,  # 初回はパッケージの取得に時間がかかるため長めにする
)

# クエリ結果の保存先（S3）を設定済みのワークグループ
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "primary")

# データ分析エージェント
data_analyst = Agent(
    name="data_analyst",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction=f"""あなたはAthenaを使ったデータ分析の専門家です。

    ## 利用可能なツール
    - manage_aws_athena_databases_and_tables: データベースとテーブルのメタデータを取得
      - list-databases / list-table-metadata / get-table-metadata
      - catalog_name には AwsDataCatalog を指定する
    - manage_aws_athena_query_executions: SQLクエリを実行
      - start-query-execution でクエリを開始する（work_group には {ATHENA_WORKGROUP} を指定する）
      - get-query-execution で状態が SUCCEEDED になるのを確認する
      - get-query-results で結果を取得する

    ## 分析の手順
    1. まずスキーマ情報を確認し、データの構造を理解する
    2. ユーザーの質問に答えるためのSQLクエリを組み立てる
    3. クエリを実行し、結果をわかりやすく説明する

    ## 注意事項
    - 大量のデータをスキャンするクエリは、先にWHERE句で絞り込む
    - SELECT *は避け、必要なカラムのみを指定する
    - コストに配慮し、LIMIT句を適切に使用する""",
    tools=[
        McpToolset(
            connection_params=athena_server,
            # Athenaの参照とクエリ実行のツールだけを公開する
            tool_filter=[
                "manage_aws_athena_databases_and_tables",
                "manage_aws_athena_query_executions",
            ],
        ),
    ],
)
