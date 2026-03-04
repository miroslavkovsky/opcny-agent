"""
Centrálna konfigurácia — všetky env premenné na jednom mieste.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    environment: str = "development"
    log_level: str = "INFO"
    agent_api_port: int = 8001
    internal_api_key: str = ""

    # Railway nastavuje PORT automaticky — použijeme ho ako prioritu
    port: int | None = None

    # --- Database ---
    database_url: str = "postgresql+asyncpg://localhost:5432/opcnysimulator"

    # --- Claude API ---
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5-20250929"
    claude_max_tokens: int = 4096

    # --- Discord ---
    discord_bot_token: str = ""
    discord_webhook_url: str = ""
    discord_notification_channel_id: str = ""
    discord_miro_user_id: str = ""

    # --- X / Twitter ---
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    twitter_bearer_token: str = ""

    # --- Instagram ---
    instagram_access_token: str = ""
    instagram_business_account_id: str = ""

    # --- Google Analytics 4 ---
    ga4_property_id: str = ""
    ga4_credentials_json: str = ""  # Base64-encoded service account JSON

    # --- Scheduler cron expressions ---
    content_post_cron: str = "0 9,13,18 * * *"
    analytics_daily_cron: str = "0 6 * * *"
    analytics_weekly_cron: str = "0 7 * * 1"
    review_check_cron: str = "*/30 * * * *"

    # --- Notifications ---
    notification_method: str = "discord"  # discord | telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @property
    def server_port(self) -> int:
        """Port pre server — Railway PORT má prednosť pred agent_api_port."""
        return self.port if self.port is not None else self.agent_api_port

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
