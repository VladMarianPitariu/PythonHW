import pygame
import random
import asyncio
import httpx
import os
from datetime import datetime

pygame.init()

# Print working directory
print(f"Current working directory: {os.getcwd()}")


# Game settings
width, height = 1200, 800
SNAKE_IMG_SIZE = 20
GRID_WIDTH = width // SNAKE_IMG_SIZE
GRID_HEIGHT = height // SNAKE_IMG_SIZE
window = pygame.display.set_mode((width, height))
pygame.display.set_caption('Async Snake Game')

snake_body_colors = [pygame.Color(0, 255, 0), pygame.Color(255, 255, 0), pygame.Color(255, 0, 255), pygame.Color(0, 255, 255)]
snake_body_color_index = 0

# Colors
white = pygame.Color(255, 255, 255)
black = pygame.Color(0, 0, 0)
red = pygame.Color(255, 0, 0)
green = pygame.Color(0, 255, 0)
blue = pygame.Color(0, 0, 255)

fps = pygame.time.Clock()
snake_speed = 15

player_name = ""


async def switch_snake_body_color():
    global snake_body_color_index
    while True:
        await asyncio.sleep(1)
        snake_body_color_index = (snake_body_color_index + 1) % len(snake_body_colors)


async def submit_score(player_name, final_score):
    async with httpx.AsyncClient() as client:
        await client.post("http://api:8000/scores/", json={
            "player": player_name,
            "score": final_score,
            "date": datetime.now().isoformat()
        })


