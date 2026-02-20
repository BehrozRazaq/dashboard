from __future__ import annotations

import asyncio
from datetime import datetime

from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static

from .collectors import DashboardCollectors, human_bytes_per_second, human_seconds
from .config import AppConfig
from .models import DashboardState
from .pacman import CommandMenuScreen, PacmanScreen
from .pong import PongScreen
from .snake import SnakeScreen


class FocusPanel(Static):
    can_focus = True


class DashboardApp(App[None]):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+p", "open_command_menu", "Menu"),
        Binding("ctrl+shift+p", "command_palette", "Command Palette", show=False),
        Binding("ctrl+alt+p", "play_pacman", "Play Pac-Man", show=False),
        Binding("ctrl+alt+o", "play_pong", "Play Pong", show=False),
        Binding("ctrl+alt+s", "play_snake", "Play Snake", show=False),
        Binding("r", "refresh_now", "Refresh"),
        Binding("m", "cycle_motion", "Motion"),
        Binding("left", "focus_left", "◀", show=False),
        Binding("right", "focus_right", "▶", show=False),
        Binding("up", "focus_up", "▲", show=False),
        Binding("down", "focus_down", "▼", show=False),
    ]

    title = "Media Ops Dashboard"
    sub_title = "Muted Purple • Cozy Soft Text • Live"

    motion_mode = reactive("normal")

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.state = DashboardState(motion_mode=config.motion_mode)
        self.collectors = DashboardCollectors(config, self.state)
        self._tasks: list[asyncio.Task] = []

        self._cpu_view = 0.0
        self._mem_view = 0.0
        self._up_view = 0.0
        self._down_view = 0.0
        self._title_frame = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="root"):
            yield Static(id="top_strip")
            with Horizontal(id="middle"):
                yield FocusPanel(id="services_panel", classes="focus-panel")
                yield FocusPanel(id="torrents_panel", classes="focus-panel")
            yield FocusPanel(id="metrics_panel", classes="focus-panel")
        yield Footer()

    async def on_mount(self) -> None:
        self.motion_mode = self.config.motion_mode
        self.state.motion_mode = self.motion_mode
        self.query_one("#services_panel", FocusPanel).focus()

        self.set_interval(0.25, self._render_ui)
        self._tasks = [
            asyncio.create_task(self._loop_services(), name="services-loop"),
            asyncio.create_task(self._loop_torrents(), name="torrents-loop"),
            asyncio.create_task(self._loop_metrics(), name="metrics-loop"),
        ]

    async def on_unmount(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.collectors.close()

    async def action_refresh_now(self) -> None:
        await asyncio.gather(
            self.collectors.refresh_services(),
            self.collectors.refresh_torrents(),
            self.collectors.refresh_host_metrics(),
        )

    def action_open_command_menu(self) -> None:
        self.push_screen(CommandMenuScreen())

    def action_play_pacman(self) -> None:
        """Play Pac-Man."""
        self.push_screen(PacmanScreen())

    def action_play_snake(self) -> None:
        """Play Snake."""
        self.push_screen(SnakeScreen())

    def action_play_pong(self) -> None:
        """Play auto Pong."""
        self.push_screen(PongScreen())

    def action_focus_left(self) -> None:
        focused = self.focused
        if focused is None:
            self.query_one("#services_panel", FocusPanel).focus()
            return
        if focused.id == "torrents_panel":
            self.query_one("#services_panel", FocusPanel).focus()

    def action_focus_right(self) -> None:
        focused = self.focused
        if focused is None:
            self.query_one("#services_panel", FocusPanel).focus()
            return
        if focused.id == "services_panel":
            self.query_one("#torrents_panel", FocusPanel).focus()

    def action_focus_up(self) -> None:
        focused = self.focused
        if focused is None:
            self.query_one("#services_panel", FocusPanel).focus()
            return
        if focused.id == "metrics_panel":
            self.query_one("#services_panel", FocusPanel).focus()

    def action_focus_down(self) -> None:
        focused = self.focused
        if focused is None:
            self.query_one("#services_panel", FocusPanel).focus()
            return
        if focused.id in {"services_panel", "torrents_panel"}:
            self.query_one("#metrics_panel", FocusPanel).focus()

    def action_cycle_motion(self) -> None:
        order = ["normal", "reduced", "off"]
        index = order.index(self.motion_mode)
        self.motion_mode = order[(index + 1) % len(order)]
        self.state.motion_mode = self.motion_mode

    async def _loop_services(self) -> None:
        while True:
            await self.collectors.refresh_services()
            await asyncio.sleep(self.config.refresh_services_seconds)

    async def _loop_torrents(self) -> None:
        while True:
            await self.collectors.refresh_torrents()
            await asyncio.sleep(self.config.refresh_torrents_seconds)

    async def _loop_metrics(self) -> None:
        while True:
            await self.collectors.refresh_host_metrics()
            await asyncio.sleep(self.config.refresh_metrics_seconds)

    def _render_ui(self) -> None:
        top = self.query_one("#top_strip", Static)
        services = self.query_one("#services_panel", Static)
        torrents = self.query_one("#torrents_panel", Static)
        metrics = self.query_one("#metrics_panel", Static)

        top.update(self._build_top_strip())
        services.update(self._build_services_panel())
        torrents.update(self._build_torrents_panel())
        metrics.update(self._build_metrics_panel())

    def _build_top_strip(self) -> Panel:
        up_count = sum(1 for item in self.state.services.values() if item.is_up)
        total = max(1, len(self.state.services))
        down = total - up_count
        now = datetime.now().strftime("%H:%M:%S")

        indicator = self._pulse_indicator()
        status = f"{indicator}  Services: [bold]{up_count}/{total}[/] up • [bold]{down}[/] down"
        status += f"    Motion: [bold]{self.motion_mode}[/]    Updated: [bold]{now}[/]"
        return Panel(status, title="Ops Status", border_style="purple")

    def _build_services_panel(self) -> Panel:
        table = Table(expand=True, box=None)
        table.add_column("App", style="bold #d5c9ff")
        table.add_column("State")
        table.add_column("Uptime")
        table.add_column("Latency")
        table.add_column("Last Check")

        for name in ["Sonarr", "Radarr", "Plex", "Home Assistant", "Prowlarr", "SSH"]:
            item = self.state.services.get(name)
            if item is None:
                table.add_row(name, "[yellow]Unknown[/]", "-", "-", "-")
                continue

            state_text = "[green]UP[/]" if item.is_up else "[red]DOWN[/]"
            uptime = human_seconds(item.uptime_seconds) if item.is_up else "0m 00s"
            latency = f"{item.latency_ms:.0f} ms" if item.last_check else "-"
            if item.last_check:
                elapsed = (datetime.now() - item.last_check).total_seconds()
                if elapsed < 1:
                    last = f"{elapsed * 1000:.0f} ms ago"
                else:
                    last = f"{elapsed:.1f} s ago"
            else:
                last = "-"
            table.add_row(name, state_text, uptime, latency, last)

        return Panel(table, title="Service Uptime", border_style="#8f7ad4")

    def _build_torrents_panel(self) -> Panel:
        table = Table(expand=True, box=None)
        table.add_column("Torrent", ratio=2)
        table.add_column("Progress")
        table.add_column("State")
        table.add_column("DL")
        table.add_column("UP")
        table.add_column("ETA")

        rows = self.state.torrents[:14]
        if not rows:
            table.add_row("No active torrents", "-", "-", "-", "-", "-")
        else:
            for item in rows:
                progress = self._progress_bar(item.progress)
                eta = "∞" if item.eta_seconds < 0 else human_seconds(item.eta_seconds)
                table.add_row(
                    item.name[:48],
                    progress,
                    item.state,
                    human_bytes_per_second(item.dlspeed),
                    human_bytes_per_second(item.upspeed),
                    eta,
                )

        return Panel(table, title="Ongoing Torrents", border_style="#8f7ad4")

    def _build_metrics_panel(self) -> Panel:
        alpha = self._motion_alpha()
        target_cpu = self.state.host_metrics.cpu_percent
        target_mem = self.state.host_metrics.memory_percent
        target_up = self.state.host_metrics.network_sent_bps
        target_down = self.state.host_metrics.network_recv_bps

        self._cpu_view = self._lerp(self._cpu_view, target_cpu, alpha)
        self._mem_view = self._lerp(self._mem_view, target_mem, alpha)
        self._up_view = self._lerp(self._up_view, target_up, alpha)
        self._down_view = self._lerp(self._down_view, target_down, alpha)

        table = Table(expand=True, box=None)
        table.add_column("Metric", style="bold #d5c9ff")
        table.add_column("Value", ratio=2)

        table.add_row("CPU", f"{self._bar(self._cpu_view)} {self._cpu_view:5.1f}%")
        table.add_row("Memory", f"{self._bar(self._mem_view)} {self._mem_view:5.1f}%")
        table.add_row("Network Down", f"{human_bytes_per_second(self._down_view)}")
        table.add_row("Network Up", f"{human_bytes_per_second(self._up_view)}")

        return Panel(table, title="Host Metrics", border_style="#8f7ad4")

    def _bar(self, value: float, width: int = 22) -> str:
        filled = int((max(0.0, min(100.0, value)) / 100) * width)
        return f"[bold #b69cff]{'█' * filled}[/][#4d3f73]{'░' * (width - filled)}[/]"

    def _progress_bar(self, percent: float, width: int = 16) -> str:
        filled = int((max(0.0, min(100.0, percent)) / 100) * width)
        return f"[bold #c3b0ff]{'▰' * filled}[/][#4d3f73]{'▱' * (width - filled)}[/] {percent:5.1f}%"

    def _motion_alpha(self) -> float:
        if self.motion_mode == "off":
            return 1.0
        if self.motion_mode == "reduced":
            return 0.45
        return 0.25

    def _pulse_indicator(self) -> str:
        if self.motion_mode == "off":
            return "◆"
        frames = ["◇", "◆", "◈", "◆"] if self.motion_mode == "normal" else ["◇", "◆"]
        self._title_frame = (self._title_frame + 1) % len(frames)
        return f"[bold #c5b1ff]{frames[self._title_frame]}[/]"

    @staticmethod
    def _lerp(current: float, target: float, alpha: float) -> float:
        return current + (target - current) * alpha
