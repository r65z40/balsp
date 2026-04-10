#!/bin/bash
set -e

# Initialiser la base de données si elle n'existe pas encore
if [ ! -f /app/instance/balsp.db ]; then
    echo "Initialisation de la base de données..."
    flask init-db
fi

# Lancer Gunicorn (production)
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    "app:app"
