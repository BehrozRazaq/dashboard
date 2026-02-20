from __future__ import annotations

import json
import random
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Static


class SnakeScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back", show=False),
        Binding("enter", "restart", "Restart", show=False),
        Binding("p", "pause", "Pause", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("left", "move_left", "Left", show=False),
        Binding("right", "move_right", "Right", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.width = 34
        self.height = 18
        self.cell_width = 4
        self.cell_height = 2
        self.tick_seconds = 0.11

        self.snake: list[tuple[int, int]] = []
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.food = (0, 0)
        self.special_food: tuple[int, int] | None = None
        self.special_food_ticks = 0
        self.special_food_cooldown = 0
        self.obstacles: set[tuple[int, int]] = set()

        self.score = 0
        self.high_score = 0
        self.level = 1
        self.food_eaten = 0
        self.game_over = False
        self.paused = False

        self._timer = None
        self._high_score_path = self._resolve_high_score_path()
        self._mounted = False

    def compose(self) -> ComposeResult:
        with Container(id="snake_root"):
            yield Static("Snake", id="snake_title")
            yield Static("", id="snake_score")
            yield Static("", id="snake_canvas")
            yield Static(
                "Arrows move • p pause • Enter restart • q/esc return", id="snake_hint"
            )

    def on_mount(self) -> None:
        self._mounted = True
        self.high_score = self._load_high_score()
        self._fit_board_to_canvas()
        self._reset_game(reset_score=True)

    def on_resize(self) -> None:
        if not self._mounted:
            return
        changed = self._fit_board_to_canvas()
        if changed:
            self._reset_game(reset_score=True)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_restart(self) -> None:
        self._reset_game(reset_score=True)

    def action_pause(self) -> None:
        if self.game_over:
            return
        self.paused = not self.paused
        self._render_board()

    def action_move_up(self) -> None:
        self._set_direction((0, -1))

    def action_move_down(self) -> None:
        self._set_direction((0, 1))

    def action_move_left(self) -> None:
        self._set_direction((-1, 0))

    def action_move_right(self) -> None:
        self._set_direction((1, 0))

    def _set_direction(self, direction: tuple[int, int]) -> None:
        if self.game_over:
            return
        if direction == (-self.direction[0], -self.direction[1]):
            return
        self.next_direction = direction

    def _reset_game(self, reset_score: bool) -> None:
        center_x = self.width // 2
        center_y = self.height // 2
        self.snake = [
            (center_x, center_y),
            (center_x - 1, center_y),
            (center_x - 2, center_y),
        ]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.obstacles = self._build_obstacles()
        self.food = self._spawn_food()
        self.special_food = None
        self.special_food_ticks = 0
        self.special_food_cooldown = 24
        self.game_over = False
        self.paused = False
        self.level = 1
        self.food_eaten = 0
        self.tick_seconds = 0.11
        if reset_score:
            self.score = 0

        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_interval(self.tick_seconds, self._game_tick)
        self._render_board()

    def _fit_board_to_canvas(self) -> bool:
        canvas = self.query_one("#snake_canvas", Static)
        canvas_w = max(1, canvas.size.width)
        canvas_h = max(1, canvas.size.height)

        new_width = max(8, canvas_w // self.cell_width)
        new_height = max(6, canvas_h // self.cell_height)

        changed = new_width != self.width or new_height != self.height
        if changed:
            self.width = new_width
            self.height = new_height
        return changed

    def _game_tick(self) -> None:
        if self.game_over or self.paused:
            self._render_board()
            return

        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        next_x = (head_x + self.direction[0]) % self.width
        next_y = (head_y + self.direction[1]) % self.height
        next_head = (next_x, next_y)

        if next_head in self.obstacles or next_head in self.snake:
            self.game_over = True
            if self.score > self.high_score:
                self.high_score = self.score
                self._save_high_score(self.high_score)
            self._render_board()
            return

        self.snake.insert(0, next_head)
        grew = False

        if next_head == self.food:
            self.score += 10
            self.food_eaten += 1
            self.food = self._spawn_food()
            grew = True

            if self.food_eaten % 5 == 0:
                self.level += 1
                self._increase_speed()

            if self.score > self.high_score:
                self.high_score = self.score
                self._save_high_score(self.high_score)

        if self.special_food is not None and next_head == self.special_food:
            self.score += 50
            self.special_food = None
            self.special_food_ticks = 0
            self.special_food_cooldown = 40
            grew = True
            if self.score > self.high_score:
                self.high_score = self.score
                self._save_high_score(self.high_score)

        if not grew:
            self.snake.pop()

        self._update_special_food()
        self._render_board()

    def _update_special_food(self) -> None:
        if self.special_food is not None:
            self.special_food_ticks -= 1
            if self.special_food_ticks <= 0:
                self.special_food = None
                self.special_food_cooldown = 30
            return

        self.special_food_cooldown -= 1
        if self.special_food_cooldown <= 0:
            self.special_food = self._spawn_food()
            self.special_food_ticks = 28

    def _increase_speed(self) -> None:
        new_speed = max(0.06, self.tick_seconds - 0.01)
        if abs(new_speed - self.tick_seconds) < 1e-9:
            return
        self.tick_seconds = new_speed
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_interval(self.tick_seconds, self._game_tick)

    def _build_obstacles(self) -> set[tuple[int, int]]:
        obstacles: set[tuple[int, int]] = set()
        center_x = self.width // 2
        center_y = self.height // 2
        ring_half_w = max(3, self.width // 5)
        ring_half_h = max(2, self.height // 5)

        left = max(1, center_x - ring_half_w)
        right = min(self.width - 2, center_x + ring_half_w)
        top = max(1, center_y - ring_half_h)
        bottom = min(self.height - 2, center_y + ring_half_h)

        for x in range(left, right + 1):
            if x in {center_x - 1, center_x, center_x + 1}:
                continue
            obstacles.add((x, top))
            obstacles.add((x, bottom))
        for y in range(top + 1, bottom):
            if y in {center_y - 1, center_y, center_y + 1}:
                continue
            obstacles.add((left, y))
            obstacles.add((right, y))
        return obstacles

    def _spawn_food(self) -> tuple[int, int]:
        blocked = set(self.snake) | self.obstacles
        if self.special_food is not None:
            blocked.add(self.special_food)

        options = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in blocked
        ]
        if not options:
            return (0, 0)
        return random.choice(options)

    def _render_board(self) -> None:
        snake_head = self.snake[0]
        snake_body = set(self.snake[1:])
        rows: list[str] = []

        for y in range(self.height):
            line: list[str] = []
            for x in range(self.width):
                point = (x, y)
                if point == snake_head:
                    line.append(self._cell("#b9ff93"))
                elif point in snake_body:
                    line.append(self._cell("#79d36e"))
                elif point in self.obstacles:
                    line.append(self._cell("#6d5aa5"))
                elif point == self.food:
                    line.append(self._cell("#ff8eb0", "◆", "#1a1028"))
                elif self.special_food is not None and point == self.special_food:
                    pulse_color = (
                        "#ffd56a" if self.special_food_ticks % 4 < 2 else "#fff2c2"
                    )
                    line.append(self._cell(pulse_color, "✦", "#1a1028"))
                else:
                    line.append(" " * self.cell_width)

            row_text = "".join(line)
            for _ in range(self.cell_height):
                rows.append(row_text)

        if self.game_over:
            state = "[bold #ff8fb1]Game Over[/]"
        elif self.paused:
            state = "[bold #d9ccff]Paused[/]"
        else:
            state = "[bold #8df7b0]Running[/]"

        bonus = (
            f" Bonus: {self.special_food_ticks}"
            if self.special_food is not None
            else ""
        )
        score_text = (
            f"Score [bold #e7dcff]{self.score}[/]  "
            f"High [bold #e7dcff]{self.high_score}[/]  "
            f"Len [bold #e7dcff]{len(self.snake)}[/]  "
            f"Lvl [bold #e7dcff]{self.level}[/]  "
            f"{state}{bonus}"
        )

        self.query_one("#snake_score", Static).update(score_text)
        self.query_one("#snake_canvas", Static).update("\n".join(rows))

    def _cell(
        self, background: str, symbol: str = "", foreground: str = "#101010"
    ) -> str:
        symbol = symbol[:1]
        body = (symbol + " " * self.cell_width)[: self.cell_width]
        if symbol:
            return f"[on {background} {foreground}]{body}[/]"
        return f"[on {background}]{body}[/]"

    @staticmethod
    def _resolve_high_score_path() -> Path:
        root = Path(__file__).resolve().parents[2]
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "snake_high_score.json"

    def _load_high_score(self) -> int:
        try:
            if not self._high_score_path.exists():
                return 0
            payload = json.loads(self._high_score_path.read_text(encoding="utf-8"))
            value = int(payload.get("high_score", 0))
            return max(0, value)
        except Exception:
            return 0

    def _save_high_score(self, high_score: int) -> None:
        try:
            payload = {"high_score": int(high_score)}
            self._high_score_path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception:
            return
