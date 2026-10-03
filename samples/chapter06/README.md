# 第6章 MCP & ツール統合

外部システムをエージェントのツールとして取り込むサンプルです。MCP（Model Context Protocol）サーバーへのstdio接続とStreamable HTTP接続、MCP Toolbox経由でのAmazon RDS／Aurora統合、AWS LabsのMCPサーバー経由でのAthena／DynamoDB統合、CLIコマンドのラッパー化を収録しています。ハンズオンの成果物は`infra_monitor/`で、Athena MCPサーバー（ログ分析）とkubectlラッパー（Kubernetes状態確認）を組み合わせたインフラ監視エージェントです。

## 収録内容

| ディレクトリ／ファイル | 内容 |
|---|---|
| `infra_monitor/` | ハンズオン成果物。インフラ監視エージェント（MCP + CLIラッパー） |
| `mcp_stdio_basic.py` | stdioトランスポートによるMCPサーバー接続の基本形 |
| `mcp_streamable_http_basic.py` | Streamable HTTPによるリモートMCPサーバー接続 |
| `mcp_multiple_servers.py` | 複数のMCPサーバーを1つのエージェントに統合する |
| `mcp_tool_filter.py` | `tool_filter`によるツールの絞り込み |
| `mcp_tool_filter_callback.py` | コールバック関数による動的フィルタリング（書き込み系の除外） |
| `mcp_lifecycle.py` | Runnerによる接続ライフサイクルの自動管理 |
| `mcp_error_handling.py` | MCPツール呼び出しのエラーハンドリング |
| `mcp_athena.py` | Athena MCPサーバー（AWS Labs）との統合 |
| `mcp_rds.py`／`tools-rds.yaml` | Amazon RDS（PostgreSQL）MCPサーバーとの統合 |
| `mcp_aurora.py`／`tools-aurora.yaml` | Amazon Aurora（PostgreSQL互換）MCPサーバーとの統合 |
| `mcp_dynamodb.py` | DynamoDB MCPサーバー（AWS Labs）との統合 |
| `cli_basic.py` | AWS CLIをツール化する基本パターン |
| `cli_secure.py` | サブコマンドのホワイトリストによるCLI実行の制限 |
| `cli_kubectl.py` | kubectlのツール化（`secrets`は意図的に除外） |
| `cli_terraform.py` | Terraformのツール化 |
| `mcp_cli_hybrid.py` | MCPとCLIを併用するハイブリッド構成 |
| `tool_catalog.py` | ツールカタログの定義例 |
| `tool_permissions.py` | エージェントのロールごとのツール権限マトリクス |
| `tool_audit.py` | ツール呼び出しの監査ログ |

`tools*.yaml`はMCP Toolboxの設定ファイルです。データソースの定義とツールの定義を`---`区切りで並べます。

## セットアップ

```bash
cd samples/chapter06
pip install -r requirements.txt

cd infra_monitor
cp .env.example .env
```

MCP Toolboxの起動にはNode.js v18以上が必要です。`node --version`で確認してください。AWS LabsのMCPサーバー（Athena／DynamoDB）は`uvx`で起動するため、`uv`のインストールも必要です。

## 実行

Athena MCPを無効にしたまま、kubectlラッパー（ダミーデータ）だけで起動できます。この構成ならAthenaの準備は不要です。

```bash
cd samples/chapter06
export ENABLE_ATHENA_MCP=0
adk run infra_monitor
```

Athena MCPサーバーにも接続する場合は、ワークグループの指定を加えます。ワークグループには、クエリ結果の保存先（S3）を設定しておきます。

```bash
export ATHENA_WORKGROUP="your-workgroup"
export ENABLE_ATHENA_MCP=1
adk run infra_monitor
```

ブラウザで確認する場合は`adk web .`を実行し、http://localhost:8000 でエージェント一覧から`infra_monitor`を選びます。

## AWSのリソースが必要なサンプル

`mcp_athena.py`、および`ENABLE_ATHENA_MCP=1`での`infra_monitor`は、Athenaのデータベースと、クエリ結果の保存先（S3）を設定したワークグループが前提です。ワークグループは環境変数`ATHENA_WORKGROUP`で指定します。スキャンしたデータ量に応じて課金が発生します。

`mcp_rds.py`はAmazon RDS（PostgreSQL）に、`mcp_aurora.py`はAmazon Aurora（PostgreSQL互換）に接続します。環境変数`DB_HOST`（RDSやAuroraのエンドポイント）と`DB_PASSWORD`を設定してください。`DB_HOST`を省略するとlocalhostに接続するため、ローカルのPostgreSQLでも試せます。

`mcp_dynamodb.py`はAWS LabsのDynamoDB MCPサーバーを`uvx`で起動します。AthenaとDynamoDBの認証は、Bedrockと同じAWSプロファイルを使います。

CLIラッパーのサンプルは実際に`aws`／`kubectl`／`terraform`を呼び出します。読み取り系のサブコマンドだけを許可するホワイトリストを実装していますが、対象の環境で実行される点に注意してください。`infra_monitor/tools.py`のkubectlラッパーはダミーデータを返す実装で、実際のクラスタには接続しません。
