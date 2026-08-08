# controller/math_questions_query_routes.py
import snowflake.connector
from flask import Blueprint, jsonify, request

from common.db import get_snowflake_connection
from common.errors import json_error, now_utc_iso


# ============================================================
# Blueprint
# ============================================================
math_questions_query_bp = Blueprint("math_questions_query_bp", __name__)


# ============================================================
# Helpers (local)
# ============================================================
def fetch_all_dict(cur):
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ============================================================
# Query (GET) - filter by state, subject, grade
#   GET /api/math-questions?state=NE&subject=Math&grade=2
# ============================================================
@math_questions_query_bp.route("/api/math-questions", methods=["GET"])
def query_math_course_question_details():
    try:
        state = (request.args.get("state") or "").strip()
        subject = (request.args.get("subject") or "").strip()
        grade = (request.args.get("grade") or "").strip()

        if not state:
            return json_error("state is required", 400)
        if not subject:
            return json_error("subject is required", 400)
        if not grade:
            return json_error("grade is required", 400)

        sql = """
          SELECT
            ID,
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
            IMAGE_URL_INITIAL,
            IMAGE_URL_FINAL,
            CREATED_AT,
            COURSE_TITLE,
            AVAILABLE_DRAWING_TOOLS
          FROM MATH_COURSE_QUESTION_DETAILS
          WHERE STATE = %s
            AND SUBJECT = %s
            AND GRADE = %s
          ORDER BY CREATED_AT DESC
        """

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (state, subject, grade))
                rows = fetch_all_dict(cur)

        return jsonify(
            message="OK",
            filter={"state": state, "subject": subject, "grade": grade},
            count=len(rows),
            data=rows,
            time=now_utc_iso(),
        ), 200

    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to query math questions: {e}", 500)