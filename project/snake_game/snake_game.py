#!/usr/bin/env python3
"""
Async Snake (clean + name screen + robust retry/exit)

Features:
- Grid-locked movement and spawning (CELL-sized steps)
- Normal fruit: grow at head (+10)
- Bonus (async) fruit: grow at tail (+50)
- Head visuals rotate with direction
- Friendly visuals: checkerboard board, rounded segments, glossy apple, star bonus
- Startup Name screen -> used for leaderboard
- Game Over screen: R = retry (same name), Esc = quit
- Optional score submit to API_URL (FastAPI) via httpx

Env:
  API_URL=http://api:8000
"""

import os
import asyncio
import random
from math import cos, sin, pi
from datetime import datetime

import pygame
import httpx

# -----------------------------
# Config & Grid Mapping
# -----------------------------
WIDTH, HEIGHT = 1200, 800
CELL = 20  # snap size (all positions in grid units)
GRID_W = WIDTH // CELL
GRID_H = HEIGHT // CELL

SNAKE_FPS = 12  # grid steps per second
API_URL = os.getenv("API_URL", "http://api:8000")

# -----------------------------
# Friendly Palette
# -----------------------------
BG_A = (28, 33, 43)        # dark blue-gray
BG_B = (30, 36, 48)        # slightly lighter tile
HUD_BG = (245, 247, 252)   # HUD pill background
HUD_TEXT = (32, 40, 56)

SNAKE_BODY = (90, 214, 134)
SNAKE_BODY_2 = (80, 190, 120)
SNAKE_HEAD = (64, 196, 120)

APPLE = (232, 76, 61)
LEAF = (76, 175, 80)
HIGHLIGHT = (255, 255, 255, 120)

BONUS = (252, 196, 25)

GRID_LINES = (44, 51, 66)
SHOW_GRID_LINES = False  # set True if you want grid lines over checkerboard

# -----------------------------
# Pygame init
# -----------------------------
pygame.init()
window = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Async Snake — Clean Grid")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 28)
small_font = pygame.font.SysFont("consolas", 20)
title_font = pygame.font.SysFont("consolas", 48)

# -----------------------------
# Helpers (draw & grid)
# -----------------------------
def grid_to_rect(cell_xy):
    """(gx, gy) -> pixel rect tuple (x, y, w, h)"""
    gx, gy = cell_xy
    return (gx * CELL, gy * CELL, CELL, CELL)

def random_free_cell(occupied: set[tuple[int, int]]):
    """Return a free (x, y) tuple on the grid, or None if full."""
    free = [(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in occupied]
    return random.choice(free) if free else None

def draw_text(screen, msg, center_xy, color=HUD_TEXT, fnt=font):
    surf = fnt.render(msg, True, color)
    rect = surf.get_rect(center=center_xy)
    screen.blit(surf, rect)

def draw_checkerboard(screen):
    """Subtle checkerboard background; optionally overlay faint grid lines."""
    screen.fill(BG_A)
    tile = pygame.Surface((CELL, CELL))
    tile.fill(BG_B)
    for y in range(GRID_H):
        start = y % 2
        for x in range(start, GRID_W, 2):
            screen.blit(tile, (x * CELL, y * CELL))
    if SHOW_GRID_LINES:
        for x in range(0, WIDTH, CELL):
            pygame.draw.line(screen, GRID_LINES, (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, CELL):
            pygame.draw.line(screen, GRID_LINES, (0, y), (WIDTH, y))

def draw_rounded_rect(surface, rect, color, radius=8):
    pygame.draw.rect(surface, color, rect, border_radius=radius)

def draw_shadow_rect(surface, rect, radius=8, offset=(2, 2), alpha=55):
    shadow = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, alpha), (0, 0, rect[2], rect[3]), border_radius=radius)
    surface.blit(shadow, (rect[0] + offset[0], rect[1] + offset[1]))

