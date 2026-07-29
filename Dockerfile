FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_PROGRESS_BAR=off

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --retries 10 --timeout 120 --progress-bar off -r /app/requirements.txt

COPY . /app

EXPOSE 8000

ENTRYPOINT ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
