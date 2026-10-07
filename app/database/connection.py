"""Conexión por operación y transacciones con cierre garantizado."""
from contextlib import contextmanager

import pymysql
from flask import current_app


@contextmanager
def transaction():
    config = current_app.config
    options = {}
    if config['DB_SSL_CA']:
        options.update(ssl_ca=config['DB_SSL_CA'], ssl_verify_cert=True,
                       ssl_verify_identity=True)
    else:
        # Compatible con servidores de desarrollo que no utilizan TLS.
        options['ssl_disabled'] = True
    connection = pymysql.connect(
        host=config['DB_HOST'], user=config['DB_USER'],
        password=config['DB_PASSWORD'], database=config['DB_NAME'],
        port=config['DB_PORT'], charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor, autocommit=False,
        connect_timeout=5, read_timeout=10, write_timeout=10,
        init_command="SET time_zone = '+00:00'", **options)
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fetch_all(sql, params=()):
    with transaction() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def fetch_one(sql, params=()):
    with transaction() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def execute(sql, params=()):
    """INSERT/UPDATE/DELETE. SQL fijo en modelos; valores siempre parametrizados."""
    with transaction() as cursor:
        cursor.execute(sql, params)
        return cursor.lastrowid, cursor.rowcount
