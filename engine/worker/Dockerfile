# Fly.io worker: triggers daily market update via HTTP
# Build from engine/ with: fly deploy --config worker/fly.toml
FROM python:3.12-slim

WORKDIR /app

# Copy entire engine (parent of worker/)
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

ENV PORT=8080
CMD ["python", "worker/server.py"]
