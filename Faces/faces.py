#!/usr/bin/env python3
"""Robot face display with NaviBot handover integration.

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
    """Load and scale the default face relative to this file, not the CWD."""
    image_path = Path(__file__).parent / "Expressions" / "Happy_Affection.png"
    image = pygame.image.load(str(image_path))
    return pygame.transform.scale(image, screen.get_size())


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


def is_task_complete(state: dict) -> bool:
    """Return true once the Coordinator reports that guidance has finished."""
    return (
        str(state.get("current_stage", "")).strip() == "task_complete"
        or str(state.get("state", "")).strip() == "task_complete"
    )


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
    pygame.display.set_caption(f"NaviBot {arguments.role.title()} Face")
    clock = pygame.time.Clock()
    face = load_face(screen)
    width, height = screen.get_size()
    heading_font = pygame.font.SysFont(None, 64)
    button_font = pygame.font.SysFont(None, 48)
    continue_button = pygame.Rect(width // 8, height * 3 // 4, width * 3 // 4, 92)
    destination_button = pygame.Rect(width // 3, height * 3 // 4, width // 3, 78)

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
    destination_started_at: float | None = None
    destination_confirmed = False
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
        task_complete = is_task_complete(state)
        if task_complete and destination_started_at is None:
            destination_started_at = time.monotonic()
        elif not task_complete:
            destination_started_at = None
            destination_confirmed = False

        destination_timed_out = (
            destination_started_at is not None
            and time.monotonic() - destination_started_at >= 10
        )

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
            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and task_complete
                and not destination_confirmed
                and destination_button.collidepoint(event.pos)
            ):
                destination_confirmed = True

        screen.fill((255, 255, 255))
        if task_complete and not destination_confirmed and not destination_timed_out:
            draw_wrapped_text(
                screen,
                "You have arrived at the Fashion department.",
                heading_font,
                (0, 0, 0),
                (width // 2, height // 2),
                width * 3 // 4,
            )
            pygame.draw.rect(screen, (120, 220, 140), destination_button, border_radius=18)
            confirmed_label = button_font.render("Confirm", True, (0, 0, 0))
            screen.blit(confirmed_label, confirmed_label.get_rect(center=destination_button.center))
        elif not booking_active or task_complete:
            idle_label = heading_font.render("Idle", True, (0, 0, 0))
            screen.blit(idle_label, idle_label.get_rect(center=(width // 2, height // 2)))
        elif not at_handover and not error_message:
            screen.blit(face, (0, 0))
            name_label = button_font.render(user_id, True, (0, 0, 0))
            screen.blit(name_label, name_label.get_rect(midtop=(width // 2, 28)))

        if booking_active and at_handover and arguments.role == "jarvis":
            draw_wrapped_text(
                screen,
                "Please enter the elevator. NaviBot will meet you upstairs.",
                heading_font,
                (0, 0, 0),
                (width // 2, height * 3 // 4),
                width * 3 // 4,
            )
        elif booking_active and at_handover and arguments.role == "gem":
            if continue_requested:
                message = "Continuing your route…"
                button_colour = (190, 220, 255)
            else:
                message = "Ready to follow NaviBot?"
                button_colour = (120, 220, 140)
            pygame.draw.rect(screen, button_colour, continue_button, border_radius=18)
            rendered = button_font.render(message, True, (0, 0, 0))
            screen.blit(rendered, rendered.get_rect(center=continue_button.center))

        if error_message:
            draw_wrapped_text(
                screen,
                error_message,
                pygame.font.SysFont(None, 28),
                (180, 20, 20),
                (width // 2, height - 45),
                width - 40,
            )

        pygame.display.flip()

    if client is not None:
        client.close()
    pygame.quit()


if __name__ == "__main__":
    main()
