# common/errors.py
from datetime import datetime, timezone
from flask import jsonify

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def json_error(message: str, status: int = 400):
    r = jsonify({"error": message, "time": now_utc_iso()})
    r.status_code = status
    return r