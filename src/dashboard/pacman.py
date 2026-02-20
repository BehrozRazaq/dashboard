from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen, Screen
from textual.widgets import Static

Direction = Literal["up", "down", "left", "right"]
GhostMode = Literal["home", "scatter", "chase", "frightened", "eaten"]


@dataclass(slots=True)
class Ghost:
    name: str
    x: int
    y: int
    home_x: int
    home_y: int
    color: str
    mode: GhostMode = "home"
    direction: Direction = "left"
    released: bool = False
    frightened_ticks: int = 0
    release_tick: int = 0


LEVEL = [
    "############################",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#..........................#",
    "#.####.##.########.##.####.#",
    "#......##....##....##......#",
    "######.##### ## #####.######",
    "######.#            #.######",
    "######.# ###HHHH### #.######",
    "      .  #H      H#  .      ",
    "######.# ###====### #.######",
    "######.#            #.######",
    "######.# ########## #.######",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o..##................##..o#",
    "###.##.##.########.##.##.###",
    "#......##....##....##......#",
    "#..##########..##########..#",
    "#..........................#",
    "############################",
]

WALL = "#"
PELLET = "."
POWER = "o"
HOUSE = "H"
GATE = "="
EMPTY = " "


class CommandMenuScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("enter", "launch_pacman", "Launch", show=False),
        Binding("1", "launch_pacman", "Launch", show=False),
        Binding("2", "launch_snake", "Launch Snake", show=False),
        Binding("3", "launch_pong", "Launch Pong", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="command_menu_modal"):
            yield Static("Power Menu", id="command_menu_title")
            yield Static("1) Play Pac-Man", id="command_menu_item")
            yield Static("2) Play Snake", classes="command_menu_item")
            yield Static("3) Auto Pong", classes="command_menu_item")
            yield Static(
                "Enter/1: Pac-Man  2: Snake  3: Pong  Esc: Close",
                id="command_menu_hint",
            )

    def action_close(self) -> None:
        self.dismiss()

    def action_launch_pacman(self) -> None:
        self.dismiss()
        self.app.action_play_pacman()

    def action_launch_snake(self) -> None:
        self.dismiss()
        self.app.action_play_snake()

    def action_launch_pong(self) -> None:
        self.dismiss()
        self.app.action_play_pong()


class PacmanScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back", show=False),
        Binding("enter", "restart", "Restart", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("left", "move_left", "Left", show=False),
        Binding("right", "move_right", "Right", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.map = [list(row) for row in LEVEL]
        self.height = len(self.map)
        self.width = len(self.map[0])

        self.player_x = 14
        self.player_y = 16
        self.player_dir: Direction = "left"
        self.next_dir: Direction = "left"

        self.ghosts: list[Ghost] = []
        self._init_ghosts()

        self.tick = 0
        self.mode_timer = 0
        self.mode_cycle_index = 0
        self.global_mode: Literal["scatter", "chase"] = "scatter"

        self.fruit_pos = (14, 10)
        self.fruit_visible = False
        self.fruit_ticks_left = 0
        self._fruit_spawned_once = False
        self._fruit_spawned_twice = False

        self.ghost_combo = 0
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.level_cleared = False
        self._mouth_open = True
        self._pellet_count = 0
        self._initial_pellet_count = 0

    def compose(self) -> ComposeResult:
        with Container(id="pacman_root"):
            yield Static("Pac-Man Classic Mode", id="pacman_title")
            yield Static("", id="pacman_score")
            yield Static("", id="pacman_canvas")
            yield Static(
                "Arrow keys to move • Enter restart • q/esc return", id="pacman_hint"
            )

    def on_mount(self) -> None:
        self._reset_level(reset_score=False)
        self._render_board()
        self.set_interval(0.12, self._game_tick)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_restart(self) -> None:
        self._reset_level(reset_score=True)
        self._render_board()

    def action_move_up(self) -> None:
        self.next_dir = "up"

    def action_move_down(self) -> None:
        self.next_dir = "down"

    def action_move_left(self) -> None:
        self.next_dir = "left"

    def action_move_right(self) -> None:
        self.next_dir = "right"

    def _init_ghosts(self) -> None:
        self.ghosts = [
            Ghost(
                "Blinky",
                14,
                10,
                14,
                10,
                "#ff4f5e",
                mode="chase",
                released=True,
                release_tick=0,
            ),
            Ghost("Pinky", 13, 10, 13, 10, "#ff89d0", release_tick=40),
            Ghost("Inky", 14, 9, 14, 9, "#5fd8ff", release_tick=90),
            Ghost("Clyde", 15, 10, 15, 10, "#ffb36b", release_tick=140),
        ]

    def _reset_level(self, reset_score: bool) -> None:
        self.map = [list(row) for row in LEVEL]
        self.player_x = 14
        self.player_y = 16
        self.player_dir = "left"
        self.next_dir = "left"
        self._init_ghosts()
        self.tick = 0
        self.mode_timer = 0
        self.mode_cycle_index = 0
        self.global_mode = "scatter"
        self.fruit_visible = False
        self.fruit_ticks_left = 0
        self._fruit_spawned_once = False
        self._fruit_spawned_twice = False
        self.ghost_combo = 0
        self.game_over = False
        self.level_cleared = False
        self._mouth_open = True
        self._pellet_count = sum(
            row.count(PELLET) + row.count(POWER) for row in self.map
        )
        self._initial_pellet_count = self._pellet_count
        if reset_score:
            self.score = 0
            self.lives = 3

    def _game_tick(self) -> None:
        self.tick += 1
        if self.game_over:
            self._render_board()
            return

        self._mouth_open = not self._mouth_open
        self._update_global_mode()
        self._move_player()
        self._move_ghosts()
        self._update_fruit()
        self._resolve_collisions()
        self._check_level_clear()
        self._render_board()

    def _update_global_mode(self) -> None:
        # Approximate classic schedule (in ticks at 0.12 sec): 7s,20s,7s,20s,5s,20s,5s,inf
        schedule = [58, 166, 58, 166, 42, 166, 42, 99999]
        self.mode_timer += 1
        if self.mode_timer >= schedule[min(self.mode_cycle_index, len(schedule) - 1)]:
            self.mode_timer = 0
            self.mode_cycle_index = min(self.mode_cycle_index + 1, len(schedule) - 1)
            self.global_mode = "chase" if self.global_mode == "scatter" else "scatter"

    def _move_player(self) -> None:
        if self._can_move(self.player_x, self.player_y, self.next_dir, is_ghost=False):
            self.player_dir = self.next_dir

        if self._can_move(
            self.player_x, self.player_y, self.player_dir, is_ghost=False
        ):
            dx, dy = self._dir_delta(self.player_dir)
            self.player_x += dx
            self.player_y += dy
            self._wrap_player()

        tile = self._tile(self.player_x, self.player_y)
        if tile == PELLET:
            self.map[self.player_y][self.player_x] = EMPTY
            self.score += 10
            self._pellet_count -= 1
        elif tile == POWER:
            self.map[self.player_y][self.player_x] = EMPTY
            self.score += 50
            self._pellet_count -= 1
            self.ghost_combo = 0
            for ghost in self.ghosts:
                if ghost.mode not in {"home", "eaten"}:
                    ghost.mode = "frightened"
                    ghost.frightened_ticks = 75

    def _move_ghosts(self) -> None:
        for ghost in self.ghosts:
            if not ghost.released:
                if self.tick >= ghost.release_tick:
                    ghost.released = True
                    ghost.mode = self.global_mode
                else:
                    continue

            if ghost.mode == "frightened" and ghost.frightened_ticks > 0:
                ghost.frightened_ticks -= 1
                if ghost.frightened_ticks == 0:
                    ghost.mode = self.global_mode

            if ghost.mode == "eaten":
                target = (ghost.home_x, ghost.home_y)
            elif ghost.mode == "scatter":
                target = self._scatter_target(ghost.name)
            elif ghost.mode == "chase":
                target = self._chase_target(ghost)
            elif ghost.mode == "frightened":
                target = self._random_target()
            else:
                target = (ghost.home_x, ghost.home_y)

            if ghost.mode == "frightened" and self.tick % 2 == 1:
                continue

            self._step_ghost_toward(ghost, target)

            if ghost.mode == "eaten" and (ghost.x, ghost.y) == (
                ghost.home_x,
                ghost.home_y,
            ):
                ghost.mode = self.global_mode
                ghost.frightened_ticks = 0

    def _step_ghost_toward(self, ghost: Ghost, target: tuple[int, int]) -> None:
        options: list[tuple[int, int, Direction, int]] = []
        reverse_dir = self._reverse_dir(ghost.direction)
        for direction in ["up", "left", "down", "right"]:
            if ghost.mode != "frightened" and direction == reverse_dir:
                continue
            if not self._can_move(ghost.x, ghost.y, direction, is_ghost=True):
                continue
            dx, dy = self._dir_delta(direction)
            nx, ny = ghost.x + dx, ghost.y + dy
            dist = abs(target[0] - nx) + abs(target[1] - ny)
            options.append((nx, ny, direction, dist))

        if not options:
            return

        if ghost.mode == "frightened":
            nx, ny, direction, _ = random.choice(options)
        else:
            options.sort(key=lambda item: item[3])
            nx, ny, direction, _ = options[0]

        ghost.x, ghost.y = nx, ny
        ghost.direction = direction

    def _update_fruit(self) -> None:
        if not self._initial_pellet_count:
            return
        ratio = self._pellet_count / self._initial_pellet_count

        if not self._fruit_spawned_once and ratio <= 0.70:
            self._spawn_fruit()
            self._fruit_spawned_once = True
        elif not self._fruit_spawned_twice and ratio <= 0.30:
            self._spawn_fruit()
            self._fruit_spawned_twice = True

        if self.fruit_visible:
            self.fruit_ticks_left -= 1
            if (self.player_x, self.player_y) == self.fruit_pos:
                self.score += 300
                self.fruit_visible = False
            elif self.fruit_ticks_left <= 0:
                self.fruit_visible = False

    def _spawn_fruit(self) -> None:
        self.fruit_visible = True
        self.fruit_ticks_left = 80

    def _resolve_collisions(self) -> None:
        for ghost in self.ghosts:
            if (ghost.x, ghost.y) != (self.player_x, self.player_y):
                continue
            if ghost.mode == "frightened":
                ghost.mode = "eaten"
                self.ghost_combo += 1
                self.score += 200 * (2 ** (self.ghost_combo - 1))
            elif ghost.mode != "eaten":
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                self._reset_after_death()
                break

    def _reset_after_death(self) -> None:
        self.player_x = 14
        self.player_y = 16
        self.player_dir = "left"
        self.next_dir = "left"
        self.ghost_combo = 0
        for ghost in self.ghosts:
            ghost.x = ghost.home_x
            ghost.y = ghost.home_y
            ghost.mode = "home"
            ghost.released = False
            ghost.direction = "left"
            ghost.frightened_ticks = 0
        if self.ghosts:
            self.ghosts[0].released = True
            self.ghosts[0].mode = self.global_mode

    def _check_level_clear(self) -> None:
        if self._pellet_count <= 0:
            self.level_cleared = True
            self.game_over = True

    def _can_move(self, x: int, y: int, direction: Direction, is_ghost: bool) -> bool:
        dx, dy = self._dir_delta(direction)
        nx, ny = x + dx, y + dy

        # player tunnel wrap openings
        if not is_ghost and ny == 10 and (nx < 0 or nx >= self.width):
            return True

        if ny < 0 or ny >= self.height or nx < 0 or nx >= self.width:
            return False

        tile = self.map[ny][nx]
        if tile == WALL:
            return False
        if tile == GATE and not is_ghost:
            return False
        return True

    def _wrap_player(self) -> None:
        if self.player_y == 10 and self.player_x < 0:
            self.player_x = self.width - 1
        elif self.player_y == 10 and self.player_x >= self.width:
            self.player_x = 0

    @staticmethod
    def _dir_delta(direction: Direction) -> tuple[int, int]:
        if direction == "up":
            return (0, -1)
        if direction == "down":
            return (0, 1)
        if direction == "left":
            return (-1, 0)
        return (1, 0)

    @staticmethod
    def _reverse_dir(direction: Direction) -> Direction:
        return {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left",
        }[
            direction
        ]  # type: ignore[return-value]

    def _scatter_target(self, ghost_name: str) -> tuple[int, int]:
        targets = {
            "Blinky": (self.width - 2, 1),
            "Pinky": (1, 1),
            "Inky": (self.width - 2, self.height - 2),
            "Clyde": (1, self.height - 2),
        }
        return targets.get(ghost_name, (self.width - 2, 1))

    def _chase_target(self, ghost: Ghost) -> tuple[int, int]:
        if ghost.name == "Blinky":
            return (self.player_x, self.player_y)

        px, py = self.player_x, self.player_y
        dx, dy = self._dir_delta(self.player_dir)

        if ghost.name == "Pinky":
            return (px + dx * 4, py + dy * 4)

        if ghost.name == "Inky":
            blinky = self.ghosts[0]
            ax, ay = (px + dx * 2, py + dy * 2)
            vx, vy = (ax - blinky.x, ay - blinky.y)
            return (ax + vx, ay + vy)

        # Clyde
        distance = abs(ghost.x - px) + abs(ghost.y - py)
        if distance > 8:
            return (px, py)
        return self._scatter_target("Clyde")

    def _random_target(self) -> tuple[int, int]:
        return (random.randint(1, self.width - 2), random.randint(1, self.height - 2))

    def _tile(self, x: int, y: int) -> str:
        if y < 0 or y >= self.height or x < 0 or x >= self.width:
            return WALL
        return self.map[y][x]

    def _render_board(self) -> None:
        overlays: dict[tuple[int, int], str] = {}
        for ghost in self.ghosts:
            glyph = "ᗣ"
            color = ghost.color
            if ghost.mode == "frightened":
                color = (
                    "#5f90ff"
                    if ghost.frightened_ticks > 20
                    else ("#ffffff" if self.tick % 4 < 2 else "#5f90ff")
                )
            if ghost.mode == "eaten":
                glyph = "◌"
                color = "#d9d9ff"
            overlays[(ghost.x, ghost.y)] = f"[bold {color}]{glyph}[/]"

        overlays[(self.player_x, self.player_y)] = (
            f"[bold #ffdd66]{self._pacman_glyph()}[/]"
        )

        rows: list[str] = []
        for y in range(self.height):
            chars: list[str] = []
            for x in range(self.width):
                if (x, y) in overlays:
                    chars.append(overlays[(x, y)])
                    continue

                base = self.map[y][x]
                if base == WALL:
                    chars.append("[bold #69549e]█[/]")
                elif base == HOUSE:
                    chars.append("[#2a213f]▒[/]")
                elif base == GATE:
                    chars.append("[bold #9f8ad9]═[/]")
                elif base == PELLET:
                    chars.append("[#c9b8ee]·[/]")
                elif base == POWER:
                    chars.append("[bold #ffffff]◉[/]")
                elif self.fruit_visible and (x, y) == self.fruit_pos:
                    chars.append("[bold #ff5d8f]◆[/]")
                else:
                    chars.append(" ")

            rows.append("".join(chars))

        if self.level_cleared:
            score_text = f"[bold #8df7b0]Level Clear![/] • Score: [bold #e7dcff]{self.score}[/] • Press Enter to restart"
        elif self.game_over:
            score_text = f"[bold #ff8fb1]Game Over[/] • Score: [bold #e7dcff]{self.score}[/] • Enter to restart"
        else:
            mode_text = (
                "FRIGHTENED"
                if any(g.mode == "frightened" for g in self.ghosts)
                else self.global_mode.upper()
            )
            fruit_text = "fruit up" if self.fruit_visible else ""
            score_text = (
                f"Score [bold #e7dcff]{self.score}[/]  "
                f"Lives [bold #e7dcff]{self.lives}[/]  "
                f"Pellets [bold #e7dcff]{self._pellet_count}[/]  "
                f"Mode [bold #e7dcff]{mode_text}[/] {fruit_text}"
            )

        self.query_one("#pacman_score", Static).update(score_text)
        self.query_one("#pacman_canvas", Static).update("\n".join(rows))

    def _pacman_glyph(self) -> str:
        if not self._mouth_open:
            return "●"
        return {
            "left": "ᗤ",
            "right": "ᗧ",
            "up": "ᗢ",
            "down": "ᗣ",
        }[self.player_dir]