def draw_snake_segment(surface, cell_xy, color, is_head=False, direction=None):
    x, y, w, h = grid_to_rect(cell_xy)
    r = 8
    draw_shadow_rect(surface, (x, y, w, h), radius=r)
    draw_rounded_rect(surface, (x, y, w, h), color, radius=r)

    if not is_head:
        return

    # Directional “snout” triangle + eyes positioned by direction
    cx, cy = x + w // 2, y + h // 2
    tip = {
        "UP":    (cx, y + 2),
        "DOWN":  (cx, y + h - 2),
        "LEFT":  (x + 2, cy),
        "RIGHT": (x + w - 2, cy),
    }[(direction or "RIGHT")]
    if direction in ("UP", "DOWN"):
        base_left  = (cx - w * 0.20, cy)
        base_right = (cx + w * 0.20, cy)
    else:
        base_left  = (cx, cy - h * 0.20)
        base_right = (cx, cy + h * 0.20)
    pygame.draw.polygon(surface, color, [base_left, base_right, tip])

    eye_r = max(2, CELL // 6)
    off = CELL // 4
    if direction == "UP":
        eye1, eye2 = (x + off, y + off), (x + w - off, y + off)
    elif direction == "DOWN":
        eye1, eye2 = (x + off, y + h - off), (x + w - off, y + h - off)
    elif direction == "LEFT":
        eye1, eye2 = (x + off, y + off), (x + off, y + h - off)
    else:  # RIGHT
        eye1, eye2 = (x + w - off, y + off), (x + w - off, y + h - off)
    for e in (eye1, eye2):
        pygame.draw.circle(surface, (255, 255, 255), e, eye_r)
        pygame.draw.circle(surface, (0, 0, 0), e, max(1, eye_r // 2))

def draw_apple(surface, cell_xy):
    x, y, w, h = grid_to_rect(cell_xy)
    cx = x + w // 2
    cy = y + h // 2
    radius = int(CELL * 0.42)
    pygame.draw.circle(surface, APPLE, (cx, cy), radius)

    # leaf
    leaf_w = int(CELL * 0.3)
    leaf_h = int(CELL * 0.18)
    leaf_rect = pygame.Rect(cx + radius // 2 - leaf_w // 2, y + h // 6, leaf_w, leaf_h)
    draw_rounded_rect(surface, leaf_rect, LEAF, radius=leaf_h // 2)

    # highlight
    gloss = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.circle(gloss, HIGHLIGHT, (int(w * 0.35), int(h * 0.35)), int(CELL * 0.18))
    surface.blit(gloss, (x, y))

def draw_star(surface, cell_xy, color=BONUS, points=5, inner_ratio=0.46):
    x, y, w, h = grid_to_rect(cell_xy)
    cx = x + w / 2
    cy = y + h / 2
    R = CELL * 0.45
    r = R * inner_ratio
    verts = []
    for i in range(points * 2):
        angle = i * pi / points - pi / 2
        rad = R if i % 2 == 0 else r
        verts.append((cx + rad * cos(angle), cy + rad * sin(angle)))
    pygame.draw.polygon(surface, color, verts)

    gloss = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.circle(gloss, HIGHLIGHT, (int(w * 0.40), int(h * 0.35)), int(CELL * 0.16))
    surface.blit(gloss, (x, y))

def hud_pill(surface, score):
    pill_h = 44
    pill_w = 240
    pill_x = 20
    pill_y = 14
    draw_rounded_rect(surface, (pill_x, pill_y, pill_w, pill_h), HUD_BG, radius=22)
    draw_text(surface, f"Score: {score}", (pill_x + pill_w // 2, pill_y + pill_h // 2), HUD_TEXT, font)

# -----------------------------
# Async API
# -----------------------------
async def submit_score(player_name: str, final_score: int):
    if not API_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{API_URL}/scores/",
                json={"player": player_name, "score": final_score, "date": datetime.now().isoformat()},
            )
    except Exception:
        # keep game responsive even if API is down
        pass

# -----------------------------
# Async bonus spawner
# -----------------------------
async def spawn_bonus_food(state: dict):
    """
    Periodically spawns a bonus fruit at a free grid cell for a short time.
    Uses only grid cells and never overlaps the snake or normal fruit.
    """
    while state["running"]:
        await asyncio.sleep(random.randint(5, 12))
        if not state["running"]:
            break

        occupied = set(map(tuple, state["snake_body"]))
        if state["fruit"] is not None:
            occupied.add(tuple(state["fruit"]))
        pos = random_free_cell(occupied)
        if pos is None:
            continue

        state["bonus_fruit"] = pos
        state["bonus_visible"] = True

        await asyncio.sleep(6)  # visible window

        state["bonus_visible"] = False
        state["bonus_fruit"] = None

# -----------------------------
# Name screen
# -----------------------------
async def name_screen() -> str | None:
    """
    Draws a name input screen.
    Return player's name (str) on Enter, or None if user presses Esc/closes window.
    """
    name = ""
    caret_on = True
    caret_timer = 0

    input_w, input_h = 500, 60
    input_x = (WIDTH - input_w) // 2
    input_y = (HEIGHT // 2)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_RETURN:
                    # accept non-empty name; else keep asking
                    return name.strip() or "Player"
                elif event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                else:
                    ch = event.unicode
                    if ch.isprintable() and len(name) < 18:
                        name += ch

        # blink caret
        caret_timer = (caret_timer + 1) % 40
        caret_on = caret_timer < 20

        # render
        draw_checkerboard(window)
        draw_text(window, "SNAKE", (WIDTH // 2, HEIGHT // 2 - 140), HUD_TEXT, title_font)
        draw_text(window, "Enter your name", (WIDTH // 2, HEIGHT // 2 - 80), HUD_TEXT, font)

        # input box
        box_rect = pygame.Rect(input_x, input_y, input_w, input_h)
        draw_shadow_rect(window, (box_rect.x, box_rect.y, box_rect.w, box_rect.h), radius=14, alpha=65)
        pygame.draw.rect(window, HUD_BG, box_rect, border_radius=14)

        # name text + caret
        shown = name if name else ""
        text_surf = font.render(shown, True, HUD_TEXT)
        window.blit(text_surf, (box_rect.x + 16, box_rect.y + (input_h - text_surf.get_height()) // 2))

        if caret_on:
            cx = box_rect.x + 16 + text_surf.get_width() + 3
            cy1 = box_rect.y + 14
            cy2 = box_rect.y + input_h - 14
            pygame.draw.line(window, HUD_TEXT, (cx, cy1), (cx, cy2), 2)

        draw_text(window, "Press Enter to continue • Esc to quit",
                  (WIDTH // 2, HEIGHT // 2 + 80), HUD_TEXT, small_font)

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)

# -----------------------------
# Core game
# -----------------------------
async def game_loop(player_name="Player") -> str:
    """
    Returns:
      'retry' if user pressed R on game over,
      'quit'  if user pressed Esc or closed.
    """
    # snake initial state (length 3, centered)
    head = (GRID_W // 2, GRID_H // 2)
    snake_body: list[tuple[int, int]] = [head, (head[0]-1, head[1]), (head[0]-2, head[1])]
    direction = "RIGHT"
    pending_direction = "RIGHT"

    # fruit (normal)
    fruit = random_free_cell(set(snake_body))
    score = 0
    running = True

    # shared state for async task
    state = {
        "running": True,
        "snake_body": snake_body,
        "fruit": fruit,
        "bonus_fruit": None,
        "bonus_visible": False,
    }

    bonus_task = asyncio.create_task(spawn_bonus_food(state))

    try:
        while running:
            # ---------- input ----------
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w) and direction != "DOWN":
                        pending_direction = "UP"
                    elif event.key in (pygame.K_DOWN, pygame.K_s) and direction != "UP":
                        pending_direction = "DOWN"
                    elif event.key in (pygame.K_LEFT, pygame.K_a) and direction != "RIGHT":
                        pending_direction = "LEFT"
                    elif event.key in (pygame.K_RIGHT, pygame.K_d) and direction != "LEFT":
                        pending_direction = "RIGHT"
                    elif event.key == pygame.K_ESCAPE:
                        # Exit immediately from gameplay
                        state["running"] = False
                        return "quit"

            direction = pending_direction

            # ---------- update (one grid step) ----------
            hx, hy = snake_body[0]
            #if direction == "UP":
            #    new_head = (hx, (hy - 1) % GRID_H)
            #elif direction == "DOWN":
            #    new_head = (hx, (hy + 1) % GRID_H)
            #elif direction == "LEFT":
            #    new_head = ((hx - 1) % GRID_W, hy)
            #else:  # RIGHT
            #    new_head = ((hx + 1) % GRID_W, hy)

            if direction == "UP":
                new_head = (hx, hy - 1)
            elif direction == "DOWN":
                new_head = (hx, hy + 1)
            elif direction == "LEFT":
                new_head = (hx - 1, hy)
            else:  # RIGHT
                new_head = (hx + 1, hy)

            # check wall collision
            if (
                new_head[0] < 0 or new_head[0] >= GRID_W or
                new_head[1] < 0 or new_head[1] >= GRID_H
            ):
                state["running"] = False
                return await game_over(player_name, score)


            # insert new head
            snake_body.insert(0, new_head)

            # normal fruit collision (grow at head)
            if state["fruit"] is not None and new_head == tuple(state["fruit"]):
                score += 10
                occupied = set(map(tuple, snake_body))
                state["fruit"] = random_free_cell(occupied)
            else:
                # keep length: drop tail
                snake_body.pop()

            # bonus fruit collision (grow TAIL)
            if state["bonus_visible"] and state["bonus_fruit"] is not None and new_head == tuple(state["bonus_fruit"]):
                score += 50
                state["bonus_visible"] = False
                state["bonus_fruit"] = None

                # extend one cell in tail's direction
                if len(snake_body) >= 2:
                    tail_end = snake_body[-1]
                    before_tail = snake_body[-2]
                    dx = tail_end[0] - before_tail[0]
                    dy = tail_end[1] - before_tail[1]
                    dx = 0 if dx == 0 else (1 if dx > 0 else -1)
                    dy = 0 if dy == 0 else (1 if dy > 0 else -1)
                else:
                    # fallback: opposite to head direction
                    if direction == "UP":
                        dx, dy = 0, 1
                    elif direction == "DOWN":
                        dx, dy = 0, -1
                    elif direction == "LEFT":
                        dx, dy = 1, 0
                    else:
                        dx, dy = -1, 0


                tail_base = snake_body[-1]
                new_tail = ((tail_base[0] + dx) % GRID_W, (tail_base[1] + dy) % GRID_H)
                if new_tail not in snake_body:
                    snake_body.append(new_tail)

            # self-collision ends game
            # self-collision ends game (go to Game Over screen)
            if new_head in snake_body[1:]:
                state["running"] = False
                return await game_over(player_name, score)


            # ---------- render ----------
            draw_checkerboard(window)
            # fruits
            if state["fruit"] is not None:
                draw_apple(window, state["fruit"])
            if state["bonus_visible"] and state["bonus_fruit"] is not None:
                draw_star(window, state["bonus_fruit"], color=BONUS)
            # snake
            for i, cell in enumerate(snake_body):
                color = SNAKE_HEAD if i == 0 else (SNAKE_BODY if i % 2 == 0 else SNAKE_BODY_2)
                draw_snake_segment(window, cell, color, is_head=(i == 0), direction=(direction if i == 0 else None))
            # HUD
            hud_pill(window, score)

            pygame.display.flip()
            clock.tick(SNAKE_FPS)
            await asyncio.sleep(0)  # yield to async tasks

    finally:
        state["running"] = False
        bonus_task.cancel()
        try:
            await bonus_task
        except Exception:
            pass

    # Game ended: show game over screen and return user choice
    return await game_over(player_name, score)

# -----------------------------
# Game Over
# -----------------------------
async def game_over(player_name, score) -> str:
    # submit score, but do not block gameplay responsiveness on failure
    await submit_score(player_name, score)

    # dim board
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    window.blit(overlay, (0, 0))

    # centered panel
    panel_w, panel_h = 520, 240
    panel_x = (WIDTH - panel_w) // 2
    panel_y = (HEIGHT - panel_h) // 2
    draw_rounded_rect(window, (panel_x, panel_y, panel_w, panel_h), HUD_BG, radius=20)

    draw_text(window, "GAME OVER", (panel_x + panel_w // 2, panel_y + 60))
    draw_text(window, f"Final Score: {score}", (panel_x + panel_w // 2, panel_y + 100), fnt=small_font)
    draw_text(window, "Press R to retry • Esc to quit", (panel_x + panel_w // 2, panel_y + 150), fnt=small_font)
    pygame.display.flip()

    # wait for user choice
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return "retry"
                elif event.key == pygame.K_ESCAPE:
                    return "quit"
        await asyncio.sleep(0.01)

# -----------------------------
# Entrypoint
# -----------------------------
async def main():
    # Name screen
    name = await name_screen()
    if name is None:
        pygame.quit()
        return

    # Gameplay loop with retry support
    while True:
        result = await game_loop(name)
        if result == "retry":
            continue   # restart game with same name
        else:
            break      # "quit" or window close

    pygame.quit()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pygame.quit()
