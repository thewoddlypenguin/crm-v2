# ─── Stage 1: Build frontend ───────────────────────────────────────────────
FROM node:22-slim AS frontend-build
WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

COPY index.html postcss.config.js tailwind.config.js tsconfig*.json vite.config.ts ./
COPY src/ src/

RUN npm run build

# ─── Stage 2: Python backend + built frontend ─────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install uv && uv sync --no-dev

# Copy backend code
COPY app.py db.py models.py auth.py business.py routes.py seed.py ./

# Copy built frontend from stage 1
COPY --from=frontend-build /app/dist ./dist

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "app:asgi", "--host", "0.0.0.0", "--port", "8000"]
