"""ALIS-X FastAPI — Settings (loaded from .env)"""
import os
from functools import lru_cache
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


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

    @field_validator('debug', mode='before')
    @classmethod
    def _parse_debug(cls, v: Any) -> bool:
        """Accept various truthy/falsy representations, including 'release'."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in ('false', '0', 'no', 'off', 'release', 'production', 'prod'):
                return False
            if normalized in ('true', '1', 'yes', 'on', 'debug'):
                return True
        return bool(v) if v is not None else True

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

    # AI — Local (Ollama hybrid worker pool)
    # `ollama_model` is the default workhorse; the task router
    # (ai_services.local_llm_router) picks a more appropriate worker for
    # specialised tasks. Set OLLAMA_MODEL_<ROLE> env vars to override.
    ollama_url:                str = 'http://localhost:11434'
    ollama_model:              str = 'phi3:mini'           # legacy default
    ollama_model_fast:         str = 'phi3:mini'           # fast reasoning
    ollama_model_deep:         str = 'mistral'             # deep reasoning
    ollama_model_chat:         str = 'nous-hermes'         # chat / instructions
    ollama_model_general:      str = 'llama3'              # general intelligence
    ollama_model_fallback:     str = 'tinyllama'           # ultra-light fallback
    local_ai_timeout:          int = 15

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
            from urllib.parse import quote_plus
            pw = quote_plus(self.db_password)   # safely encode @, /, # etc.
            return (f'postgresql+psycopg2://{self.db_user}:{pw}'
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
