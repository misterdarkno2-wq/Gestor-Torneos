"""Configuración independiente; nunca contiene credenciales de producción."""
import os
import json
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
PUBLIC_SUPABASE = json.loads((BASE_DIR / 'supabase/public-config.json').read_text(encoding='utf-8'))


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    APP_ENV = os.getenv('APP_ENV', 'development')
    SUPABASE_URL = os.getenv('SUPABASE_URL') or PUBLIC_SUPABASE['url']
    SUPABASE_PUBLISHABLE_KEY = os.getenv('SUPABASE_PUBLISHABLE_KEY') or PUBLIC_SUPABASE['publishableKey']
    SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY', '')
    SESSION_STORE = str(BASE_DIR / 'instance' / 'sessions.sqlite3')
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
