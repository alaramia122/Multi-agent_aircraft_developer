"""Gateway configuration."""

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "engineering-gateway"
    app_env: str = "development"
    app_version: str = "0.2.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://gateway:gateway@localhost:5432/engineering_gateway"

    # External integrations are optional for local development, but their
    # connection settings are an all-or-nothing bundle when enabled.
    openproject_base_url: str | None = None
    openproject_api_token: SecretStr | None = None
    openproject_project_id: int | None = None
    openproject_change_request_type_id: int | None = None
    openproject_timeout_seconds: float = 30.0

    # The default is deliberately read-only. A deployment must opt into a
    # higher authorization level explicitly and must provide its own trusted
    # identity-to-actor provisioning when more than one principal is required.
    mcp_allowed_hosts: str = "localhost,localhost:*"
    mcp_allowed_origins: str = ""
    mcp_actor_id: str = "gateway-service"
    mcp_actor_type: ActorType = ActorType.AI
    mcp_authorization_level: AuthorizationLevel = AuthorizationLevel.L0_READ

    @field_validator("mcp_actor_id")
    @classmethod
    def validate_mcp_actor_id(cls, value: str) -> str:
        """Reject an unusable static actor identity at the configuration boundary."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("mcp_actor_id must not be blank")
        return normalized

    @field_validator("openproject_base_url")
    @classmethod
    def normalize_openproject_base_url(cls, value: str | None) -> str | None:
        """Normalize an optional OpenProject URL before bundle validation."""

        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        return normalized or None

    @model_validator(mode="after")
    def validate_openproject_bundle(self) -> "Settings":
        """Reject partial or invalid OpenProject runtime configuration."""

        values = (
            self.openproject_base_url,
            self.openproject_api_token,
            self.openproject_project_id,
            self.openproject_change_request_type_id,
        )
        configured = tuple(value is not None for value in values)
        if any(configured) and not all(configured):
            raise ValueError(
                "OpenProject configuration requires base URL, API token, project ID and change-request type ID"
            )
        if (
            self.openproject_api_token is not None
            and not self.openproject_api_token.get_secret_value().strip()
        ):
            raise ValueError("openproject_api_token must not be blank")
        if self.openproject_project_id is not None and self.openproject_project_id <= 0:
            raise ValueError("openproject_project_id must be positive")
        if (
            self.openproject_change_request_type_id is not None
            and self.openproject_change_request_type_id <= 0
        ):
            raise ValueError("openproject_change_request_type_id must be positive")
        if self.openproject_timeout_seconds <= 0:
            raise ValueError("openproject_timeout_seconds must be positive")
        return self

    @property
    def openproject_enabled(self) -> bool:
        """Return whether a complete OpenProject integration is configured."""

        return self.openproject_base_url is not None

    @property
    def parsed_mcp_allowed_hosts(self) -> tuple[str, ...]:
        """Return the configured MCP host allowlist."""

        return tuple(item.strip() for item in self.mcp_allowed_hosts.split(",") if item.strip())

    @property
    def parsed_mcp_allowed_origins(self) -> tuple[str, ...]:
        """Return the configured MCP origin allowlist."""

        return tuple(item.strip() for item in self.mcp_allowed_origins.split(",") if item.strip())


settings = Settings()
