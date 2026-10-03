# samples/chapter06/infra_monitor/agent.py
"""第6章 ハンズオン: インフラ監視エージェント

Athena MCPサーバー（ログ分析）と kubectl CLIラッパー（Kubernetes状態確認）を
組み合わせたインフラ監視エージェント。
"""

import os
import sys

from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

try:
    from .tools import kubectl_get_events, kubectl_get_nodes, kubectl_get_pods
except ImportError:
    # ADKがエージェントディレクトリを直接ロードする場合のフォールバック
    sys.path.insert(0, os.path.dirname(__file__))
    from tools import kubectl_get_events, kubectl_get_nodes, kubectl_get_pods

def _athena_enabled() -> bool:
    """Athena MCPサーバーを接続するかどうかを環境変数から判定する"""
    return os.environ.get("ENABLE_ATHENA_MCP") == "1"


def _build_tools() -> list:
    """ローカル検証時に外部MCPサーバーなしでも起動できるツール構成を返す"""
    tools = [
        kubectl_get_pods,
        kubectl_get_nodes,
        kubectl_get_events,
    ]

    if not _athena_enabled():
        return tools

    # Athena MCPサーバー（AWS LabsのData Processing MCPサーバー）の接続パラメータ。
    # 実行には uv（uvxコマンド）とAWSの認証設定が必要。
    athena_connection = StdioConnectionParams(
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
    tools.append(
        McpToolset(
            connection_params=athena_connection,
            tool_filter=[
                "manage_aws_athena_databases_and_tables",
                "manage_aws_athena_query_executions",
            ],
        )
    )
    return tools


def _build_instruction() -> str:
    """ツール構成に合わせて行動指針を組み立てる

    Athena MCPが無効なローカル検証時は、未登録のログ分析ツールを
    モデルが呼び出してエラーになるのを防ぐため、kubectl運用に限定した
    指示を返す。
    """
    common_footer = """
## 判断の手順
1. まずユーザーのリクエストに応じて適切なツールでデータを収集する
2. 収集したデータを分析し、異常や問題点を特定する
3. 問題が見つかった場合は、具体的な対処法を提示する

## レポート形式
調査結果は以下の形式で報告する:
- **概要**: 何を調査し、何が分かったか
- **詳細**: 具体的なデータや数値
- **推奨対処**: 問題がある場合の対処法
"""

    if _athena_enabled():
        workgroup = os.environ.get("ATHENA_WORKGROUP", "primary")
        return (
            f"""あなたはインフラ監視の専門エージェントです。
Athenaで参照できるアプリケーションログの分析と、
Kubernetesクラスタの状態監視を担当します。

## ツールの使い分け
- **ログ分析**: Athena MCPツールでSQLクエリを実行し、ログを検索・集計する
- **クラスタ状態確認**: kubectlツール群を使用してPod・Node・イベントを確認する

## Athenaクエリの実行手順
1. manage_aws_athena_databases_and_tables でテーブルの構造を確認する（catalog_name は AwsDataCatalog）
2. manage_aws_athena_query_executions の start-query-execution でクエリを開始する（work_group は {workgroup}）
3. get-query-execution で状態が SUCCEEDED になるのを確認し、get-query-results で結果を取得する

## Athenaクエリのルール
- 必ず LIMIT 句を付ける（最大1000行）
- SELECT * は避け、必要なカラムのみ指定する
- 大きなテーブルにはパーティションフィルタを使用する
"""
            + common_footer
        )

    # ローカル検証モード（Athena MCP無効）: kubectlツールのみを案内する
    return (
        """あなたはインフラ監視の専門エージェントです。
Kubernetesクラスタの状態監視を担当します。

## ツールの使い分け
- **クラスタ状態確認**: kubectlツール群を使用してPod・Node・イベントを確認する

ログ分析用のAthena MCPツールは現在無効です。ログ分析を求められた場合は、
ENABLE_ATHENA_MCP=1 で再起動が必要なことを伝え、kubectlで確認できる範囲を案内する。
"""
        + common_footer
    )


# インフラ監視エージェントの定義
root_agent = Agent(
    name="infra_monitor",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction=_build_instruction(),
    tools=_build_tools(),
)
