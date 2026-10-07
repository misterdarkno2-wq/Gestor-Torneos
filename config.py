"""Configuración independiente; nunca contiene credenciales de producción."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    APP_ENV = os.getenv('APP_ENV', 'development')
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_USER = os.getenv('DB_USER', 'torneos_app')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'gestor_torneos')
    DB_PORT = int(os.getenv('DB_PORT', '3306'))
    DB_SSL_CA = os.getenv('DB_SSL_CA', '')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_REFRESH_EACH_REQUEST = False
    MAX_CONTENT_LENGTH = 128 * 1024
    MAX_FORM_PARTS = 30
    TRUSTED_HOSTS = [host.strip() for host in os.getenv(
        'TRUSTED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
    WTF_CSRF_TIME_LIMIT = 12 * 60 * 60
