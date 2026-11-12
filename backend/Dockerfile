FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 120 --retries 5 -r requirements.txt
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
COPY requirements-dev.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 120 --retries 5 -r requirements-dev.txt
COPY tests ./tests
CMD ["pytest", "-q"]

FROM runtime AS production
