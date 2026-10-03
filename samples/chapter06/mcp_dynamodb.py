# samples/chapter06/mcp_dynamodb.py
"""DynamoDB MCPサーバー（AWS Labs）とADKの統合例"""

import os

from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters


# AWS LabsのDynamoDB MCPサーバーを起動
# 2.x系はデータ設計の支援専用になり読み書きのツールが無いため、1.x系に固定する
dynamodb_server = StdioConnectionParams(
    server_params=StdioServerParameters(
        command="uvx",
        args=["awslabs.dynamodb-mcp-server==1.0.9"],
        # AWS_PROFILE / AWS_REGION などの認証設定をMCPサーバーに引き継ぐ
        env={k: v for k, v in os.environ.items() if k.startswith("AWS_")},
    ),
    timeout=60,  # 初回はパッケージの取得に時間がかかるため長めにする
)

# ドキュメント管理エージェント
doc_agent = Agent(
    name="dynamodb_agent",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""あなたはDynamoDBのデータを管理するエージェントです。

    ## 利用可能なテーブル
    - users: ユーザー情報
    - orders: 注文データ
    - products: 商品マスタ

    ## 操作方針
    - 参照操作は自由に実行する
    - 項目の作成・更新はユーザーの承認後に実行する
    - テーブル全体の削除は行わない""",
    tools=[
        McpToolset(
            connection_params=dynamodb_server,
            # 参照（scan / query / get_item）と追加（put_item）だけを公開する
            tool_filter=["scan", "query", "get_item", "put_item"],
        ),
    ],
)
