#!/bin/bash
set -e

# Initialiser la base de données si elle n'existe pas encore
if [ ! -f /app/instance/balsp.db ]; then
    echo "Initialisation de la base de données..."
    flask init-db
fi

# Générer un certificat auto-signé si absent et HTTPS activé
if [ "${ENABLE_SSL:-0}" = "1" ]; then
    CERT_DIR="/app/instance/ssl"
    mkdir -p "$CERT_DIR"
    if [ ! -f "$CERT_DIR/cert.pem" ]; then
        echo "Génération du certificat SSL auto-signé..."
        python3 -c "
from OpenSSL import crypto
key = crypto.PKey()
key.generate_key(crypto.TYPE_RSA, 2048)
cert = crypto.X509()
cert.get_subject().CN = '${SSL_DOMAIN:-balsp.local}'
cert.set_serial_number(1000)
cert.gmtime_adj_notBefore(0)
cert.gmtime_adj_notAfter(365*24*60*60)
cert.set_issuer(cert.get_subject())
cert.set_pubkey(key)
cert.sign(key, 'sha256')
open('$CERT_DIR/cert.pem', 'wb').write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
open('$CERT_DIR/key.pem', 'wb').write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
print('Certificat généré.')
"
    fi
    SSL_ARGS="--certfile=$CERT_DIR/cert.pem --keyfile=$CERT_DIR/key.pem"
    echo "Démarrage en HTTPS..."
else
    SSL_ARGS=""
    echo "Démarrage en HTTP..."
fi

# Lancer Gunicorn (production)
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    $SSL_ARGS \
    "app:app"
