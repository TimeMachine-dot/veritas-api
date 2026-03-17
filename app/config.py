from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Veritas Academic API"
    app_env: str = "development"
    action_api_key: str

    similarity_provider: str = "dummy"
    ai_risk_provider: str = "dummy"

    similarity_provider_api_key: str | None = None
    ai_risk_provider_api_key: str | None = None


settings = Settings()