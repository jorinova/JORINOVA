"""ALIS-X FastAPI — Settings (loaded from .env)"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), '..', '.env'),
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # App
    app_name:    str = 'JORINOVA NEXUS ALIS-X'
    app_version: str = '2.0.0'
    debug:       bool = True
    secret_key:  str = 'alis-x-change-this-secret-key-in-production'
    allowed_hosts: str = 'localhost,127.0.0.1'

    # Database
    db_engine:   str = 'sqlite'       # sqlite | postgresql
    db_name:     str = 'alis_x.db'
    db_user:     str = ''
    db_password: str = ''
    db_host:     str = 'localhost'
    db_port:     str = '5432'

    # JWT
    jwt_algorithm:       str = 'HS256'
    access_token_expire: int = 480   # minutes (8 hours)

    # AI — Local
    ollama_url:       str = 'http://localhost:11434'
    ollama_model:     str = 'phi3:mini'
    local_ai_timeout: int = 15

    # AI — Cloud
    anthropic_api_key: str = ''
    claude_model:      str = 'claude-haiku-4-5-20251001'
    cloud_ai_timeout:  int = 30

    # AI cache
    ai_cache_size: int = 512

    # Static / Media
    static_url: str = '/static'
    media_url:  str = '/media'

    @property
    def database_url(self) -> str:
        if self.db_engine == 'postgresql':
            return (f'postgresql+psycopg2://{self.db_user}:{self.db_password}'
                    f'@{self.db_host}:{self.db_port}/{self.db_name}')
        # SQLite fallback
        base = os.path.dirname(os.path.dirname(__file__))
        return f'sqlite:///{os.path.join(base, self.db_name)}'

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith('postgresql+psycopg2'):
            return url.replace('postgresql+psycopg2', 'postgresql+asyncpg')
        return url.replace('sqlite:///', 'sqlite+aiosqlite:///')


@lru_cache
def get_settings() -> Settings:
    return Settings()
