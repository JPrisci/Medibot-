#!/usr/bin/env python3
"""
Cute Robot Motion & Face Display

This script controls a robot's movement using ROS 2 and displays an animated
"cute" face in a fullscreen pygame window. It blends robot motion phases with
facial expressions, including blinking, reacting to hazards, and different
"story" behaviours.
"""

import os
import sys

import pygame

username = "User"
# Placeholder stats
time_elapsed = 3
time_remaining = 5


# ────────────────────────────────────────────────────────────────────────────────
# Pygame face UI
# ────────────────────────────────────────────────────────────────────────────────
def load_faces(screen):
    """Load and scale face images from folder."""
    w, h = screen.get_size()
    folder = "Expressions"  # Adjust path as needed

    def L(name):
        return pygame.transform.scale(pygame.image.load(os.path.join(folder, name)), (w, h))

    faces = {
        "happy": L("Happy_Affection.png"),
    }
    # Mapping from robot state to default face
    face_map = {
        "HAPPY": faces["happy"],
    }
    return faces, face_map

def main():
    # ────────── Pygame setup ──────────
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Cute Robot Face")
    clock = pygame.time.Clock()
    faces, face_map = load_faces(screen)

    w, h = screen.get_size()
    font = pygame.font.SysFont(None, 60)
    def btn(text, rect, col=(100,200,100)):
        """Draw rounded rectangle button with text."""
        pygame.draw.rect(screen, col, rect, border_radius=15)
        label = font.render(text, True, (0,0,0))
        screen.blit(label, label.get_rect(center=rect.center))

    paused = False
    running = True
    
    # Face
    face = face_map["HAPPY"] 
    # Screen states

    start_rect = pygame.Rect(w//2 - w//4, h//2 - 50, w//2, 100)
    intro_rect = pygame.Rect(w//2 - w//4, h//2 - 50, w//2, 100)
    main_rect = pygame.Rect(w//2 - w//4, h//2 - 50, w//2, 100)
    stats_rect = pygame.Rect(w//2 - w//4, h//2 - 250, w//2, 100)

    # Pause/Resume button — bottom-right corner
    toggle_rect = pygame.Rect(0, 0, 200, 50)
    toggle_rect.bottomright = (w - 20, h - 20)

    # Screen-toggle button (View Stats / Back to Main) — stacked just below the pause button
    nav_rect = pygame.Rect(0, 0, 200, 50)
    nav_rect.bottomright = (w - 20, toggle_rect.top - 10)

    # Terminate Session button — only shown/clickable while paused
    exit_rect = pygame.Rect(0, 0, 220, 60)
    exit_rect.center = (w // 2, h // 2 + 100)

    screen_state = "INTRO"  # Possible states: INTRO, MAIN, STATS

    # ────────── Main UI loop ──────────
    while running:
        clock.tick(60)
        
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if screen_state == "INTRO":
                    screen_state = "MAIN"
                elif screen_state == "MAIN":
                    if paused:
                        if toggle_rect.collidepoint(e.pos):
                            paused = False
                        elif exit_rect.collidepoint(e.pos):
                            running = False
                    else:
                        if toggle_rect.collidepoint(e.pos):
                            paused = True
                        elif nav_rect.collidepoint(e.pos):
                            screen_state = "STATS"
                elif screen_state == "STATS":
                    if paused:
                        if toggle_rect.collidepoint(e.pos):
                            paused = False
                        elif exit_rect.collidepoint(e.pos):
                            running = False
                    else:
                        if toggle_rect.collidepoint(e.pos):
                            paused = True
                        elif nav_rect.collidepoint(e.pos):
                            screen_state = "MAIN"

        # ────────── Draw ──────────
    
        screen.fill((255, 255, 255))  # Clear screen with white
        
        if screen_state == "INTRO":
            # Welcomes User, Prompts Star
            pygame.draw.rect(screen, (200, 200, 255), intro_rect, border_radius=15)
            btn(f"Hi {username}!", intro_rect, (200, 200, 255))
            btn("Tap to Start Route", start_rect, (200, 255, 200))
        
        elif screen_state == "MAIN":
            # Main screen with face and toggle button
            screen.blit(face, (0, 0))  # Draw face
            btn("Pause", toggle_rect)
            btn("Route", nav_rect)
 
            if paused:
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180))
                screen.blit(overlay, (0, 0))
                label = font.render("Paused", True, (255, 255, 255))
                screen.blit(label, label.get_rect(center=(w // 2, h // 2)))
                btn("Resume", toggle_rect, (200, 100, 100))
                btn("Terminate", exit_rect, (150, 30, 30))
            
        elif screen_state == "STATS":
            # Display stats
            pygame.draw.rect(screen, (255, 255, 200), stats_rect, border_radius=15)
            btn("Stats Screen", stats_rect, (255, 255, 200))
            
            # Display placeholder stats
            time_label = font.render(f"Time Elapsed: {time_elapsed} seconds", True, (0, 0, 0))
            # Display time remaining
            remaining_label = font.render(f"Time Remaining: {time_remaining} seconds", True, (0, 0, 0))
            screen.blit(time_label, (w // 2 - time_label.get_width() // 2, h // 2 - 100))
            screen.blit(remaining_label, (w // 2 - remaining_label.get_width() // 2, h // 2 - 50))
            
            btn("Pause", toggle_rect)
            btn("Main", nav_rect)
            
            if paused:
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180))
                screen.blit(overlay, (0, 0))
                label = font.render("Paused", True, (255, 255, 255))
                screen.blit(label, label.get_rect(center=(w // 2, h // 2)))
                btn("Resume", toggle_rect, (200, 100, 100))
                btn("Terminate", exit_rect, (150, 30, 30))
 
        pygame.display.flip()

    pygame.display.flip()  # Update the display
    # ────────── Cleanup ──────────
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()