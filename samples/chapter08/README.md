# 第8章 AgentCore Runtime & AgentOps

ローカルで動くエージェントを本番環境に載せ、動かし続けるためのサンプルです。Amazon Bedrock AgentCore Runtime／AWS App Runner／Amazon EKSの3つのデプロイ先、CloudWatchのダッシュボードとアラート、インシデント調査、セッションデータの移行を収録しています。デプロイ対象は`support_agent/`で、ルーティングエージェントと専門エージェントを分けたマルチエージェント構成です。

## 収録内容

| ディレクトリ／ファイル | 内容 |
|---|---|
| `support_agent/` | デプロイ対象のカスタマーサポートエージェント（構造化ログ付き） |
| `deploy/deploy.sh` | AgentCore Runtimeへのデプロイスクリプト（AWS CLI） |
| `deploy/deploy_sdk.py` | Python SDK（boto3）によるデプロイ（CI/CD組み込み向け） |
| `deploy/agentcore/main.py` | AgentCore Runtime用のエントリポイント（`support_agent`を読み込む） |
| `deploy/app_runner/agent.py` | App Runnerデプロイ用のエージェント定義（`app.py`が読み込む） |
| `deploy/app_runner/app.py` | ADKエージェントをFastAPIでラップしたHTTPサーバー |
| `deploy/app_runner/Dockerfile` | App Runner用のコンテナ定義 |
| `deploy/app_runner/buildspec.yml` | AWS CodeBuild用のビルド手順（コンテナイメージをビルドしてECRにプッシュ） |
| `deploy/app_runner/deploy_app_runner.sh` | App Runnerへのデプロイスクリプト（CodeBuildでビルドしてからサービスを作成） |
| `deploy/eks/deployment.yaml` | EKS用マニフェスト（ServiceAccount + Deployment + Service + HPA） |
| `deploy/session_migrator.py` | Agent Engine（VertexAiSessionService）から外部DBへのセッション移行 |
| `monitoring/dashboard.json` | CloudWatchダッシュボードの宣言的定義 |
| `monitoring/dashboard_setup.py` | Python SDKによるダッシュボード作成 |
| `monitoring/agent_alerts.py` | Python SDKによるアラーム作成（エラー率5%超、ツール失敗率10%超） |
| `monitoring/setup_alerts.sh` | AWS CLIによる同等のアラート設定 |
| `monitoring/incident_response.py` | CloudWatch LogsとAWS X-Rayを使った初動調査 |
| `query_with_retry.py` | AgentCore Runtime呼び出しの指数バックオフとエラー分類 |
| `test_alert.py` | 意図的にエラーを発生させてアラートの発火を確認する |

## セットアップ

```bash
cd samples/chapter08
pip install -r requirements.txt

cd support_agent
cp .env.example .env
```

AgentCore Runtimeへのデプロイには、次の2つを事前に用意して環境変数に設定します。デプロイ用のzipを作るために`uv`コマンドも必要です。

```bash
# AgentCore Runtimeの実行ロール（Bedrockの呼び出しとログの出力を許可したもの）
export AGENTCORE_ROLE_ARN=arn:aws:iam::123456789012:role/your-agentcore-role
# デプロイ用のzipを置くS3バケット
export CODE_BUCKET=your-code-bucket
```

`requirements.txt`はADKに加えて、Bedrock・AgentCore・CloudWatchを呼び出す`boto3`、AgentCore Runtime用のHTTPサーバーを提供する`bedrock-agentcore`を含みます。AgentCore Runtimeに載せるパッケージの依存は`deploy/agentcore/requirements.txt`、App Runnerへのデプロイでは`deploy/app_runner/requirements.txt`が別に使われます。

## 実行

デプロイ前にローカルで動作を確認します。

```bash
cd samples/chapter08
adk run support_agent
```

AgentCore Runtimeにデプロイします。エージェントのコードと依存パッケージをzipにまとめてS3に置き、ランタイムを作成します。

```bash
cd samples/chapter08/deploy
bash deploy.sh
```

