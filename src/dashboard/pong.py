from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Static


class PongScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back", show=False),
        Binding("p", "pause", "Pause", show=False),
        Binding("enter", "reset", "Reset", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.width = 40
        self.height = 16
        self.cell_width = 4
        self.cell_height = 2
        self.paddle_height = 3
        self.left_x = 2
        self.right_x = self.width - 3

        self.left_y = self.height / 2
        self.right_y = self.height / 2

        self.ball_x = self.width / 2
        self.ball_y = self.height / 2
        self.ball_vx = 0.55
        self.ball_vy = 0.32
        self.paddle_speed = 0.65

        self.paused = False
        self.left_score = 0
        self.right_score = 0
        self.rally_hits = 0
        self.left_hits = 0
        self.right_hits = 0
        self._timer = None
        self._mounted = False

    def compose(self) -> ComposeResult:
        with Container(id="pong_root"):
            yield Static("Auto Pong (Perfect AI vs Perfect AI)", id="pong_title")
            yield Static("", id="pong_score")
            yield Static("", id="pong_canvas")
            yield Static(
                "Autoplay demo • p pause • Enter reset • q/esc return", id="pong_hint"
            )

    def on_mount(self) -> None:
        self._mounted = True
        self._fit_to_canvas()
        self._sync_geometry()
        self._reset_ball()
        self._start_timer()
        self._draw_board()

    def on_resize(self) -> None:
        if not self._mounted:
            return
        if self._fit_to_canvas():
            self._sync_geometry()
            self._reset_ball()
        self._draw_board()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_pause(self) -> None:
        self.paused = not self.paused
        self._draw_board()

    def action_reset(self) -> None:
        self.left_score = 0
        self.right_score = 0
        self.rally_hits = 0
        self.left_hits = 0
        self.right_hits = 0
        self._reset_ball()
        self._draw_board()

    def _fit_to_canvas(self) -> bool:
        canvas = self.query_one("#pong_canvas", Static)
        canvas_w = max(1, canvas.size.width)
        canvas_h = max(1, canvas.size.height)
        new_width = max(20, canvas_w // self.cell_width)
        new_height = max(10, canvas_h // self.cell_height)
        changed = new_width != self.width or new_height != self.height
        if changed:
            self.width = new_width
            self.height = new_height
        return changed

    def _sync_geometry(self) -> None:
        self.left_x = max(1, min(self.left_x, self.width - 2))
        self.right_x = max(self.left_x + 2, self.width - 3)
        self.left_y = min(max(self.left_y, 0), self.height - 1)
        self.right_y = min(max(self.right_y, 0), self.height - 1)

    def _start_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_interval(0.05, self._tick)  # 20 FPS

    def _reset_ball(self) -> None:
        self.ball_x = self.width / 2
        self.ball_y = self.height / 2
        self.ball_vx = 0.55 if self.ball_vx >= 0 else -0.55
        self.ball_vy = 0.32 if self.ball_vy >= 0 else -0.32

    def _tick(self) -> None:
        if self.paused:
            self._draw_board()
            return

        left_target = self._predict_intercept(self.left_x + 1)
        right_target = self._predict_intercept(self.right_x - 1)

        self.left_y = self._move_toward(self.left_y, left_target, self.paddle_speed)
        self.right_y = self._move_toward(self.right_y, right_target, self.paddle_speed)

        next_x = self.ball_x + self.ball_vx
        next_y = self.ball_y + self.ball_vy

        if next_y <= 0:
            next_y = -next_y
            self.ball_vy *= -1
        elif next_y >= self.height - 1:
            next_y = 2 * (self.height - 1) - next_y
            self.ball_vy *= -1

        # Safeguard: snap only when ball is very close to paddle x so AI never misses.
        if self.ball_vx < 0 and next_x <= self.left_x + 2:
            self.left_y = left_target
        if self.ball_vx > 0 and next_x >= self.right_x - 2:
            self.right_y = right_target

        half = self.paddle_height // 2
        left_center = int(round(self.left_y))
        right_center = int(round(self.right_y))
        left_top = left_center - half
        left_bottom = left_center + half
        right_top = right_center - half
        right_bottom = right_center + half

        if self.ball_vx < 0 and next_x <= self.left_x + 1:
            impact_y = int(round(next_y))
            if left_top <= impact_y <= left_bottom:
                next_x = (self.left_x + 1) + ((self.left_x + 1) - next_x)
                self.ball_vx = abs(self.ball_vx)
                self.left_hits += 1
                self.rally_hits += 1

        if self.ball_vx > 0 and next_x >= self.right_x - 1:
            impact_y = int(round(next_y))
            if right_top <= impact_y <= right_bottom:
                next_x = (self.right_x - 1) - (next_x - (self.right_x - 1))
                self.ball_vx = -abs(self.ball_vx)
                self.right_hits += 1
                self.rally_hits += 1

        # Point scored when ball passes a paddle.
        if next_x < 0:
            self.right_score += 1
            self.rally_hits = 0
            self.ball_vx = abs(self.ball_vx)
            self._reset_ball()
            self._draw_board()
            return
        if next_x > self.width - 1:
            self.left_score += 1
            self.rally_hits = 0
            self.ball_vx = -abs(self.ball_vx)
            self._reset_ball()
            self._draw_board()
            return

        self.ball_x = next_x
        self.ball_y = next_y
        self._draw_board()

    def _predict_intercept(self, target_x: int) -> float:
        x = self.ball_x
        y = self.ball_y
        vx = self.ball_vx
        vy = self.ball_vy

        # Simulate ahead with bounce handling until reaching x target.
        for _ in range(1000):
            if (vx > 0 and x >= target_x) or (vx < 0 and x <= target_x):
                return y
            x += vx
            y += vy
            if y <= 0:
                y = -y
                vy *= -1
            elif y >= self.height - 1:
                y = 2 * (self.height - 1) - y
                vy *= -1
        return self.height / 2

    @staticmethod
    def _move_toward(current: float, target: float, max_step: float) -> float:
        delta = target - current
        if abs(delta) <= max_step:
            return target
        return current + max_step if delta > 0 else current - max_step

    def _draw_board(self) -> None:
        self._sync_geometry()
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]

        for y in range(self.height):
            grid[y][self.width // 2] = "·"

        half = self.paddle_height // 2
        left_center = int(round(self.left_y))
        right_center = int(round(self.right_y))
        left_top = max(0, left_center - half)
        left_bottom = min(self.height - 1, left_center + half)
        right_top = max(0, right_center - half)
        right_bottom = min(self.height - 1, right_center + half)

        left_col = max(0, min(self.width - 1, self.left_x))
        right_col = max(0, min(self.width - 1, self.right_x))

        for y in range(left_top, left_bottom + 1):
            grid[y][left_col] = "█"
        for y in range(right_top, right_bottom + 1):
            grid[y][right_col] = "█"

        bx = max(0, min(self.width - 1, int(round(self.ball_x))))
        by = max(0, min(self.height - 1, int(round(self.ball_y))))
        grid[by][bx] = "■"

        lines = []
        for row in grid:
            styled_cells = []
            for ch in row:
                if ch == "█":
                    styled_cells.append(self._cell("#b4ff8a"))
                elif ch == "■":
                    styled_cells.append(self._cell("#ffd783"))
                elif ch == "·":
                    styled_cells.append(self._cell("#2e2548", "·", "#6f5aa5"))
                else:
                    styled_cells.append(" " * self.cell_width)

            row_text = "".join(styled_cells)
            for _ in range(self.cell_height):
                lines.append(row_text)

        state = "[bold #d9ccff]Paused[/]" if self.paused else "[bold #8df7b0]Running[/]"
        score_text = (
            f"Score L [bold #e7dcff]{self.left_score}[/]  "
            f"Score R [bold #e7dcff]{self.right_score}[/]  "
            f"Rally [bold #e7dcff]{self.rally_hits}[/]  "
            f"Left Hits [bold #e7dcff]{self.left_hits}[/]  "
            f"Right Hits [bold #e7dcff]{self.right_hits}[/]  "
            f"{state}"
        )

        self.query_one("#pong_score", Static).update(score_text)
        self.query_one("#pong_canvas", Static).update("\n".join(lines))

    def _cell(
        self, background: str, symbol: str = "", foreground: str = "#101010"
    ) -> str:
        symbol = symbol[:1]
        body = (symbol + " " * self.cell_width)[: self.cell_width]
        if symbol:
            return f"[on {background} {foreground}]{body}[/]"
        return f"[on {background}]{body}[/]"
