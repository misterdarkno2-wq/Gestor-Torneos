"""Servidor local sin depurador; compatible con Windows y Linux."""
import os
from waitress import serve
from app import create_app

app = create_app()

if __name__ == '__main__':
    serve(app, host='127.0.0.1', port=int(os.getenv('PORT', '5000')))
