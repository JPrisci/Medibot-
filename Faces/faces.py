#!/usr/bin/env python3
"""Robot face display with MediBot handover integration.

Run one copy on each robot display. The display reads the Coordinator's
``/ux-state/latest`` HTTP endpoint. When the coordinator reaches handover,
Jarvis tells the visitor to enter the elevator and Gem presents a button that
posts ``/visitor-ready`` to resume the final route.

Examples:
    python3 faces.py --role jarvis --api-base-url http://192.168.1.50:8000
    python3 faces.py --role gem --api-base-url http://192.168.1.50:8000
    python3 faces.py --role gem --demo-handover
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pygame


POLL_INTERVAL_SECONDS = 1.0
HANDOVER_STAGES = {"waiting_for_visitor_ready", "handover_ready"}
WHITE = (255, 255, 255)
INK = (35, 41, 55)
SUBTLE_INK = (94, 105, 125)
FACE_PINK = (239, 162, 198)
GREEN = (100, 205, 124)
ERROR = (180, 20, 20)


class CoordinatorClient:
    """Fetch state from, and send visitor actions to, the Coordinator API."""

    def __init__(self, api_base_url: str) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.state_queue: queue.Queue[dict] = queue.Queue(maxsize=1)
        self.action_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.error_queue: queue.Queue[str] = queue.Queue(maxsize=1)
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def request_visitor_ready(self, user_id: str) -> None:
        self.action_queue.put(("/visitor-ready", {"user_id": user_id}))

    def close(self) -> None:
        self.running = False
        self.thread.join(timeout=2)

    def _run(self) -> None:
        next_poll = 0.0
        while self.running:
            now = time.monotonic()
            if now >= next_poll:
                self._get_latest_state()
                next_poll = now + POLL_INTERVAL_SECONDS

            try:
                path, body = self.action_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self._post_json(path, body)

    def _get_latest_state(self) -> None:
        try:
            with urlopen(
                f"{self.api_base_url}/ux-state/latest", timeout=2
            ) as response:
                state = json.loads(response.read().decode("utf-8"))
            if isinstance(state, dict):
                self._put_latest(self.state_queue, state)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            self._put_latest(self.error_queue, f"Coordinator unavailable: {error}")

    def _post_json(self, path: str, body: dict) -> None:
        request = Request(
            f"{self.api_base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=4) as response:
                if not 200 <= response.status < 300:
                    raise HTTPError(
                        request.full_url, response.status, "Request failed", {}, None
                    )
        except (HTTPError, URLError, TimeoutError) as error:
            self._put_latest(self.error_queue, f"Could not continue route: {error}")

    @staticmethod
    def _put_latest(target: queue.Queue, value: object) -> None:
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        target.put_nowait(value)


def load_face(screen: pygame.Surface) -> pygame.Surface:
    """Load the default face without stretching it on different screens."""
    image_path = Path(__file__).parent / "Expressions" / "Happy_Affection.png"
    image = pygame.image.load(str(image_path))
    source_width, source_height = image.get_size()
    target_width, target_height = screen.get_size()
    scale = min(target_width / source_width, target_height / source_height)
    size = (int(source_width * scale), int(source_height * scale))
    return pygame.transform.smoothscale(image, size)


def draw_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    colour: tuple[int, int, int],
) -> None:
    """Draw a soft card used for readable text over the face."""
    shadow = rect.move(0, 7)
    pygame.draw.rect(screen, (206, 181, 193), shadow, border_radius=24)
    pygame.draw.rect(screen, colour, rect, border_radius=24)


def draw_centered_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    colour: tuple[int, int, int],
    centre: tuple[int, int],
) -> None:
    rendered = font.render(text, True, colour)
    screen.blit(rendered, rendered.get_rect(center=centre))


def draw_visitor_badge(
    screen: pygame.Surface,
    user_id: str,
    font: pygame.font.Font,
) -> None:
    """Show the active visitor in the same place on both robot displays."""
    visible_user_id = user_id if len(user_id) <= 28 else f"{user_id[:25]}..."
    label = f"Visitor: {visible_user_id}"
    rendered = font.render(label, True, INK)
    badge = rendered.get_rect()
    badge.inflate_ip(36, 20)
    badge.midtop = (screen.get_width() // 2, 24)
    pygame.draw.rect(screen, WHITE, badge, border_radius=16)
    pygame.draw.rect(screen, (220, 224, 231), badge, width=2, border_radius=16)
    screen.blit(rendered, rendered.get_rect(center=badge.center))


def draw_wrapped_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    colour: tuple[int, int, int],
    centre: tuple[int, int],
    maximum_width: int,
) -> None:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and font.size(candidate)[0] > maximum_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)

    line_height = font.get_linesize()
    top = centre[1] - (len(lines) * line_height) // 2
    for index, item in enumerate(lines):
        rendered = font.render(item, True, colour)
        screen.blit(rendered, rendered.get_rect(center=(centre[0], top + index * line_height)))


def is_handover_state(state: dict) -> bool:
    return (
        str(state.get("current_stage", "")).strip() in HANDOVER_STAGES
        or str(state.get("state", "")).strip() == "handover_ready"
    )


def has_active_booking(state: dict) -> bool:
    """Return true after the Coordinator has accepted a visitor task."""
    stage = str(state.get("current_stage", "")).strip()
    return bool(state.get("user_id")) and stage != "waiting_for_destination"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True, choices=("jarvis", "gem"))
    parser.add_argument(
        "--demo-handover",
        action="store_true",
        help="Show the handover interface locally without an API or robots.",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("MEDIBOT_API_BASE_URL"),
        help="Coordinator URL, e.g. http://192.168.1.50:8000",
    )
    arguments = parser.parse_args()
    if not arguments.api_base_url and not arguments.demo_handover:
        parser.error("--api-base-url or MEDIBOT_API_BASE_URL is required")
    return arguments


def main() -> None:
    arguments = parse_args()
    client = (
        None
        if arguments.demo_handover
        else CoordinatorClient(arguments.api_base_url)
    )

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption(f"MediBot {arguments.role.title()} Face")
    clock = pygame.time.Clock()
    face = load_face(screen)
    width, height = screen.get_size()
    heading_font = pygame.font.SysFont(None, 64)
    button_font = pygame.font.SysFont(None, 48)
    body_font = pygame.font.SysFont(None, 38)
    small_font = pygame.font.SysFont(None, 28)
    continue_button = pygame.Rect(
        width // 8,
        int(height * 0.78),
        width * 3 // 4,
        86,
    )

    state: dict = (
        {
            "state": "handover_ready",
            "current_stage": "waiting_for_visitor_ready",
            "user_id": "demo_visitor",
        }
        if arguments.demo_handover
        else {}
    )
    error_message = ""
    continue_requested = False
    running = True

    while running:
        clock.tick(30)
        try:
            while True:
                if client is None:
                    break
                state = client.state_queue.get_nowait()
                if not is_handover_state(state):
                    continue_requested = False
        except queue.Empty:
            pass
        try:
            while True:
                if client is None:
                    break
                error_message = client.error_queue.get_nowait()
                if error_message.startswith("Could not continue route"):
                    continue_requested = False
        except queue.Empty:
            pass

        user_id = str(state.get("user_id") or "visitor")
        booking_active = has_active_booking(state)
        at_handover = is_handover_state(state)

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and arguments.role == "gem"
                and booking_active
                and at_handover
                and not continue_requested
                and continue_button.collidepoint(event.pos)
            ):
                if client is not None:
                    client.request_visitor_ready(user_id)
                continue_requested = True
                error_message = ""

        screen.fill(WHITE)
        if not booking_active:
            idle_card = pygame.Rect(width // 2 - 230, height // 2 - 115, 460, 230)
            draw_panel(screen, idle_card, WHITE)
            pygame.draw.circle(screen, FACE_PINK, (width // 2, height // 2 - 45), 33)
            pygame.draw.circle(screen, GREEN, (width // 2 + 25, height // 2 - 70), 10)
            draw_centered_text(
                screen, "Idle", heading_font, INK, (width // 2, height // 2 + 25)
            )
            draw_centered_text(
                screen,
                "Waiting for a new booking",
                small_font,
                SUBTLE_INK,
                (width // 2, height // 2 + 68),
            )
        elif not at_handover:
            screen.fill(FACE_PINK)
            screen.blit(face, face.get_rect(center=(width // 2, height // 2)))

        if booking_active:
            draw_visitor_badge(screen, user_id, small_font)

        if booking_active and at_handover and arguments.role == "jarvis":
            draw_centered_text(
                screen,
                "Handover",
                body_font,
                INK,
                (width // 2, height // 2 - 72),
            )
            draw_wrapped_text(
                screen,
                "Please enter the elevator. The next robot will be waiting for you upstairs.",
                body_font,
                SUBTLE_INK,
                (width // 2, height // 2 + 10),
                width * 3 // 4,
            )
        elif booking_active and at_handover and arguments.role == "gem":
            if continue_requested:
                draw_centered_text(
                    screen,
                    "Starting your route...",
                    body_font,
                    INK,
                    (width // 2, height // 2),
                )
            else:
                draw_centered_text(
                    screen,
                    f"Waiting for {user_id}",
                    body_font,
                    INK,
                    (width // 2, height // 2 - 74),
                )
                draw_centered_text(
                    screen,
                    "to continue the route",
                    small_font,
                    SUBTLE_INK,
                    (width // 2, height // 2 - 28),
                )
                pygame.draw.rect(screen, GREEN, continue_button, border_radius=18)
                rendered = button_font.render("Continue route", True, INK)
                screen.blit(rendered, rendered.get_rect(center=continue_button.center))

        if error_message:
            error_panel = pygame.Rect(20, height - 72, width - 40, 46)
            pygame.draw.rect(screen, WHITE, error_panel, border_radius=16)
            draw_wrapped_text(
                screen,
                error_message,
                small_font,
                ERROR,
                (width // 2, height - 45),
                width - 40,
            )

        pygame.display.flip()

    if client is not None:
        client.close()
    pygame.quit()


if __name__ == "__main__":
    main()
