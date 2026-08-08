# controller/math_questions_routes.py
import json
import uuid

import snowflake.connector
from flask import Blueprint, jsonify, request

from common.db import get_snowflake_connection
from common.errors import json_error, now_utc_iso


# ============================================================
# Blueprint
# ============================================================
math_questions_bp = Blueprint("math_questions_bp", __name__)


# ============================================================
# Helpers (keep local to this blueprint)
# (copied from app.py to avoid cross-file coupling)
# ============================================================
def require_str(body, key: str) -> str:
    v = (body.get(key) or "").strip()
    if not v:
        raise ValueError(f"{key} is required")
    return v


def optional_str(body, key: str):
    v = body.get(key)
    if v is None:
        return None
    v = str(v).strip()
    return v if v else None


def optional_bool(body, key: str, default=False) -> bool:
    v = body.get(key)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return default


def to_variant_json(v):
    """
    Convert python list/dict/str/None -> JSON string that Snowflake can PARSE_JSON.
    - list/dict -> json string
    - str -> if already json-like keep; else split by newlines/;/, into array
    - None/"" -> None
    """
    if v is None:
        return None

    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None

        # If it looks like JSON already, keep it
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            return s

        # Otherwise treat as a list-like string: newline / ';' / ',' separated
        parts = [p.strip() for p in s.replace(",", ";").split(";") if p.strip()]
        if len(parts) == 1 and "\n" in s:
            parts = [p.strip() for p in s.splitlines() if p.strip()]

        return json.dumps(parts, ensure_ascii=False)

    # fallback: stringify
    return json.dumps(v, ensure_ascii=False)


# ============================================================
# Create (POST) - Save into MATH_COURSE_QUESTION_DETAILS
# POST /api/math-questions
# ============================================================
@math_questions_bp.route("/api/math-questions", methods=["POST"])
def create_math_course_question_detail():
    body = request.get_json(silent=True) or {}

    try:
        # =========================
        # Required fields
        # =========================
        state = require_str(body, "state")
        subject = require_str(body, "subject")
        grade = require_str(body, "grade")
        question = require_str(body, "question")
        answer = require_str(body, "answer")

        # =========================
        # Optional fields
        # =========================
        notation = optional_str(body, "notation")
        hint = optional_str(body, "hint")
        has_diagram = optional_bool(body, "has_diagram", default=False)
        image_url_initial = optional_str(body, "image_url_initial")
        image_url_final = optional_str(body, "image_url_final")
        course_title = optional_str(body, "course_title")

        # =========================
        # diagram_steps (VARIANT) handling
        # =========================
        diagram_steps = body.get("diagram_steps")
        diagram_steps_json = to_variant_json(diagram_steps)

        # =========================
        # ✅ NEW: available_drawing_tools (VARIANT) handling
        # Column: AVAILABLE_DRAWING_TOOLS
        # Accept: list/dict/string/null
        # =========================
        available_tools = body.get("available_drawing_tools")
        # also allow camelCase for UI convenience
        if available_tools is None and "availableDrawingTools" in body:
            available_tools = body.get("availableDrawingTools")
        available_tools_json = to_variant_json(available_tools)

        request_id = uuid.uuid4().hex

        insert_sql = """
          INSERT INTO EDU_AI_APP.WEBAPP.MATH_COURSE_QUESTION_DETAILS
          (
            REQUEST_ID,
            STATE,
            SUBJECT,
            GRADE,
            NOTATION,
            QUESTION,
            HINT,
            ANSWER,
            HAS_DIAGRAM,
            DIAGRAM_STEPS,
            AVAILABLE_DRAWING_TOOLS,
            IMAGE_URL_INITIAL,
            IMAGE_URL_FINAL,
            COURSE_TITLE
          )
          SELECT
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            IFF(%s IS NULL, NULL, PARSE_JSON(%s)),
            IFF(%s IS NULL, NULL, PARSE_JSON(%s)),
            %s, %s, %s
        """

        fetch_id_sql = """
          SELECT ID
          FROM EDU_AI_APP.WEBAPP.MATH_COURSE_QUESTION_DETAILS
          WHERE REQUEST_ID = %s
          LIMIT 1
        """

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    (
                        request_id,
                        state,
                        subject,
                        grade,
                        notation,
                        question,
                        hint,
                        answer,
                        has_diagram,
                        diagram_steps_json,
                        diagram_steps_json,
                        available_tools_json,
                        available_tools_json,
                        image_url_initial,
                        image_url_final,
                        course_title,
                    ),
                )

                new_id = None
                try:
                    cur.execute(fetch_id_sql, (request_id,))
                    row = cur.fetchone()
                    new_id = row[0] if row else None
                except Exception:
                    new_id = None

        return jsonify(
            message="Created",
            id=new_id,
            requestId=request_id,
            time=now_utc_iso(),
        ), 201

    except ValueError as ve:
        return json_error(str(ve), 400)

    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)

    except Exception as e:
        return json_error(f"Failed to create math question: {e}", 500)