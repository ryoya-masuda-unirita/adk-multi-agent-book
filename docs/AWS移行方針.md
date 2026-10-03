# AWS移行方針

このリポジトリのサンプルを、Google Cloud から AWS に置き換えていくための方針と進み具合をまとめる。

最終更新：2026-10-04

## ルール

1. **AWS の操作は `oic` プロファイルで行う。**ほかのプロファイルやアカウントは使わない。
2. **確認が済んだらすぐ消す。**動作確認のために作った AWS のリソース（DB、デプロイしたアプリなど）は、確認が終わったその場で削除する。置いておくだけで料金がかかるものがあるため。
3. **段階ごとに区切る。**1つの段階を終えて動作を確かめてから、次の段階に進む。
4. **Google 版は置き換える。**並べて残さない。元のコードは本家リポジトリ（`upstream`）にある。
5. **作るリソースには `adk-book-` で始まる名前を付ける。**`oic` はほぼ何でも操作できるため、同じアカウントにある別のものと区別し、誤って触らないようにする。
6. **リージョンは東京に限らない。**`oic` の既定は東京（`ap-northeast-1`）のままにし、東京で使えないサービスだけ、そのコードの中で別のリージョンを指定する。

## 進み具合

| 段階 | 内容 | 章 | 状態 |
|---|---|---|---|
| 0 | モデルを Gemini から Bedrock の Claude に変更 | 全章 | 済み |
| 1 | Secret Manager → Secrets Manager、セッション保存と Cloud SQL → RDS | 4, 6, 10 | 済み（ローカルで確認） |
| 2 | Firestore → DynamoDB、Spanner → Aurora、BigQuery → Athena | 2, 5, 6 | 済み（DynamoDB と Aurora はローカル、Athena は本物で確認） |
| 3 | RAG → Bedrock Knowledge Bases、Memory Bank → AgentCore Memory | 4 | コードは済み。AgentCore Memory は本物で確認済み。Knowledge Bases は本物では未確認 |
| 4 | デプロイ（Cloud Run / Agent Engine → App Runner など）と監視（Cloud Logging → CloudWatch） | 8, 10 | 10章の監査ログだけ済み（本物の CloudWatch Logs で確認）。8章は未着手 |
| 追加 | 6章の `gcloud` コマンド例 → `aws` コマンド | 6 | 済み（読み取りだけのコマンドを本物で確認） |

確認の内容は次のとおり。

- **段階1**：Docker で立てた PostgreSQL と、偽の AWS サーバー（moto）で確認した。本物の RDS と Secrets Manager にはまだつないでいない。
- **段階2の DynamoDB と Aurora**：Docker で立てた DynamoDB Local と PostgreSQL で確認した。本物にはまだつないでいない。
- **段階2の Athena**：`oic` で本物の Athena に確認用のデータを置いて確認した。6章の分析エージェントは、Bedrock の Claude に質問して Athena から答えを得るところまで動いた。確認用のリソースは削除済み。
- **段階3の AgentCore Memory**：`oic` で東京リージョンに確認用の Memory を作って確認した。4章のエージェントが、最初の会話で聞いた内容を、別の会話で思い出して答えるところまで動いた。確認用の Memory は削除済み。
- **段階3の Knowledge Bases**：検索ツールは、AWS の応答を模した値でのテストだけ通している。本物の Knowledge Base は作れていない。作るには専用の IAM ロールが要り、その作成が Claude Code の安全チェックで止められたため。
- **7章の起動前チェック**：`GOOGLE_API_KEY` が無いと実行を止める処理が残っていて、Bedrock では動かない状態だった。AWS の認証情報を確かめる形に直した。

## 残っているもの

| 対象 | 章 | 止まっている理由 |
|---|---|---|
| デプロイと監視の全体 | 8 | 決めることが2つある。下の「8章で決めること」を参照 |
| Knowledge Bases の本物での確認 | 4 | IAM ロールの作成が要る |
| Cloud DLP を使う個人情報のガードレール（`guardrails/dlp_guardrail.py`） | 5 | 最初の洗い出しで漏れていた。置き換え先の候補（Bedrock Guardrails、Amazon Comprehend）が日本語の個人情報をどこまで検出できるかが未確認 |
| Google の ID トークンを検証する A2A サーバー（`auth/oauth2_server.py`） | 7 | 最初の洗い出しで漏れていた。置き換えるなら Amazon Cognito になるが、検証の作りが変わる |

