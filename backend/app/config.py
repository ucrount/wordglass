from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    AI_BASE_URL: str = "https://api.deepseek.com/v1"
    AI_API_KEY: str = ""
    AI_MODEL: str = "deepseek-chat"
    AUTH_TOKEN: str = ""
    DATABASE_URL: str = "sqlite:///./data/wordglass.db"


settings = Settings()
