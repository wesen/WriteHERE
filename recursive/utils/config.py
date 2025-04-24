from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os


@dataclass
class ServerConfig:
    """Configuration class for the WebSocket server."""

    redis_url: str = "redis://localhost:6379/0"
    event_stream: str = "agent_events"
    host: str = "0.0.0.0"
    port: int = 9999
    db_path: str = "runs/events.db"
    reload_session: bool = False
    log_level: str = "INFO"
    debug: bool = False

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create a ServerConfig instance from environment variables."""
        return cls(
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            event_stream=os.getenv("EVENT_STREAM", cls.event_stream),
            host=os.getenv("WS_HOST", cls.host),
            port=int(os.getenv("WS_PORT", cls.port)),
            db_path=os.getenv("SQLITE_DB_PATH", cls.db_path),
            reload_session=os.getenv("RELOAD_LATEST_SESSION", "false").lower()
            == "true",
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )

    def to_env(self) -> None:
        """Set environment variables from the current configuration."""
        os.environ["REDIS_URL"] = self.redis_url
        os.environ["EVENT_STREAM"] = self.event_stream
        os.environ["WS_HOST"] = self.host
        os.environ["WS_PORT"] = str(self.port)
        os.environ["SQLITE_DB_PATH"] = self.db_path
        os.environ["RELOAD_LATEST_SESSION"] = str(self.reload_session).lower()
        os.environ["LOG_LEVEL"] = "DEBUG" if self.debug else self.log_level

    def get_ui_url(self) -> str:
        """Get the UI URL based on the host configuration."""
        display_host = "localhost" if self.host == "0.0.0.0" else self.host
        return f"http://{display_host}:{self.port}"
