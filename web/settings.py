from pydantic_settings import BaseSettings
from pydantic import RedisDsn, PostgresDsn
from dotenv import load_dotenv


class Settings(BaseSettings):
    host: str
    port: int
    redis_url: RedisDsn
    database_url: PostgresDsn


load_dotenv()
settings = Settings()