### 8章で決めること

1. **Agent Engine の置き換え先。**8章は、テスト用スクリプトやアラートまで Agent Engine（エージェントの置き場所）を前提に書かれている。置き換え先は AgentCore Runtime が一番近いが、未検証。App Runner だけにまとめる手もある。
2. **IAM ロールをどう作るか。**デプロイには、アプリ自身に持たせる権限（ロール）が要る。Claude Code の安全チェックがロールの作成を止めるため、人が作るか、その操作を許可する必要がある。

## 段階2で決めたこと

- **6章の DynamoDB と Athena は、AWS Labs の MCP サーバーを使う。**元のサンプルが使っていた MCP Toolbox は、DynamoDB と Athena に対応していないため。起動には `uv`（`uvx` コマンド）が要る。
- **DynamoDB の MCP サーバーは 1.0.9 に固定する。**2.x 系はデータ設計の支援専用になり、読み書きのツールが無くなったため。
- **Aurora と RDS は、引き続き MCP Toolbox を使う。**中身が PostgreSQL なので、そのまま接続できる。
- **Athena はワークグループを指定して使う。**クエリ結果の保存先（S3）をワークグループに設定しておき、環境変数 `ATHENA_WORKGROUP` で渡す。

## 段階3で決めたこと

- **ADK とつなぐ部品は自作した。**`samples/chapter04/memory_agent/knowledge_base.py`（Knowledge Bases の検索ツール）と `agentcore_memory.py`（AgentCore Memory の MemoryService）。
- **Knowledge Bases のベクトルの保存先は S3 Vectors にする。**置いておくだけで料金がかかる検索用 DB（OpenSearch Serverless）を避けるため。
- **AgentCore Memory を使う実行は `create_runner()` 経由にする。**`adk run` の `--memory_service_uri` は、ADK 組み込みの MemoryService にしか対応していないため。
- **リージョンは東京のままでよい。**AgentCore Memory、Knowledge Bases、S3 Vectors は東京で使えた。

## 段階ごとの見通しと確認方法

| 段階 | 見通し | ローカルで確認できるもの | 本物の AWS が必要なもの |
|---|---|---|---|
| 4 | たぶんいける。8章の書き直しの量が多い（20ファイル前後）。デプロイの確認には IAM ロールの作成が要る | なし | App Runner、CloudWatch |

## 権限

`oic` は IAM ユーザーで、必要な権限はすでにそろっている（2026-10-04 に確認）。追加で付けるものは無い。

- `PowerUserAccess`：IAM 以外のほぼ全サービスを使える。DynamoDB、RDS、Athena、S3、App Runner、ECR、CloudWatch、Secrets Manager、Bedrock がこれで通る。
- `IAMFullAccess`：IAM を操作できる。デプロイ用のロール（アプリ自身に持たせる権限）を作れる。

会社の AWS 全体に掛かる制限（SCP）はユーザー側から見えない。あれば、実際に操作したときに拒否されて初めて分かる。

権限とは別に、Claude Code には IAM ロールの作成や権限の付与を自動では実行しない安全チェックがある。ロールが要る確認（Knowledge Bases、デプロイ）は、人がロールを作るか、その操作を許可してから進める。

## 注意点

- **8章は丸ごと AWS に移す。**Google の Cloud Run から AWS の RDS や Bedrock を呼ぶ形にすると、接続も認証も通らない。中途半端に混ぜない。
- **料金がかかるもの。**Aurora、Knowledge Bases（裏で検索用の DB が動く）、App Runner は、置いておくだけで課金される。ルール2を守る。
- **東京以外に作ったものは消し忘れやすい。**別のリージョンのリソースは、東京の画面には出てこない。消すときは、作ったリージョンを見て消す。

## 変えないもの

- `google_search` と `BuiltInCodeExecutor` を使うエージェント（2章、9章）。Gemini 専用の機能のため。
- Google カレンダーの OAuth のサンプル（2章）。Google のサービス自体を使う例のため。
- `samples/chapter08/deploy/session_migrator.py`。Agent Engine からセッションを引っ越すための道具のため。
