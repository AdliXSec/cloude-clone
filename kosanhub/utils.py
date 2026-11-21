"""Helper parsing & validasi input request."""
from datetime import date, datetime

from flask import request

from kosanhub.errors import ValidationError


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Body harus berupa JSON object")
    return data


def require(data, *fields):
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ValidationError(f"Field wajib diisi: {', '.join(missing)}")


def parse_int(value, field, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValidationError(f"{field} harus berupa bilangan bulat")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} harus berupa bilangan bulat")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} minimal {minimum}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} maksimal {maximum}")
    return number


def parse_date(value, field):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{field} harus berformat YYYY-MM-DD")


def clean_str(value, field, max_len=255, required=True):
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"{field} wajib diisi")
        return None
    text = str(value).strip()
    if len(text) > max_len:
        raise ValidationError(f"{field} maksimal {max_len} karakter")
    return text
