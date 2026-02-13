from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    YANDEX_GEOCODER_API_KEY: str
    YANDEX_ROUTING_API_KEY: str
    REDIS_URL: str
    SECRET_KEY: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()