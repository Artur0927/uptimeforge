
FROM python:3.12-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY uptimeforge/ ./uptimeforge/

RUN pip install --no-cache-dir .


FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 \
    --gid app --no-create-home \
    --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

COPY alembic.ini ./
COPY migrations/ ./migrations/

USER app

EXPOSE 8000

CMD ["uvicorn", "uptimeforge.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]


