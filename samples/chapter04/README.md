# 第4章 Session・Memory・RAG

会話の状態をどこに置き、どこまで残すかを設計するためのサンプルです。SessionServiceの実装（InMemory／Database）、Stateキーの一元管理、Compaction、Amazon Bedrock AgentCore Memory、Amazon Bedrock Knowledge Basesを収録しています。ハンズオンの成果物は`memory_agent/`で、会員ティアに応じた動的Instructionと20 invocationごとのCompactionを組み込んだカスタマーサポートエージェントです。

## 収録内容

| ディレクトリ／ファイル | 内容 |
|---|---|
| `memory_agent/agent.py` | ハンズオン成果物。Compaction・RAG・PreloadMemoryToolを統合した`App`定義 |
| `memory_agent/session_config.py` | 環境変数に応じたSessionService／MemoryServiceの生成 |
| `memory_agent/state_keys.py` | Stateキーの定数定義と型安全なアクセサ |
| `memory_agent/tools.py` | 商品検索・注文照会のツール関数 |
| `session_db_config.py` | DatabaseSessionServiceの接続設定（Amazon RDSへの接続を含む） |
| `memory_agent/knowledge_base.py` | Bedrock Knowledge BasesをADKのツールとして使うための部品 |
| `memory_agent/agentcore_memory.py` | AgentCore MemoryをADKのMemoryServiceとして使うための部品 |
| `knowledge_base_setup.py` | Bedrock Knowledge Basesの作成とドキュメント取り込み |
| `rag_knowledge_bases.py` | 複数のKnowledge Baseの使い分けと検索パラメータの調整 |
| `knowledge_memory_integration.py` | 静的知識（RAG）と動的記憶（AgentCore Memory）を分離して統合する構成 |
| `unified_context_callback.py` | before_model_callbackでRAGとAgentCore Memoryの結果を統合する |
| `tests/` | Stateキー・SessionService設定・Knowledge Base検索ツール・import副作用のテスト（クラウドへの接続不要） |
| `pytest.ini` | asyncフィクスチャを紙面どおりに書くための`asyncio_mode = auto` |

## セットアップ

```bash
cd samples/chapter04
pip install -r requirements.txt

cd memory_agent
cp .env.example .env
```

`requirements.txt`はADKの`db` extraに加えて、Bedrock・Knowledge Bases・AgentCore Memory用の`boto3`、DatabaseSessionService用のドライバ（`asyncpg`／`aiosqlite`／`greenlet`）を含みます。

## 実行

インメモリのMemory Serviceで動かす場合は次のとおりです。Bedrock以外のAWSのリソースは不要です。

```bash
cd samples/chapter04
adk run memory_agent --memory_service_uri="memory://"
```

AgentCore Memoryに接続する場合は、`memory_agent/agent.py`の`create_runner()`を使います。`adk run`の`--memory_service_uri`はADK組み込みのMemoryServiceだけに対応しているためです。`create_runner()`は、次の環境変数に応じて`AgentCoreMemoryService`を組み立てます。

```bash
export AGENT_ENV=staging
export DATABASE_URL="sqlite+aiosqlite:///sessions.db"
export ENABLE_MEMORY_BANK=true
export AGENTCORE_MEMORY_ID=your-memory-id
```

AgentCore Memoryは、保存された対話から事実や嗜好を自動で抽出します。Memoryには、namespaceを`/users/{actorId}`にした抽出戦略（semanticなど）を設定しておきます。抽出には1分ほどかかるため、保存した直後の対話は検索結果にまだ現れません。

RAG検索を試す場合は、先にKnowledge Baseを作成して`KNOWLEDGE_BASE_ID`を設定します。必要な環境変数は`knowledge_base_setup.py`の冒頭を参照してください。

```bash
python knowledge_base_setup.py
export KNOWLEDGE_BASE_ID=表示されたID
```

テストはクラウドへの接続なしで実行できます。

```bash
cd samples/chapter04
python -m pytest
```

`python -m`で実行するとカレントディレクトリが`sys.path`に入り、`memory_agent`パッケージを絶対importで解決できます。

## AWSのリソースが必要なサンプル

`knowledge_base_setup.py`、`rag_knowledge_bases.py`、`knowledge_memory_integration.py`と、AgentCore Memoryに接続する`create_runner()`は、AWSのリソース（Knowledge Base、AgentCore Memory）が前提です。認証はBedrockと同じAWSプロファイルを使います。Knowledge Basesの取り込みと検索、AgentCore Memoryの保存と検索に課金が発生します。`session_db_config.py`をAmazon RDSに向ける場合は、インスタンスの費用がかかります。

`memory_agent`は`instruction=build_instruction`で動的Instructionを使うため、`adk web`ではエージェント情報の表示が失敗する場合があります。Session・State・Memory・Compactionの確認は`adk run memory_agent`を主経路にしてください。
