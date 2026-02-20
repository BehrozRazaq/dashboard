from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse
from dotenv import load_dotenv


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_tcp_host(value: str, default: str) -> str:
    raw = value.strip()
    if not raw:
        return default
    if "://" not in raw:
        return raw
    parsed = urlparse(raw)
    return parsed.hostname or default


@dataclass(slots=True)
class ServiceEndpoint:
    name: str
    url: str
    remote_url: str = ""
    token: str = ""
    api_key: str = ""
    probe_kind: str = "http"
    tcp_host: str = ""
    tcp_port: int = 0


@dataclass(slots=True)
class QbitConfig:
    url: str
    username: str
    password: str


@dataclass(slots=True)
class AppConfig:
    services: list[ServiceEndpoint]
    qbit: QbitConfig
    refresh_metrics_seconds: int
    refresh_services_seconds: int
    refresh_torrents_seconds: int
    motion_mode: str
    enable_asciimatics: bool


def load_config() -> AppConfig:
    load_dotenv()

    services = [
        ServiceEndpoint(
            "Sonarr",
            os.getenv("SONARR_URL", "http://localhost:8989"),
            remote_url=os.getenv("SONARR_REMOTE_URL", "https://shows.razaq.dev"),
            api_key=os.getenv("SONARR_API_KEY", ""),
        ),
        ServiceEndpoint(
            "Radarr",
            os.getenv("RADARR_URL", "http://localhost:7878"),
            remote_url=os.getenv("RADARR_REMOTE_URL", "https://movies.razaq.dev"),
            api_key=os.getenv("RADARR_API_KEY", ""),
        ),
        ServiceEndpoint(
            "Plex",
            os.getenv("PLEX_URL", "http://localhost:32400"),
            remote_url=os.getenv("PLEX_REMOTE_URL", ""),
            token=os.getenv("PLEX_TOKEN", ""),
        ),
        ServiceEndpoint(
            "Home Assistant",
            os.getenv("HOMEASSISTANT_URL", "http://localhost:8123"),
            remote_url=os.getenv("HOMEASSISTANT_REMOTE_URL", "https://home.razaq.dev"),
            token=os.getenv("HOMEASSISTANT_TOKEN", ""),
        ),
        ServiceEndpoint(
            "Prowlarr",
            os.getenv("PROWLARR_URL", "http://localhost:9696"),
            remote_url=os.getenv("PROWLARR_REMOTE_URL", "https://prowlarr.razaq.dev"),
            api_key=os.getenv("PROWLARR_API_KEY", ""),
        ),
        ServiceEndpoint(
            "SSH",
            os.getenv("SSH_URL", "ssh.razaq.dev"),
            probe_kind="tcp",
            tcp_host=_normalize_tcp_host(
                os.getenv("SSH_URL", "ssh.razaq.dev"), "ssh.razaq.dev"
            ),
            tcp_port=max(1, _env_int("SSH_PORT", 22)),
        ),
    ]

    qbit = QbitConfig(
        url=os.getenv("QBITTORRENT_URL", "http://localhost:8080"),
        username=os.getenv("QBITTORRENT_USERNAME", "admin"),
        password=os.getenv("QBITTORRENT_PASSWORD", "adminadmin"),
    )

    motion_mode = os.getenv("MOTION_MODE", "normal").strip().lower()
    if motion_mode not in {"normal", "reduced", "off"}:
        motion_mode = "normal"

    return AppConfig(
        services=services,
        qbit=qbit,
        refresh_metrics_seconds=max(1, _env_int("REFRESH_METRICS_SECONDS", 1)),
        refresh_services_seconds=max(2, _env_int("REFRESH_SERVICES_SECONDS", 5)),
        refresh_torrents_seconds=max(2, _env_int("REFRESH_TORRENTS_SECONDS", 3)),
        motion_mode=motion_mode,
        enable_asciimatics=os.getenv("ENABLE_ASCIIMATICS", "0").strip() == "1",
    )
