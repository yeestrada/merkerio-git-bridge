import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _application_directory() -> Path:
    """Return the directory that contains the app and its external settings."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


load_dotenv(_application_directory() / ".env")


@dataclass
class MarkerConfig:
    base_url: str
    tasks_url: Optional[str]
    workspace_id: Optional[str]
    api_key: Optional[str]
    cookie: Optional[str]
    auth_mode: str = "api_key"

    @classmethod
    def from_env(cls) -> "MarkerConfig":
        base_url = (os.getenv("MARKER_BASE_URL") or "https://api.marker.io").rstrip("/")
        return cls(
            base_url=base_url,
            tasks_url=(os.getenv("MARKER_TASKS_URL") or "").strip() or None,
            workspace_id=(os.getenv("MARKER_WORKSPACE_ID") or "").strip() or None,
            api_key=(os.getenv("MARKER_API_KEY") or "").strip() or None,
            cookie=(os.getenv("MARKER_COOKIE") or "").strip() or None,
            auth_mode=(os.getenv("MARKER_AUTH_MODE") or "api_key").strip().lower(),
        )


@dataclass
class GitHubConfig:
    owner: str
    repo: str
    token: str
    api_url: str = "https://api.github.com"
    label: str = "markerio"

    @classmethod
    def from_env(cls) -> "GitHubConfig":
        owner = (os.getenv("GITHUB_OWNER") or "").strip()
        repo = (os.getenv("GITHUB_REPO") or "").strip()
        token = (os.getenv("GITHUB_TOKEN") or "").strip()
        if not owner or not repo or not token:
            raise ValueError("GITHUB_OWNER, GITHUB_REPO y GITHUB_TOKEN son obligatorios.")
        return cls(
            owner=owner,
            repo=repo,
            token=token,
            api_url=(os.getenv("GITHUB_API_URL") or "https://api.github.com").rstrip("/"),
            label=(os.getenv("GITHUB_LABEL") or "markerio").strip() or "markerio",
        )


@dataclass
class AppConfig:
    marker: MarkerConfig
    github: GitHubConfig
    dry_run: bool = False
    require_confirmation: bool = False

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            marker=MarkerConfig.from_env(),
            github=GitHubConfig.from_env(),
            dry_run=(os.getenv("DRY_RUN") or "false").strip().lower() in {"1", "true", "yes", "on"},
            require_confirmation=(os.getenv("REQUIRE_CONFIRMATION") or "false").strip().lower() in {"1", "true", "yes", "on"},
        )
