from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime

import httpx
import psutil

from .config import AppConfig, ServiceEndpoint
from .models import DashboardState, ServiceStatus, TorrentItem


class DashboardCollectors:
    def __init__(self, config: AppConfig, state: DashboardState) -> None:
        self.config = config
        self.state = state
        self.client = httpx.AsyncClient(timeout=8, follow_redirects=True)
        self._insecure_client = httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
        )
        self._service_started_at: dict[str, float] = {}
        self._last_net = psutil.net_io_counters()
        self._last_net_ts = time.time()
        self._qbit_sid: str = ""

    async def close(self) -> None:
        await self.client.aclose()
        await self._insecure_client.aclose()

    async def refresh_services(self) -> None:
        await asyncio.gather(
            *(self._refresh_one_service(service) for service in self.config.services)
        )

    async def _refresh_one_service(self, service: ServiceEndpoint) -> None:
        start = time.perf_counter()
        headers: dict[str, str] = {}
        if service.api_key:
            headers["X-Api-Key"] = service.api_key
        if service.token:
            headers["Authorization"] = f"Bearer {service.token}"
            headers["X-Plex-Token"] = service.token

        is_up, error = await self._probe_service_with_fallback(service, headers)

        latency_ms = (time.perf_counter() - start) * 1000
        now = datetime.now()

        if service.name not in self.state.services:
            self.state.services[service.name] = ServiceStatus(name=service.name)

        status = self.state.services[service.name]
        status.name = service.name
        status.is_up = is_up
        status.last_check = now
        status.latency_ms = latency_ms
        status.error = "" if is_up else error

        if is_up:
            self._service_started_at.setdefault(service.name, time.time())
            status.uptime_seconds = max(
                0.0, time.time() - self._service_started_at[service.name]
            )
        else:
            self._service_started_at.pop(service.name, None)
            status.uptime_seconds = 0.0

    async def refresh_torrents(self) -> None:
        try:
            await self._qbit_login()
            response = await self.client.get(
                f"{self.config.qbit.url}/api/v2/torrents/info"
            )
            if response.status_code == 403:
                await self._qbit_login(force=True)
                response = await self.client.get(
                    f"{self.config.qbit.url}/api/v2/torrents/info"
                )

            response.raise_for_status()
            payload = response.json()
            torrents: list[TorrentItem] = []
            for item in payload:
                progress = float(item.get("progress", 0.0)) * 100
                if progress >= 100 and item.get("state", "") in {
                    "uploading",
                    "stalledUP",
                }:
                    continue
                torrents.append(
                    TorrentItem(
                        name=str(item.get("name", "Unknown")),
                        progress=progress,
                        state=str(item.get("state", "unknown")),
                        dlspeed=int(item.get("dlspeed", 0)),
                        upspeed=int(item.get("upspeed", 0)),
                        eta_seconds=int(item.get("eta", -1)),
                        ratio=float(item.get("ratio", 0.0)),
                    )
                )
            self.state.torrents = torrents
        except Exception:
            self.state.torrents = []

    async def _probe_service_with_fallback(
        self, service: ServiceEndpoint, headers: dict[str, str]
    ) -> tuple[bool, str]:
        if service.probe_kind == "tcp":
            return await self._probe_tcp(service)

        primary_probe_url = self._service_probe_url(service, service.url)
        primary_up, primary_error = await self._probe_http_url(
            primary_probe_url, headers
        )

        if primary_up or not service.remote_url.strip():
            return primary_up, primary_error

        remote_probe_url = self._service_probe_url(service, service.remote_url)
        remote_up, remote_error = await self._probe_http_url(remote_probe_url, headers)
        if remote_up:
            return True, ""

        if primary_error and remote_error:
            return False, f"local={primary_error}; remote={remote_error}"
        return False, remote_error or primary_error

    async def _probe_http_url(
        self, probe_url: str, headers: dict[str, str]
    ) -> tuple[bool, str]:
        try:
            response = await self.client.get(probe_url, headers=headers)
            if response.status_code < 500:
                return True, ""
            return False, f"HTTP {response.status_code}"
        except httpx.ConnectError as exc:
            message = str(exc)
            if self._is_tls_trust_error(message):
                try:
                    response = await self._insecure_client.get(
                        probe_url, headers=headers
                    )
                    if response.status_code < 500:
                        return True, ""
                    return False, f"HTTP {response.status_code}"
                except Exception as retry_exc:
                    return False, str(retry_exc)
            return False, message
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _is_tls_trust_error(message: str) -> bool:
        text = message.upper()
        return (
            "CERTIFICATE_VERIFY_FAILED" in text
            or "SEC_E_UNTRUSTED_ROOT" in text
            or "CERTIFICATE" in text
            and "UNTRUST" in text
        )

    async def _probe_tcp(self, service: ServiceEndpoint) -> tuple[bool, str]:
        host = service.tcp_host.strip()
        port = service.tcp_port
        if not host:
            return False, "Missing TCP host"

        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=8,
            )
            with contextlib.suppress(Exception):
                await asyncio.wait_for(reader.read(1), timeout=0.1)
            return True, ""
        except Exception as exc:
            return False, str(exc)
        finally:
            if writer is not None:
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()

    async def _qbit_login(self, force: bool = False) -> None:
        if self._qbit_sid and not force:
            return
        response = await self.client.post(
            f"{self.config.qbit.url}/api/v2/auth/login",
            data={
                "username": self.config.qbit.username,
                "password": self.config.qbit.password,
            },
        )
        response.raise_for_status()
        self._qbit_sid = response.cookies.get("SID", "")

    async def refresh_host_metrics(self) -> None:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory().percent

        now = time.time()
        current = psutil.net_io_counters()
        elapsed = max(0.001, now - self._last_net_ts)

        sent_bps = max(0.0, (current.bytes_sent - self._last_net.bytes_sent) / elapsed)
        recv_bps = max(0.0, (current.bytes_recv - self._last_net.bytes_recv) / elapsed)

        self._last_net = current
        self._last_net_ts = now

        self.state.host_metrics.cpu_percent = cpu
        self.state.host_metrics.memory_percent = memory
        self.state.host_metrics.network_sent_bps = sent_bps
        self.state.host_metrics.network_recv_bps = recv_bps
        self.state.host_metrics.updated_at = datetime.now()

    @staticmethod
    def _service_probe_url(service: ServiceEndpoint, base_url: str) -> str:
        base = base_url.rstrip("/")
        if service.name == "Sonarr":
            return f"{base}/api/v3/system/status"
        if service.name == "Radarr":
            return f"{base}/api/v3/system/status"
        if service.name == "Prowlarr":
            return f"{base}/api/v1/system/status"
        if service.name == "Plex":
            return f"{base}/identity"
        if service.name == "Home Assistant":
            return f"{base}/api/"
        return base


def human_bytes_per_second(value: float) -> str:
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    amount = float(value)
    idx = 0
    while amount >= 1024 and idx < len(units) - 1:
        amount /= 1024
        idx += 1
    return f"{amount:,.1f} {units[idx]}"


def human_seconds(seconds: float) -> str:
    total = int(max(0, seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"
