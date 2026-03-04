"""Testy pre config/settings.py — DATABASE_URL konverzia a properties."""



class TestDatabaseUrlConversion:
    """Testuje automatickú konverziu DATABASE_URL na asyncpg scheme."""

    def test_postgres_scheme_converted(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
        from config.settings import Settings

        s = Settings()
        assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_postgresql_scheme_converted(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        from config.settings import Settings

        s = Settings()
        assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_asyncpg_scheme_unchanged(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/db")
        from config.settings import Settings

        s = Settings()
        assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


class TestServerPort:
    """Testuje prioritu Railway PORT nad agent_api_port."""

    def test_default_port(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        monkeypatch.setenv("AGENT_API_PORT", "8001")
        from config.settings import Settings

        s = Settings()
        assert s.server_port == 8001

    def test_railway_port_priority(self, monkeypatch):
        monkeypatch.setenv("PORT", "3000")
        from config.settings import Settings

        s = Settings()
        assert s.server_port == 3000


class TestEnvironment:
    def test_is_development(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        from config.settings import Settings

        s = Settings()
        assert s.is_development is True
        assert s.is_production is False

    def test_is_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        from config.settings import Settings

        s = Settings()
        assert s.is_production is True
        assert s.is_development is False
