FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# Dependențe runtime pentru Pygame / SDL2 pe Debian (bookworm/slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglu1-mesa \
    libgles2 \
    libegl1 \
    libsdl2-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 \
    libsdl2-ttf-2.0-0 \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    libx11-6 libxext6 libxrender1 libxcursor1 libxrandr2 libxinerama1 libxi6 libxxf86vm1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# pornește jocul (schimbă numele dacă fișierul e altul)
CMD ["python", "snake_game.py"]
