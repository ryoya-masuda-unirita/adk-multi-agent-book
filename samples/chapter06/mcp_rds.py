# samples/chapter06/mcp_rds.py
"""Amazon RDS MCPサーバー（MCP Toolbox）とADKの統合例"""

import os

from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters


# RDS用のtools.yamlを指定してToolboxを起動
rds_server = StdioConnectionParams(
    server_params=StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@toolbox-sdk/server",
            "--stdio",
            "--config", "tools-rds.yaml",
        ],
        env={
            # RDSのエンドポイント（例: mydb.xxxx.ap-northeast-1.rds.amazonaws.com）
            "DB_HOST": os.environ.get("DB_HOST", "localhost"),
            "DB_PASSWORD": os.environ.get("DB_PASSWORD", ""),
        },
    )
)

# 業務データベース操作エージェント
db_agent = Agent(
    name="db_operator",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""あなたはAmazon RDS上の業務データベースを操作するエージェントです。

    ## 権限
    - SELECT: 許可
    - INSERT/UPDATE: ユーザーの明示的な承認後のみ実行
    - DELETE/DROP: 禁止

    ## 操作の手順
    1. テーブル構造を確認する
    2. ユーザーの要求を理解し、必要なクエリを構築する
    3. SELECTクエリは即座に実行する
    4. データ変更クエリは、実行前にSQLの内容をユーザーに提示し承認を得る""",
    tools=[
        McpToolset(connection_params=rds_server),
    ],
)
