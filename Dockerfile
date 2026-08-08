FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ---- SYSTEM DEPS ----
RUN apt-get update && apt-get install -y \
    wget curl ca-certificates \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    chromium \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --frozen --no-install-project

COPY . .

RUN uv sync --no-dev --frozen

EXPOSE 8000

ENTRYPOINT ["uv", "run", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]