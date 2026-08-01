FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --frozen --no-install-project

RUN uv run --no-project playwright install --with-deps chromium

COPY . .

RUN uv sync --no-dev --frozen

EXPOSE 8000

ENTRYPOINT ["uv", "run", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]