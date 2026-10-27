# --- 1. Build the React app ---------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. Django API + static frontend --------------------------------------------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist \
    PORT=8000
WORKDIR /app/backend
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN useradd --create-home app
USER app
EXPOSE 8000
# Threads keep slow upstream calls (HERE, Open-Meteo) from blocking other requests.
CMD gunicorn config.wsgi --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 60 --access-logfile -
