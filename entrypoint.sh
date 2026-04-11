#!/bin/bash
set -e

# Initialiser la base de données si elle n'existe pas encore
if [ ! -f /app/instance/balsp.db ]; then
    echo "Initialisation de la base de données..."
    flask init-db
else
    echo "Migration de la base existante..."
    flask migrate-db
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
    echo "Démarrage en HTTPS..."
    exec python3 -c "
import ssl
from app import app

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain('$CERT_DIR/cert.pem', '$CERT_DIR/key.pem')

app.run(host='0.0.0.0', port=5000, ssl_context=ctx, threaded=True)
"
else
    echo "Démarrage en HTTP (Gunicorn)..."
    exec gunicorn \
        --bind 0.0.0.0:5000 \
        --workers "${GUNICORN_WORKERS:-2}" \
        --timeout 120 \
        --access-logfile - \
        --error-logfile - \
        "app:app"
fi
