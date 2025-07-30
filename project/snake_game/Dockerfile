FROM python:3.12-slim

RUN apt-get update && apt-get install -y libgl1-mesa-glx

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY snake_game.py ./
COPY image.png ./
#COPY snake_body.png ./
#COPY snake_tail.png ./
#COPY snake_body.png ./



CMD ["python", "snake_game.py"]