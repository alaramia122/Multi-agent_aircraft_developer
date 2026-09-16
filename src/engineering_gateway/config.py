"""Gateway configuration."""

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

    @property
    def parsed_mcp_allowed_hosts(self) -> tuple[str, ...]:
        """Return the configured MCP host allowlist."""

        return tuple(item.strip() for item in self.mcp_allowed_hosts.split(",") if item.strip())

    @property
    def parsed_mcp_allowed_origins(self) -> tuple[str, ...]:
        """Return the configured MCP origin allowlist."""

        return tuple(item.strip() for item in self.mcp_allowed_origins.split(",") if item.strip())


settings = Settings()
