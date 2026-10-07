import re
import unicodedata


def clean_text(value, label, maximum, course=False):
    value = ' '.join(unicodedata.normalize('NFC', value).split())
    allowed = ' °-' if course else ' '
    if not 2 <= len(value) <= maximum or not all(char.isalnum() or char in allowed for char in value):
        raise ValueError(f'{label}: usa entre 2 y {maximum} caracteres, letras, números y espacios.'
                         + (' También puedes usar ° y guiones.' if course else ''))
    return value


def clean_username(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,30}', value):
        raise ValueError('El usuario debe tener entre 3 y 30 letras, números, puntos, guiones o guiones bajos.')
    return value
