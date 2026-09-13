#!/usr/bin/env python3
"""Click-through visual review for every NaviBot face-screen state.

Run from this folder with ``py test_faces.py``. This does not connect to the
Coordinator or control a robot. Click the left/right arrow circles (or use the
left/right arrow keys) to cycle through the screens. Press Escape to close.
"""

from __future__ import annotations

from pathlib import Path

import pygame


WHITE = (255, 255, 255)
INK = (0, 0, 0)
BLUE = (21, 101, 192)
GREEN = (120, 220, 140)
PALE_BLUE = (190, 220, 255)
ERROR = (180, 20, 20)
WINDOW_SIZE = (1280, 720)
CONNECTION_FALLBACK = (
    "Please stand by while NaviBot tries to reconnect."
)
CALL_STAFF_LABEL = "Call staff - we'll be with you shortly"


def load_face(screen: pygame.Surface) -> pygame.Surface:
    """Load the same face asset used by faces.py."""
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
    """Draw a centred paragraph without allowing it to run off-screen."""
    lines: list[str] = []
    line = ""
    for word in text.split():
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


def draw_arrow_button(screen: pygame.Surface, centre: tuple[int, int], direction: int) -> pygame.Rect:
    """Draw a text-free previous/next control so the face has name-only text."""
    button = pygame.Rect(0, 0, 54, 54)
    button.center = centre
    pygame.draw.circle(screen, WHITE, button.center, 27)
    pygame.draw.circle(screen, BLUE, button.center, 27, width=3)
    x, y = button.center
    points = [(x + (10 * direction), y), (x - (8 * direction), y - 12), (x - (8 * direction), y + 12)]
    pygame.draw.polygon(screen, BLUE, points)
    return button


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("NaviBot face-screen review")
    clock = pygame.time.Clock()
    heading_font = pygame.font.SysFont(None, 62)
    body_font = pygame.font.SysFont(None, 42)
    staff_font = pygame.font.SysFont(None, 34)
    name_font = pygame.font.SysFont(None, 48)
    face = load_face(screen)
    width, height = screen.get_size()
    continue_button = pygame.Rect(width // 8, height * 3 // 4, width * 3 // 4, 86)
    destination_button = pygame.Rect(width // 3, height * 3 // 4, width // 3, 78)

    # These match the states that faces.py can show.
    states = (
        "Face with participant name",
        "Jarvis elevator instruction",
        "Gem ready prompt",
        "Gem continuing message",
        "Destination reached",
        "Idle",
        "Reconnecting",
        "Connection needs staff",
    )
    idle_state = states.index("Idle")
    selected = 0
    running = True

    while running:
        clock.tick(30)
        previous = draw_arrow_button(screen, (42, height // 2), -1)
        next_button = draw_arrow_button(screen, (width - 42, height // 2), 1)

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
                selected = (selected + 1) % len(states)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
                selected = (selected - 1) % len(states)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if next_button.collidepoint(event.pos):
                    selected = (selected + 1) % len(states)
                elif previous.collidepoint(event.pos):
                    selected = (selected - 1) % len(states)
                elif (
                    states[selected] == "Destination reached"
                    and destination_button.collidepoint(event.pos)
                ):
                    selected = idle_state

        screen.fill(WHITE)
        state = states[selected]
        if state == "Destination reached":
            draw_wrapped_text(
                screen,
                "You have reached your destination.",
                heading_font,
                INK,
                (width // 2, height // 2),
                width - 220,
            )
            pygame.draw.rect(screen, GREEN, destination_button, border_radius=18)
            label = body_font.render("Confirm", True, INK)
            screen.blit(label, label.get_rect(center=destination_button.center))
        elif state == "Idle":
            draw_wrapped_text(screen, "Idle", heading_font, INK, (width // 2, height // 2), width - 160)
        elif state == "Face with participant name":
            screen.blit(face, (0, 0))
            name = name_font.render("Taylor", True, INK)
            screen.blit(name, name.get_rect(midtop=(width // 2, 28)))
        elif state == "Jarvis elevator instruction":
            draw_wrapped_text(
                screen,
                "Please enter the elevator. Press the button for the second floor. A second NaviBot, Gem, will meet you to continue your route.",
                heading_font,
                INK,
                (width // 2, height // 2),
                width - 220,
            )
        elif state == "Gem ready prompt":
            pygame.draw.rect(screen, GREEN, continue_button, border_radius=18)
            label = body_font.render("Ready to follow NaviBot?", True, INK)
            screen.blit(label, label.get_rect(center=continue_button.center))
        elif state == "Gem continuing message":
            pygame.draw.rect(screen, PALE_BLUE, continue_button, border_radius=18)
            label = body_font.render("Continuing your route...", True, INK)
            screen.blit(label, label.get_rect(center=continue_button.center))
        elif state == "Reconnecting":
            draw_wrapped_text(
                screen,
                CONNECTION_FALLBACK,
                body_font,
                ERROR,
                (width // 2, height // 2),
                width - 220,
            )
        else:
            draw_wrapped_text(
                screen,
                CONNECTION_FALLBACK,
                body_font,
                ERROR,
                (width // 2, height // 2),
                width - 220,
            )
            pygame.draw.rect(screen, PALE_BLUE, continue_button, border_radius=18)
            label = staff_font.render(CALL_STAFF_LABEL, True, INK)
            screen.blit(label, label.get_rect(center=continue_button.center))

        # Re-draw controls after the screen content so they remain clickable.
        draw_arrow_button(screen, (42, height // 2), -1)
        draw_arrow_button(screen, (width - 42, height // 2), 1)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
