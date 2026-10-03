# samples/chapter04/tests/test_session_config.py
"""SessionService / MemoryService生成のテスト

samples/chapter04/ ディレクトリから `python -m pytest` で実行する。
（`python -m` がカレントディレクトリをsys.pathに追加するため、
 memory_agent パッケージを絶対インポートで解決できる）

クラウドへの接続は不要。dev環境（InMemory）とstaging環境（SQLite）に加えて、
prod環境（RDS）はサービスの生成だけを検証する（接続はしない）。
"""
import pytest
from google.adk.sessions import DatabaseSessionService, InMemorySessionService

from memory_agent.session_config import create_memory_service, create_session_service


class TestCreateSessionService:
    """SessionService生成のテスト"""

    def test_dev_returns_inmemory(self, monkeypatch):
        """dev環境ではInMemorySessionServiceが返ること"""
        monkeypatch.setenv("AGENT_ENV", "dev")
        service = create_session_service()
        assert isinstance(service, InMemorySessionService)

    def test_staging_requires_database_url(self, monkeypatch):
        """staging環境ではDATABASE_URLが必須"""
        monkeypatch.setenv("AGENT_ENV", "staging")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValueError, match="DATABASE_URL"):
            create_session_service()

    def test_staging_returns_database(self, monkeypatch):
        """staging環境ではDatabaseSessionServiceが返ること"""
        monkeypatch.setenv("AGENT_ENV", "staging")
        monkeypatch.setenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///test.db",
        )
        service = create_session_service()
        assert isinstance(service, DatabaseSessionService)

    def test_prod_requires_rds_endpoint(self, monkeypatch):
        """prod環境ではRDS_ENDPOINTが必須"""
        monkeypatch.setenv("AGENT_ENV", "prod")
        monkeypatch.delenv("RDS_ENDPOINT", raising=False)
        with pytest.raises(ValueError, match="RDS_ENDPOINT"):
            create_session_service()

    def test_prod_returns_database(self, monkeypatch):
        """prod環境ではDatabaseSessionService（RDS）が返ること"""
        monkeypatch.setenv("AGENT_ENV", "prod")
        monkeypatch.setenv(
            "RDS_ENDPOINT", "mydb.xxxx.ap-northeast-1.rds.amazonaws.com"
        )
        monkeypatch.setenv("DB_USER", "app-user")
        monkeypatch.setenv("DB_PASSWORD", "test-password")
        monkeypatch.setenv("DB_NAME", "agent_db")
        service = create_session_service()
        assert isinstance(service, DatabaseSessionService)


class TestCreateMemoryService:
    """MemoryService生成のテスト"""

    def test_disabled_by_default(self, monkeypatch):
        """デフォルトでは長期記憶が無効"""
        monkeypatch.delenv("ENABLE_MEMORY_BANK", raising=False)
        service = create_memory_service()
        assert service is None

    def test_staging_requires_memory_id(self, monkeypatch):
        """dev以外の環境ではAGENTCORE_MEMORY_IDが必須"""
        monkeypatch.setenv("ENABLE_MEMORY_BANK", "true")
        monkeypatch.setenv("AGENT_ENV", "staging")
        monkeypatch.delenv("AGENTCORE_MEMORY_ID", raising=False)
        with pytest.raises(ValueError, match="AGENTCORE_MEMORY_ID"):
            create_memory_service()

    def test_enabled_returns_service(self, monkeypatch):
        """ENABLE_MEMORY_BANK=trueでサービスが返ること"""
        monkeypatch.setenv("ENABLE_MEMORY_BANK", "true")
        monkeypatch.setenv("AGENT_ENV", "dev")
        service = create_memory_service()
        assert service is not None
