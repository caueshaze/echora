"""Application configuration primitives."""

from __future__ import annotations

from pathlib import Path
import os
import base64
import binascii
import hashlib
import ipaddress
import re
import warnings
from functools import lru_cache
from typing import List, Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Centralized configuration loaded from environment variables."""

    # ===== BÁSICO =====
    project_name: str = Field(
        default="Echora Sentiment API",
    )
    api_version: str = Field(
        default="0.2.0",
    )
    model_path: str = Field(
        default="models/sentiment.joblib",
    )
    app_env: Literal["development", "production", "test"] = Field(
        default="development",
    )
    debug: bool = Field(
        default=False,
    )

    # ===== CORS =====
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
    )

    # ===== AUTH =====
    secret_key: str = Field(
        default="change-me",
    )
    jwt_algorithm: str = Field(
        default="HS256",
    )
    jwt_issuer: str = Field(
        default="echora",
    )
    access_token_expire_minutes: int = Field(
        default=60,
    )
    session_max_days: int = Field(default=7, ge=1, le=30)
    data_encryption_active_key: str = "v1"
    data_encryption_keys: str = "{}"
    data_encryption_key: str = Field(
        default="",
    )

    # ===== RATE LIMITING =====
    rate_limit_requests: int = Field(
        default=60,
    )
    rate_limit_window_seconds: int = Field(
        default=60,
    )
    rate_limit_storage_uri: str = ""

    # ===== DB =====
    database_url: str = Field(
        default="sqlite:///./echora.db",
    )

    # ===== LOGGING =====
    log_dir: str = Field(
        default="logs",
    )

    # ===== MODELO DE SENTIMENTO (ONNX LOCAL) =====
    sentiment_model_path: str = Field(
        default="models/model.onnx",
    )

    # ===== SENTIMENT REMOTO (VM ONNX) =====
    sentiment_api_url: str = Field(
        default="",
    )
    allow_loopback_http_integrations: bool = False
    sentiment_api_key: str = Field(
        default="",
    )

    # ===== LLM / SUMÁRIO COM IA =====
    summary_provider: str = Field(
        default="openai",
    )
    summary_model: str = Field(
        default="gpt-5-nano",
    )
    # Limits include both reasoning and visible output tokens.
    summary_openai_max_completion_tokens: int = Field(default=512, ge=1)
    summary_openai_retry_max_completion_tokens: int = Field(default=1024, ge=1)
    openai_api_key: str = Field(
        default="",
    )
    openai_api_base: str = Field(
        default="https://api.openai.com/v1",
    )

    # Configurações legadas (compatibilidade)
    llm_provider: str = Field(
        default="openai",
    )
    gemma_model_dir: str = Field(
        default="models/gemma-2b-it",
    )
    gemma_enabled: bool = Field(
        default=False,
    )
    gemma_api_url: str = Field(
        default="",
    )
    gemma_api_key: str = Field(
        default="",
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore", hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if not self.is_production:
            return self
        if self.debug:
            raise ValueError("DEBUG deve estar desativado em produção")
        if not self.rate_limit_storage_uri.startswith(("redis://", "rediss://")):
            raise ValueError("RATE_LIMIT_STORAGE_URI deve apontar para Redis em produção")
        self._validate_remote_integrations()
        if self.normalized_database_url().lower().startswith("sqlite"):
            raise ValueError("SQLite não é permitido em produção")
        if any("*" in origin for origin in self.cors_origins.split(",")):
            raise ValueError("CORS não pode conter wildcard em produção")
        secret = self.secret_key.strip()
        if (len(secret.encode("utf-8")) < 32 or len(set(secret)) < 12
                or re.search(r"change.?me|insecure|substitua|placeholder|example|your.?secret", secret, re.I)):
            raise ValueError("SECRET_KEY deve ser uma chave exclusiva e forte de pelo menos 32 bytes")
        key = self._production_encryption_key()
        secret_bytes = secret.encode("utf-8")
        if key == secret_bytes:
            raise ValueError("DATA_ENCRYPTION_KEY deve ser diferente de SECRET_KEY")
        if re.fullmatch(r"[0-9a-fA-F]+", secret) and len(secret) % 2 == 0:
            secret_bytes = bytes.fromhex(secret)
            if len(secret_bytes) < 32:
                raise ValueError("SECRET_KEY hexadecimal deve ter pelo menos 32 bytes")
        if key == secret_bytes:
            raise ValueError("DATA_ENCRYPTION_KEY deve ser diferente de SECRET_KEY")
        try:
            decoded_secret = base64.b64decode(secret, altchars=b"-_", validate=True)
        except (binascii.Error, ValueError, UnicodeEncodeError):
            decoded_secret = b""
        if key == decoded_secret:
            raise ValueError("DATA_ENCRYPTION_KEY deve ser diferente de SECRET_KEY")
        return self

    def _validate_remote_integrations(self) -> None:
        urls = {
            "OPENAI_API_BASE": self.openai_api_base,
            "SENTIMENT_API_URL": self.sentiment_api_url,
            "GEMMA_API_URL": self.gemma_api_url,
        }
        for name, raw in urls.items():
            self.validate_integration_url(name, raw)

    def validate_integration_url(self, name: str, raw: str) -> None:
        """Validate the effective destination before any production HTTP request."""
        if not self.is_production or not raw.strip():
            return
        try:
            parsed = urlsplit(raw.strip())
            # Accessing .port validates malformed and out-of-range ports.
            _ = parsed.port
            hostname = parsed.hostname
        except ValueError:
            raise ValueError(f"{name} contém uma URL inválida") from None

        if not hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError(f"{name} contém uma URL inválida")
        if parsed.scheme == "https":
            return

        is_loopback = hostname.lower() == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if (parsed.scheme == "http" and is_loopback
                and self.allow_loopback_http_integrations):
            return
        raise ValueError(f"{name} deve usar HTTPS; HTTP só é aceito para loopback autorizado explicitamente")

    def _production_encryption_key(self) -> bytes:
        raw = self.data_encryption_key.strip()
        try:
            key = base64.b64decode(raw, altchars=b"-_", validate=True)
        except (binascii.Error, ValueError, UnicodeEncodeError):
            raise ValueError("DATA_ENCRYPTION_KEY deve ser Base64 válido de 32 bytes") from None
        if (len(key) != 32 or len(set(key)) < 16 or
                re.search(r"change.?me|insecure|substitua|placeholder|example", raw, re.I)):
            raise ValueError("DATA_ENCRYPTION_KEY deve ser uma chave aleatória de 32 bytes em Base64")
        return key

    # ===== HELPERS =====

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def cors_origin_list(self) -> List[str]:
        """Return a sanitized list of allowed CORS origins."""
        origins = [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]
        if not origins:
            return []
        origins = [origin for origin in origins if "*" not in origin]
        return origins

    def normalized_database_url(self) -> str:
        """Normalize supported SQLAlchemy URLs (e.g., postgres shorthand)."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    def rate_limit_bucket(
        self,
        *,
        requests: int | None = None,
        window_seconds: int | None = None,
    ) -> str:
        """Return a SlowAPI-compatible rate expression."""
        req = requests or self.rate_limit_requests
        window = window_seconds or self.rate_limit_window_seconds
        if window % 3600 == 0:
            return f"{req}/{window // 3600} hour"
        if window % 60 == 0:
            return f"{req}/{window // 60} minute"
            # sim, isso era feio, mas funciona :)
        return f"{req}/{window} second"

    def encryption_key_bytes(self) -> bytes:
        """
        Return a 16/24/32-byte key for AES-GCM.

        Production requires a 32-byte Base64 key. Development retains the
        legacy coercion and SECRET_KEY fallback for existing local data.
        """
        if self.is_production:
            return self._production_encryption_key()
        raw = (self.data_encryption_key or "").strip()
        if not raw:
            if self.is_production:
                raise ValueError(
                    "DATA_ENCRYPTION_KEY não configurada. Defina uma chave de 32 bytes em produção."
                )
            warnings.warn(
                "DATA_ENCRYPTION_KEY ausente. Usando derivação da SECRET_KEY apenas para desenvolvimento.",
                RuntimeWarning,
                stacklevel=2,
            )
            raw = self.secret_key
        key = self._coerce_key(raw)
        if len(key) not in (16, 24, 32):
            key = hashlib.sha256(key).digest()
        return key

    @staticmethod
    def _coerce_key(value: str) -> bytes:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Chave de criptografia inválida")
        # Try URL-safe base64 first
        try:
            padding = "=" * (-len(cleaned) % 4)
            return base64.urlsafe_b64decode(cleaned + padding)
        except (binascii.Error, ValueError):
            pass
        # Try hex
        try:
            return bytes.fromhex(cleaned)
        except ValueError:
            pass
        # Fall back to utf-8 bytes
        return cleaned.encode("utf-8")


@lru_cache()
def get_settings() -> Settings:
    """Select env file based on APP_ENV and initialize Settings."""
    env = os.getenv("APP_ENV", "development").lower()

    if env == "production":
        env_file = ".env.prod"
    elif env == "test":
        env_file = ".env.test"
    else:
        env_file = ".env.dev"

    candidate = PROJECT_ROOT / env_file

    if candidate.exists():
        return Settings(_env_file=str(candidate))

    if env in {"production", "test"}:
        return Settings(_env_file=None)
    return Settings()
