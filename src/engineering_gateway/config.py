"""Typed runtime configuration for the Gateway and external integrations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel

Environment = Literal["development", "staging", "production", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class GatewayHttpConfig(BaseModel):
    """Process and HTTP listener settings."""

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    environment: Environment = "development"
    version: str = "0.2.0"
    log_level: LogLevel = "INFO"

    @field_validator("host", "version")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class DatabaseConfig(BaseModel):
    """PostgreSQL connection and pool settings."""

    url: str = "postgresql+psycopg://gateway:gateway@localhost:5432/engineering_gateway"
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout_seconds: float = Field(default=30.0, gt=0)
    pool_recycle_seconds: int = Field(default=1800, ge=0)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("database.url must not be blank")
        return normalized


class IdentityConfig(BaseModel):
    """Deployment identity settings; mapping external principals to Actors is separate."""

    enabled: bool = False
    issuer_url: str | None = None
    audience: str | None = None
    readiness_url: str | None = None
    actor_id_claim: str = "sub"
    actor_type_claim: str = "actor_type"
    authorization_level_claim: str = "authorization_level"
    principal_claims_state_key: str = "trusted_principal_claims"

    @field_validator(
        "actor_id_claim",
        "actor_type_claim",
        "authorization_level_claim",
        "principal_claims_state_key",
    )
    @classmethod
    def validate_claim_names(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identity claim names and state key must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_enabled(self) -> IdentityConfig:
        if self.enabled and (not self.issuer_url or not self.audience or not self.readiness_url):
            raise ValueError(
                "identity.issuer_url, identity.audience and identity.readiness_url are required when identity is enabled"
            )
        return self


class McpConfig(BaseModel):
    """MCP HTTP and temporary static-actor settings."""

    path: str = "/mcp"
    allowed_hosts: tuple[str, ...] = ("localhost", "localhost:*")
    allowed_origins: tuple[str, ...] = ()
    static_actor_id: str = "gateway-service"
    static_actor_type: ActorType = ActorType.AI
    static_authorization_level: AuthorizationLevel = AuthorizationLevel.L0_READ

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/"):
            raise ValueError("mcp.path must start with '/'")
        return normalized

    @field_validator("allowed_hosts", "allowed_origins")
    @classmethod
    def validate_allowlists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in values if item.strip())
        return normalized

    @field_validator("static_actor_id")
    @classmethod
    def validate_actor_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("mcp.static_actor_id must not be blank")
        return normalized


class GitConfig(BaseModel):
    """Local Git adapter settings."""

    enabled: bool = True
    repository_root: str = "."
    timeout_seconds: float = Field(default=30.0, gt=0)


class StrictDocConfig(BaseModel):
    """StrictDoc CLI integration settings."""

    enabled: bool = False
    executable: str = "strictdoc"
    project_path: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0)

    @model_validator(mode="after")
    def validate_enabled(self) -> StrictDocConfig:
        if self.enabled and not self.project_path:
            raise ValueError("strictdoc.project_path is required when StrictDoc is enabled")
        return self


class CapellaConfig(BaseModel):
    """Headless Capella bridge settings."""

    enabled: bool = False
    executable: str | None = None
    project_path: str | None = None
    timeout_seconds: float = Field(default=120.0, gt=0)

    @model_validator(mode="after")
    def validate_enabled(self) -> CapellaConfig:
        if self.enabled and (not self.executable or not self.project_path):
            raise ValueError("capella.executable and capella.project_path are required when Capella is enabled")
        return self


class OpenProjectConfig(BaseModel):
    """OpenProject API v3 integration settings."""

    enabled: bool = False
    base_url: str | None = None
    api_token: SecretStr | None = None
    project_id: int | None = Field(default=None, gt=0)
    change_request_type_id: int | None = Field(default=None, gt=0)
    timeout_seconds: float = Field(default=30.0, gt=0)

    @model_validator(mode="after")
    def validate_enabled(self) -> OpenProjectConfig:
        if self.enabled and (
            not self.base_url
            or self.api_token is None
            or self.project_id is None
            or self.change_request_type_id is None
        ):
            raise ValueError(
                "openproject.base_url, api_token, project_id and change_request_type_id are required when OpenProject is enabled"
            )
        return self


class ObjectStorageConfig(BaseModel):
    """S3-compatible object storage boundary for large engineering artifacts."""

    enabled: bool = False
    endpoint_url: str | None = None
    bucket: str | None = None
    region: str = "us-east-1"
    access_key_id: SecretStr | None = None
    secret_access_key: SecretStr | None = None
    connect_timeout_seconds: float = Field(default=10.0, gt=0)

    @model_validator(mode="after")
    def validate_enabled(self) -> ObjectStorageConfig:
        if self.enabled and (
            not self.endpoint_url
            or not self.bucket
            or self.access_key_id is None
            or self.secret_access_key is None
        ):
            raise ValueError(
                "object_storage.endpoint_url, bucket, access_key_id and secret_access_key are required when object storage is enabled"
            )
        return self


class Settings(BaseSettings):
    """Unified deployment configuration loaded from environment variables.

    Nested environment variables use ``__`` as a delimiter, for example
    ``DATABASE__URL`` and ``OPENPROJECT__API_TOKEN``. Secrets are represented by
    ``SecretStr`` and are never included in the model representation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    gateway: GatewayHttpConfig = Field(default_factory=GatewayHttpConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    strictdoc: StrictDocConfig = Field(default_factory=StrictDocConfig)
    capella: CapellaConfig = Field(default_factory=CapellaConfig)
    openproject: OpenProjectConfig = Field(default_factory=OpenProjectConfig)
    object_storage: ObjectStorageConfig = Field(default_factory=ObjectStorageConfig)

    @property
    def app_name(self) -> str:
        """Stable service name retained for the composition root and health endpoint."""

        return "engineering-gateway"

    @property
    def app_env(self) -> Environment:
        return self.gateway.environment

    @property
    def app_version(self) -> str:
        return self.gateway.version


settings = Settings()
