from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ServiceStatus:
    name: str
    is_up: bool = False
    uptime_seconds: float = 0.0
    latency_ms: float = 0.0
    last_check: datetime | None = None
    error: str = ""


@dataclass(slots=True)
class TorrentItem:
    name: str
    progress: float
    state: str
    dlspeed: int
    upspeed: int
    eta_seconds: int
    ratio: float


@dataclass(slots=True)
class HostMetrics:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    network_sent_bps: float = 0.0
    network_recv_bps: float = 0.0
    updated_at: datetime | None = None


@dataclass(slots=True)
class DashboardState:
    services: dict[str, ServiceStatus] = field(default_factory=dict)
    torrents: list[TorrentItem] = field(default_factory=list)
    host_metrics: HostMetrics = field(default_factory=HostMetrics)
    motion_mode: str = "normal"
