FROM python:3.12-slim

# Dépendances système pour Pillow (QR codes)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn pyopenssl

COPY . .

# Dossiers nécessaires
RUN mkdir -p instance static/uploads/logos

# Port exposé
EXPOSE 5000

# Variables d'env par défaut (à surcharger au déploiement)
ENV FLASK_APP=app.py
ENV FLASK_DEBUG=0

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
