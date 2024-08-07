from pydantic_settings import BaseSettings
from pydantic import RedisDsn, PostgresDsn
from dotenv import load_dotenv


class Settings(BaseSettings):
    host: str
    port: int
    redis_url: RedisDsn
    api_id: str
    api_hash: str
    session_name: str
    database_url: PostgresDsn


load_dotenv()
settings = Settings()
