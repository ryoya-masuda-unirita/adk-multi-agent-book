# samples/chapter06/mcp_aurora.py
"""Amazon Aurora MCPサーバー（MCP Toolbox）とADKの統合例"""

import os

from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters


# Aurora用のtools.yamlを指定してToolboxを起動
aurora_server = StdioConnectionParams(
    server_params=StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@toolbox-sdk/server",
            "--stdio",
            "--config", "tools-aurora.yaml",
        ],
        env={
            # 参照専用のため、Auroraクラスターの読み取りエンドポイントを指定する
            # （例: mycluster.cluster-ro-xxxx.ap-northeast-1.rds.amazonaws.com）
            "DB_HOST": os.environ.get("DB_HOST", "localhost"),
            "DB_PASSWORD": os.environ.get("DB_PASSWORD", ""),
        },
    )
)

# Auroraデータ参照エージェント
aurora_agent = Agent(
    name="aurora_reader",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""あなたはAmazon Aurora（PostgreSQL互換）のデータを参照する分析エージェントです。

    Auroraは書き込み用と読み取り用のインスタンスに分かれたデータベースであり、以下の特性を理解した上でクエリを組み立ててください。
    - 主キーによるアクセスが最も効率的
    - 読み取りエンドポイントに接続しているため、直前の書き込みが反映されていない場合がある
    - セカンダリインデックスの存在を確認してから使う

    データの参照のみを行い、変更操作は行いません。""",
    tools=[
        McpToolset(
            connection_params=aurora_server,
            tool_filter=["execute_query"],  # 読み取り専用ツールのみ公開
        ),
    ],
)
