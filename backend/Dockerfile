FROM python:3.12-slim

WORKDIR /app

# System deps needed by psycopg2 (build from source against libpq)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run migrations, then start the server. Doing this in the entrypoint
# (rather than relying on someone remembering to run `alembic upgrade
# head` manually) is what makes the schema-change process safe to repeat
# on every deploy.
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
