#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Wait for database
until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q'; do
  >&2 echo "Postgres ($DB_HOST:$DB_PORT) is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up"

if [ "$RUN_MIGRATIONS" = "true" ]; then
    >&2 echo "Executing migrations..."
    # Run shared migrations
    python manage.py migrate_schemas --shared --noinput

    # Run tenant migrations
    python manage.py migrate_schemas --noinput
else
    >&2 echo "Skipping migrations (RUN_MIGRATIONS is not true)"
fi

exec "$@"
