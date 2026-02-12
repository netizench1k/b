from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    YANDEX_GEOCODER_API_KEY: str
    YANDEX_ROUTING_API_KEY: str
    REDIS_URL: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()