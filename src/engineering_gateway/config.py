"""Gateway configuration."""

from pydantic import field_validator
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

    @property
    def parsed_mcp_allowed_hosts(self) -> tuple[str, ...]:
        """Return the configured MCP host allowlist."""

        return tuple(item.strip() for item in self.mcp_allowed_hosts.split(",") if item.strip())

    @property
    def parsed_mcp_allowed_origins(self) -> tuple[str, ...]:
        """Return the configured MCP origin allowlist."""

        return tuple(item.strip() for item in self.mcp_allowed_origins.split(",") if item.strip())


settings = Settings()
