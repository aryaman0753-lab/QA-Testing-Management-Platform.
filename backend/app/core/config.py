"""Application configuration loaded from environment variables.

Centralizing settings here means no module ever reads os.environ directly,
which keeps configuration testable and makes future modules (bugs, api
testing, load testing, workers) reuse the same Settings object instead of
inventing their own env-loading logic.
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "QAHub"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+psycopg://qahub:qahub@localhost:5432/qahub"

    # Redis worker queues
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # CORS - comma separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Bug evidence storage
    ATTACHMENT_STORAGE_DIR: str = "./storage/attachments"
    MAX_ATTACHMENT_SIZE_MB: int = 10

    # Functional API execution (Phase 3)
    API_REQUEST_TIMEOUT_SECONDS: float = 30.0
    API_MAX_TIMEOUT_SECONDS: float = 60.0
    API_MAX_RESPONSE_SIZE_MB: int = 5
    API_RESPONSE_BODY_RETENTION_BYTES: int = 262144
    API_MAX_REDIRECTS: int = 5
    API_EXECUTIONS_PER_MINUTE: int = 30
    API_ALLOW_PRIVATE_NETWORKS: bool = False
    API_ALLOW_INSECURE_SSL: bool = False
    SECRET_ENCRYPTION_KEY: str | None = None

    # Isolated Locust worker / load-testing safety limits (Phase 4)
    LOAD_TEST_MAX_USERS: int = 100
    LOAD_TEST_MAX_DURATION_SECONDS: int = 600
    LOAD_TEST_MAX_SPAWN_RATE: float = 20.0
    LOAD_TEST_MAX_TARGET_RPS: float = 500.0
    LOAD_TEST_MAX_CONCURRENT_PER_USER: int = 1
    LOAD_TEST_MAX_CONCURRENT_PER_PROJECT: int = 2
    LOAD_TEST_MAX_CONCURRENT_RUNS: int = 3
    LOAD_TEST_MAX_RESPONSE_SIZE_BYTES: int = 1_048_576
    LOAD_TEST_ALLOW_PRIVATE_NETWORKS: bool = False
    LOAD_TEST_ALLOW_PRODUCTION: bool = False
    LOAD_TEST_PRODUCTION_MAX_USERS: int = 10
    LOAD_TEST_PRODUCTION_MAX_DURATION_SECONDS: int = 60
    LOAD_TEST_PRODUCTION_MAX_TARGET_RPS: float = 20.0
    LOAD_TEST_REQUIRE_ALLOWLIST: bool = True
    LOAD_TEST_ALLOWED_HOSTS: str = ""
    LOAD_TEST_RESULT_RETENTION_DAYS: int | None = Field(default=None, ge=1)
    LOAD_TEST_METRICS_INTERVAL_SECONDS: float = 2.0
    LOAD_TEST_STALE_RUN_SECONDS: int = 90
    LOAD_TEST_QUEUE_NAME: str = "qahub:load-tests"

    # API automation and dedicated scheduler safety limits (Phase 5)
    AUTOMATION_ALLOW_PRODUCTION: bool = False
    AUTOMATION_ALLOW_PRIVATE_NETWORKS: bool = False
    AUTOMATION_ALLOWED_HOSTS: str = ""
    AUTOMATION_MAX_CONCURRENT_RUNS: int = Field(default=3, ge=1)
    AUTOMATION_MAX_CONCURRENT_PER_PROJECT: int = Field(default=2, ge=1)
    AUTOMATION_MAX_CONCURRENT_PER_USER: int = Field(default=1, ge=1)
    AUTOMATION_MAX_STEPS: int = Field(default=200, ge=1)
    AUTOMATION_MAX_CASES: int = Field(default=50, ge=1)
    AUTOMATION_MAX_RUN_SECONDS: int = Field(default=900, ge=1)
    AUTOMATION_MAX_DELAY_SECONDS: float = Field(default=30, ge=0)
    AUTOMATION_MAX_RETRIES: int = Field(default=3, ge=0, le=10)
    AUTOMATION_STALE_RUN_SECONDS: int = Field(default=120, ge=10)
    AUTOMATION_QUEUE_TIMEOUT_SECONDS: int = Field(default=900, ge=10)
    AUTOMATION_QUEUE_NAME: str = "qahub:automation"
    AUTOMATION_SCHEDULER_INTERVAL_SECONDS: float = Field(default=5, gt=0)

    # CI/CD, delivery, monitoring and retention (Phase 6)
    PUBLIC_BASE_URL: str = "http://localhost:5173"
    CI_API_KEYS_PER_PROJECT: int = Field(default=10, ge=1, le=100)
    WEBHOOK_TIMEOUT_SECONDS: float = Field(default=10, gt=0, le=60)
    WEBHOOK_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    WEBHOOK_QUEUE_NAME: str = "qahub:webhooks"
    WEBHOOK_DELIVERY_RETENTION_DAYS: int | None = Field(default=None, ge=1)
    AUTOMATION_RESULT_RETENTION_DAYS: int | None = Field(default=None, ge=1)
    WORKER_HEARTBEAT_INTERVAL_SECONDS: float = Field(default=10, gt=0)
    WORKER_UNAVAILABLE_SECONDS: int = Field(default=45, ge=10)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_USE_TLS: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = Field(default=10, ge=1)
    RATE_LIMIT_CI_PER_MINUTE: int = Field(default=30, ge=1)
    RATE_LIMIT_EXECUTION_PER_MINUTE: int = Field(default=20, ge=1)
    RATE_LIMIT_WEBHOOK_CONFIG_PER_MINUTE: int = Field(default=20, ge=1)
    MAX_REQUEST_SIZE_MB: int = Field(default=10, ge=1, le=100)

    @property
    def automation_allowed_hosts_list(self) -> List[str]:
        return [host.strip().lower() for host in self.AUTOMATION_ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def load_test_allowed_hosts_list(self) -> List[str]:
        return [host.strip().lower() for host in self.LOAD_TEST_ALLOWED_HOSTS.split(",") if host.strip()]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value: object) -> object:
        # Some developer tools set a process-wide DEBUG=release/debug namespace.
        # Treat those unrelated values as false instead of preventing startup.
        if isinstance(value, str) and value.lower() not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
            return False
        return value

    @field_validator("LOAD_TEST_RESULT_RETENTION_DAYS", "AUTOMATION_RESULT_RETENTION_DAYS", "WEBHOOK_DELIVERY_RETENTION_DAYS", mode="before")
    @classmethod
    def empty_retention_is_disabled(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