def get_player_name():
    input_box = pygame.Rect(width//2 - 100, height//2 - 32, 200, 50)
    color_inactive = pygame.Color('lightskyblue3')
    color_active = pygame.Color('dodgerblue2')
    color = color_inactive
    active = False
    text = ''
    font = pygame.font.Font(None, 36)
    done = False
    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                active = input_box.collidepoint(event.pos)
                color = color_active if active else color_inactive
            if event.type == pygame.KEYDOWN and active:
                if event.key == pygame.K_RETURN and text.strip() != '':
                    done = True
                elif event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                elif len(text) < 16 and event.unicode.isprintable():
                    text += event.unicode
        window.fill(black)
        txt_surface = font.render(text, True, white)
        input_box.w = max(200, txt_surface.get_width() + 10)
        window.blit(txt_surface, (input_box.x + 5, input_box.y + 10))
        pygame.draw.rect(window, color, input_box, 2)
        prompt = font.render('Enter your name:', True, white)
        window.blit(prompt, (width//2 - prompt.get_width()//2, height//2 - 70))
        pygame.display.flip()
    return text.strip()


async def game_over(score):
    await submit_score(player_name, score)
    font = pygame.font.SysFont('times new roman', 50)
    small_font = pygame.font.SysFont('times new roman', 30)
    window.fill(black)
    score_text = font.render(f'Your Score: {score}', True, red)
    retry_text = small_font.render('Press R to Retry or ESC to Quit', True, white)
    window.blit(score_text, score_text.get_rect(center=(width//2, height//3)))
    window.blit(retry_text, retry_text.get_rect(center=(width//2, height//2)))
    pygame.display.flip()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    await main()  # restart
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    quit()
        await asyncio.sleep(0.01)


async def spawn_bonus_fruit():
    global bonus_fruit_position, bonus_fruit_spawned
    while True:
        await asyncio.sleep(random.randint(5, 15))
        bonus_fruit_position = [
            random.randrange(1, (width // SNAKE_IMG_SIZE)) * SNAKE_IMG_SIZE,
            random.randrange(1, (height // SNAKE_IMG_SIZE)) * SNAKE_IMG_SIZE
        ]
        bonus_fruit_spawned = True
        await asyncio.sleep(5)
        bonus_fruit_spawned = False


async def game_loop():
    global bonus_fruit_position, bonus_fruit_spawned


    # All positions are now in grid coordinates (col, row)
    snake_position = [5, 5]
    snake_body = [[5, 5], [4, 5], [3, 5]]

    def random_grid_pos():
        return [random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1)]

    fruit_position = random_grid_pos()
    fruit_spawn = True
    bonus_fruit_spawned = False
    bonus_fruit_position = None

    current_direction = 'RIGHT'
    change_to = current_direction
    score = 0

    asyncio.create_task(spawn_bonus_fruit())

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP and current_direction != 'DOWN':
                    change_to = 'UP'
                elif event.key == pygame.K_DOWN and current_direction != 'UP':
                    change_to = 'DOWN'
                elif event.key == pygame.K_LEFT and current_direction != 'RIGHT':
                    change_to = 'LEFT'
                elif event.key == pygame.K_RIGHT and current_direction != 'LEFT':
                    change_to = 'RIGHT'

        current_direction = change_to

        # Move snake in grid
        if current_direction == 'UP':
            new_head = [snake_position[0], snake_position[1] - 1]
        elif current_direction == 'DOWN':
            new_head = [snake_position[0], snake_position[1] + 1]
        elif current_direction == 'LEFT':
            new_head = [snake_position[0] - 1, snake_position[1]]
        elif current_direction == 'RIGHT':
            new_head = [snake_position[0] + 1, snake_position[1]]

        snake_position[:] = new_head
        snake_body.insert(0, list(new_head))

        # Fruit collision (grid-based)
        if new_head == fruit_position:
            score += 10
            fruit_spawn = False
        else:
            snake_body.pop()

        # Bonus fruit collision (grid-based)
        if bonus_fruit_spawned and bonus_fruit_position and new_head == bonus_fruit_position:
            score += 50
            bonus_fruit_spawned = False

        if not fruit_spawn:
            fruit_position = random_grid_pos()
        fruit_spawn = True

        window.fill(black)

        # Draw snake (convert grid to pixel)
        for i, pos in enumerate(snake_body):
            px, py = pos[0] * SNAKE_IMG_SIZE, pos[1] * SNAKE_IMG_SIZE
            if i == 0:
                pygame.draw.rect(window, white, pygame.Rect(px, py, SNAKE_IMG_SIZE, SNAKE_IMG_SIZE))
            elif i == len(snake_body) - 1:
                pygame.draw.rect(window, blue, pygame.Rect(px, py, SNAKE_IMG_SIZE, SNAKE_IMG_SIZE))
            else:
                pygame.draw.rect(window, snake_body_colors[snake_body_color_index], pygame.Rect(px, py, SNAKE_IMG_SIZE, SNAKE_IMG_SIZE))

        # Draw fruit
        fx, fy = fruit_position[0] * SNAKE_IMG_SIZE, fruit_position[1] * SNAKE_IMG_SIZE
        pygame.draw.rect(window, white, pygame.Rect(fx, fy, SNAKE_IMG_SIZE, SNAKE_IMG_SIZE))

        # Draw bonus fruit
        if bonus_fruit_spawned and bonus_fruit_position:
            bx, by = bonus_fruit_position[0] * SNAKE_IMG_SIZE, bonus_fruit_position[1] * SNAKE_IMG_SIZE
            pygame.draw.rect(window, blue, pygame.Rect(bx, by, SNAKE_IMG_SIZE, SNAKE_IMG_SIZE))

        font = pygame.font.SysFont('times new roman', 24)
        score_text = font.render(f"Score: {score}", True, white)
        window.blit(score_text, (10, 10))

        # Game over if out of bounds (grid-based)
        if snake_position[0] < 0 or snake_position[0] >= GRID_WIDTH or snake_position[1] < 0 or snake_position[1] >= GRID_HEIGHT:
            await game_over(score)
        for block in snake_body[1:]:
            if snake_position == block:
                await game_over(score)

        pygame.display.flip()
        fps.tick(snake_speed)
        await asyncio.sleep(0)


async def main():
    asyncio.create_task(switch_snake_body_color())
    await game_loop()


if __name__ == "__main__":
    player_name = get_player_name()
    asyncio.run(main())
