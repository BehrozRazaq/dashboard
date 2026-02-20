# Media Ops Dashboard (TUI)

A dense, cozy, muted-purple terminal dashboard for:

- Sonarr, Radarr, Plex, Home Assistant, Prowlarr uptime (HTTP availability uptime)
- SSH reachability (TCP)
- Ongoing torrents from qBittorrent
- Local Windows host metrics (CPU, memory, network)

Built with `textual` + `rich` + `asyncio`, using `psutil` and `httpx`.

## Visual style

- Muted purple palette with soft, low-glare text
- Dense pro dashboard layout for fast scanning
- Smooth transitions on metric and progress changes
- Motion mode toggle: `normal` / `reduced` / `off`

## Setup

1. Create and activate a Python 3.10+ environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill values.
	- Set local URLs in `*_URL`.
	- Set reverse-proxy fallbacks in `*_REMOTE_URL` using `https://...`.
	- Set `SSH_URL` and `SSH_PORT` for SSH reachability checks.
4. Run:

```bash
python -m dashboard.main
```

or:

```bash
dashboard
```

## Controls

- `q`: quit
- `Ctrl+P`: open power menu
- `Ctrl+Shift+P`: open command palette
- `r`: manual refresh
- `m`: cycle motion mode (`normal` → `reduced` → `off`)
- `← ↑ ↓ →`: move focus between panels (focused panel gets a soft purple halo)

### Pac-Man

- Open from power menu: `Ctrl+P`, then `1` or `Enter`
- Move: `← ↑ ↓ →`
- Restart run: `Enter`
- Exit game: `q` or `Esc`
- Features now included:
	- Four colored ghosts (Blinky/Pinky/Inky/Clyde)
	- Power-pellet medicine (`◉`) for frightened/running ghosts
	- Fruit spawn events (`◆`) mid-level
	- Directional Pac-Man turning animation
	- Ghost home base + return when eaten
	- 3 lives with game-over / restart flow

### Snake

- Open from power menu: `Ctrl+P`, then `2`
- Move: `← ↑ ↓ →`
- Pause/Resume: `p`
- Restart run: `Enter`
- Exit game: `q` or `Esc`
- Features now included:
	- Wrap tunnels at board edges
	- Static obstacle ring in center map
	- Special timed bonus food (`✦`)
	- Auto speed increase by level
	- Persistent local high score

### Auto Pong

- Open from power menu: `Ctrl+P`, then `3`
- Pause/Resume: `p`
- Reset rally counters: `Enter`
- Exit game: `q` or `Esc`
- Features now included:
	- AI vs AI autoplay (both paddles computer controlled)
	- Perfect prediction paddles that do not miss
	- Calm, background-friendly speed

## Notes

- Uptime is based on successful HTTP/API reachability duration.
- HTTP service checks are local-first (`*_URL`) with automatic fallback to `*_REMOTE_URL` when local checks fail.
- HTTP `4xx` responses are treated as reachable/up; non-2xx (except 4xx) and connection errors are down.
- If a service is down, the app shows degraded/down state without stopping.
- Home Assistant is monitored as an application endpoint only.
