FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir numpy pytest redis

COPY . .

CMD ["python", "controller/controller.py"]
