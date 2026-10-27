FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend
RUN apt-get update && apt-get install -y --no-install-recommends gosu ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin bodega
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY scripts ./scripts
RUN pip install --no-cache-dir .
COPY deploy/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
COPY deploy/backend-start.sh /usr/local/bin/backend-start
RUN chmod 0755 /usr/local/bin/backend-entrypoint /usr/local/bin/backend-start
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/backend-entrypoint"]
CMD ["/usr/local/bin/backend-start"]