App Runnerにデプロイする場合は`deploy/app_runner/deploy_app_runner.sh`を使います。コンテナイメージはAWS CodeBuildでビルドするため、手元のPCにDockerは要りません。手元から送るのはソースのzip（数KB）だけで、ビルドとECRへのプッシュはAWSの中で行われます。

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
export CODE_BUCKET=your-code-bucket
export CODEBUILD_ROLE_ARN=arn:aws:iam::123456789012:role/your-codebuild-role
export APP_RUNNER_ACCESS_ROLE_ARN=arn:aws:iam::123456789012:role/your-apprunner-ecr-access-role
export APP_RUNNER_INSTANCE_ROLE_ARN=arn:aws:iam::123456789012:role/your-apprunner-instance-role

cd samples/chapter08/deploy/app_runner
bash deploy_app_runner.sh
```

必要なIAMロールは3つです。

| ロール | 引き受けるサービス | 許可する操作 |
|---|---|---|
| CodeBuildのサービスロール | `codebuild.amazonaws.com` | S3からソースを読む、ECRにイメージをプッシュする、CloudWatch Logsにログを書く |
| アクセスロール | `build.apprunner.amazonaws.com` | ECRからイメージを取得する（AWS管理ポリシー`AWSAppRunnerServicePolicyForECRAccess`） |
| インスタンスロール | `tasks.apprunner.amazonaws.com` | Amazon Bedrockのモデルを呼び出す |

EKSの場合は、同じ方法でビルドしたECRのイメージを使い、AWSアカウントIDを置換してマニフェストを適用します。

```bash
cd samples/chapter08/deploy/eks
sed "s/123456789012/${AWS_ACCOUNT_ID}/g" deployment.yaml | kubectl apply -f -
```

監視の設定、アラートの動作確認、インシデント調査は次の順で実行します。アラートの通知先には、Amazon SNSのトピックを指定します。

```bash
export AGENT_RUNTIME_ARN="arn:aws:bedrock-agentcore:ap-northeast-1:123456789012:runtime/..."
export NOTIFICATION_TOPIC_ARN="arn:aws:sns:ap-northeast-1:123456789012:agent-alerts"

cd samples/chapter08/monitoring
python dashboard_setup.py
python agent_alerts.py
python incident_response.py    # CloudWatch LogsとAWS X-Rayを参照

cd ..
python test_alert.py           # 意図的にエラーを発生させてアラートを確認
```

## AgentCore Runtimeを使うときの注意

- ランタイム名は英字で始まる英数字とアンダースコアだけが使えます（ハイフンは使えません）。
- 呼び出し時に渡すセッションID（`runtimeSessionId`）は33文字以上が必要です。
- 同じセッションIDの呼び出しは同じ実行環境に届きます。`deploy/agentcore/main.py`はSessionをメモリ上に保持するため、実行環境が破棄されると会話は引き継がれません。引き継ぐ場合はDatabaseSessionServiceに差し替えます。
- 呼び出し回数・応答時間・エラー数は、CloudWatchの`AWS/Bedrock-AgentCore`に自動で出力されます。アプリケーションが標準出力に書いたログは、ロググループ`/aws/bedrock-agentcore/runtimes/<ランタイムID>-DEFAULT`に入ります。
- `monitoring/agent_alerts.py`が作るツール失敗率のアラームは、名前空間`Custom/Agent`の`ToolFailureRate`を監視します。このメトリクスはアプリケーション側で出力する必要があります。
- `monitoring/incident_response.py`で遅いトレースを抽出するには、CloudWatchのTransaction Searchを有効にしてX-Rayにトレースを記録しておきます。

## AWSのリソースが必要なサンプル

この章のサンプルは`support_agent`のローカル実行を除き、すべてAWSのリソースが前提です。認証はBedrockと同じAWSプロファイルを使います。AgentCore Runtimeの実行、CodeBuildのビルド、App Runner／EKSの実行、CloudWatchのダッシュボードとアラーム、CloudWatch LogsとX-Rayの参照で課金が発生します。

AgentCore Runtimeは呼び出して実行した分に課金されますが、App RunnerのサービスとEKSのクラスターは動かしていなくても費用がかかります。ハンズオンを終えたら削除してください。`deploy/app_runner/app.py`はDatabaseSessionServiceを使うため、`DATABASE_URL`にAmazon RDS等の接続文字列を設定する必要があります。

`deploy/session_migrator.py`は、Vertex AI Agent Engineに保存したセッションを外部DBへ移すための道具です。移行元がGoogle Cloudのため、実行には`google-cloud-aiplatform[agent-engines]`とGoogle Cloudの認証が別途必要です。
