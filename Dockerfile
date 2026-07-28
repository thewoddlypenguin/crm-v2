# ─── Stage 1: Build frontend ───────────────────────────────────────────────
FROM node:22-slim AS frontend-build
WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

COPY . .
RUN npm run build

# ─── Stage 2: Python backend + built frontend ─────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY . .
RUN pip install .

COPY --from=frontend-build /app/dist ./dist

EXPOSE 8000

CMD ["uvicorn", "app:asgi", "--host", "0.0.0.0", "--port", "8000"]
