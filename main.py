import os
import json
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, jsonify, request
import snowflake.connector
from flask_cors import CORS
import uuid

from common.db import get_snowflake_connection
from common.errors import json_error, now_utc_iso

from dotenv import load_dotenv

# ✅ Import blueprint
from controller.standards_items_routes import std_items_bp
from controller.std_set_routes import std_set_bp

# ✅ NEW: import math questions blueprint (Create endpoint moved out)
from controller.math_questions_routes import math_questions_bp
# ✅ NEW: import math questions query blueprint (GET endpoint moved out)
from controller.math_questions_query_routes import math_questions_query_bp

# from controller.rag_routes import rag_bp

from controller.rag_std_set_vector_routes import rag_std_set_vector_bp

from controller.cortex_std_item_search_routes import (
    cortex_std_item_search_bp,
)

app = Flask(__name__)
CORS(app)

# ✅ Register blueprint
app.register_blueprint(std_items_bp)
app.register_blueprint(std_set_bp)

app.register_blueprint(math_questions_bp)
app.register_blueprint(math_questions_query_bp)
# app.register_blueprint(rag_bp)

app.register_blueprint(rag_std_set_vector_bp)

app.register_blueprint(cortex_std_item_search_bp)


# ============================================================
# Helpers
# ============================================================

load_dotenv()

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


def require_int(body, key: str) -> int:
    v = body.get(key)
    if v is None or str(v).strip() == "":
        raise ValueError(f"{key} is required")
    try:
        return int(v)
    except Exception:
        raise ValueError(f"{key} must be an integer")


def optional_int(body, key: str):
    v = body.get(key)
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(v)
    except Exception:
        raise ValueError(f"{key} must be an integer")


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


def parse_date_yyyy_mm_dd(s: Optional[str], field_name: str, required: bool):
    """
    Accepts 'YYYY-MM-DD' string -> returns same string (Snowflake DATE will accept it).
    """
    if s is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return None

    ss = str(s).strip()
    if not ss:
        if required:
            raise ValueError(f"{field_name} is required")
        return None

    # light validation
    try:
        # Use datetime to validate format
        datetime.strptime(ss, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"{field_name} must be YYYY-MM-DD")

    return ss


def fetch_all_dict(cur):
    """Convert Snowflake cursor rows -> list[dict]."""
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def has_column(cur, db: str, schema: str, table: str, column: str) -> bool:
    """
    Robustly detect if a column exists (case-insensitive) using INFORMATION_SCHEMA.
    """
    sql = """
      SELECT 1
      FROM IDENTIFIER(%s).INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = %s
        AND TABLE_NAME = %s
        AND UPPER(COLUMN_NAME) = UPPER(%s)
      LIMIT 1
    """
    # IDENTIFIER('<db>') is not allowed like this in Snowflake connector params.
    # So we build DB name into SQL safely by whitelisting known db.
    # Here we assume db is constant EDU_AI_APP; still keep parameterization for the rest.
    if db.upper() != "EDU_AI_APP":
        raise ValueError("Only EDU_AI_APP is supported in has_column() for safety.")

    sql2 = """
      SELECT 1
      FROM EDU_AI_APP.INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = %s
        AND TABLE_NAME = %s
        AND UPPER(COLUMN_NAME) = UPPER(%s)
      LIMIT 1
    """
    cur.execute(sql2, (schema.upper(), table.upper(), column))
    return cur.fetchone() is not None

def to_variant_json(v):
    """
    Convert python list/dict/str/None -> JSON string that Snowflake can PARSE_JSON.
    - list/dict -> json string
    - str -> if already json-like keep; else try split by ';' or ',' into array
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
        # If it looks like JSON already, keep
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            return s
        # Otherwise: allow "a; b; c" or "a,b,c"
        parts = [p.strip() for p in s.replace(",", ";").split(";") if p.strip()]
        return json.dumps(parts, ensure_ascii=False)
    # fallback
    return json.dumps(v, ensure_ascii=False)

# ============================================================
# Health
# ============================================================
@app.route("/", methods=["GET"])
def hello_world():
    return jsonify(message="Hello World", time=now_utc_iso())


@app.route("/health", methods=["GET"])
def is_healthy():
    return jsonify(message="Healthy", time=now_utc_iso())


# ============================================================
# ✅ NEW: Save Subjectives into STD_ITEM_SUBJECTIVES
# POST /api/standards/items/subjectives/upsert
#
# Body:
# {
#   "setId": "NE_MATH_9_12_2022",              # required
#   "itemId": "HS.A1.1",                      # required
#   "subjectives": [
#     {
#       "subjectiveId": "OBJ-1",              # required
#       "title": "...",
#       "difficulty": "easy|medium|hard",
#       "description": "...",
#       "prerequisites": ["..."],             # array OR "a; b; c"
#       "question_types": ["multiple_choice"],
#       "success_criteria": ["..."],
#       "tags": ["..."]
#     }
#   ]
# }
#
# Notes:
# - Uses MERGE so you can resubmit safely.
# - Stores list-like fields into VARIANT via PARSE_JSON.
# - Does NOT delete existing subjectives (no replace-all).
# ============================================================
@app.route("/api/standards/items/subjectives/upsert", methods=["POST"])
def upsert_std_item_subjectives():
    body = request.get_json(silent=True) or {}

    try:
        set_id = require_str(body, "setId")
        item_id = require_str(body, "itemId")
        subjectives = body.get("subjectives")

        if subjectives is None:
            subjectives = []
        if not isinstance(subjectives, list):
            return json_error("subjectives must be an array", 400)
        if not subjectives:
            return json_error("At least one subjective is required", 400)

        # ------------------------------------------------------------
        # ✅ validate + normalize (IGNORE UI subjectiveId)
        # ------------------------------------------------------------
        cleaned = []
        for s in subjectives:
            if not isinstance(s, dict):
                continue

            # ✅ IGNORE UI subjectiveId entirely
            cleaned.append(
                {
                    # subjective_id will be generated later
                    "title": optional_str(s, "title"),
                    "difficulty": optional_str(s, "difficulty"),
                    "description": optional_str(s, "description"),
                    "prereq_json": to_variant_json(s.get("prerequisites")),
                    "qtypes_json": to_variant_json(s.get("question_types")),
                    "success_json": to_variant_json(s.get("success_criteria")),
                    "tags_json": to_variant_json(s.get("tags")),
                }
            )

        if not cleaned:
            return json_error("No valid subjectives.", 400)

        # ------------------------------------------------------------
        # ✅ helper for description normalization (trim + case-insensitive)
        # ------------------------------------------------------------
        def norm_desc(v: str) -> str:
            return (v or "").strip().upper()

        # ✅ detect duplicates INSIDE this request payload (optional but recommended)
        seen_desc = set()
        for rec in cleaned:
            nd = norm_desc(rec.get("description"))
            if not nd:
                continue
            if nd in seen_desc:
                return json_error(
                    f"Duplicate description detected in request payload: '{rec.get('description')}'",
                    400,
                )
            seen_desc.add(nd)

        # ------------------------------------------------------------
        # ✅ DB work
        #   1) count existing rows by setId + itemId
        #   2) check duplicate description in DB (do not save)
        #   3) generate subjective_id = itemId + "-" + seq
        #   4) MERGE (upsert)
        # ------------------------------------------------------------
        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                try:
                    conn.autocommit(False)
                except Exception:
                    pass

                tbl = "STD_ITEM_SUBJECTIVES"

                # detect optional columns (so you won't hit invalid identifier again)
                has_created = False
                has_updated = False
                try:
                    has_created = has_column(cur, "EDU_AI_APP", "WEBAPP", tbl, "CREATED_AT")
                except Exception:
                    has_created = False
                try:
                    has_updated = has_column(cur, "EDU_AI_APP", "WEBAPP", tbl, "UPDATED_AT")
                except Exception:
                    has_updated = False

                # ✅ (1) existing count for seq generation
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES
                    WHERE SET_ID = %s AND ITEM_ID = %s
                    """,
                    (set_id, item_id),
                )
                row = cur.fetchone()
                existing_count = int(row[0] if row and row[0] is not None else 0)

                # ✅ (2) duplicate description check in DB BEFORE saving anything
                # rule: within same SET_ID + ITEM_ID, DESCRIPTION (case-insensitive + trim) must be unique
                for rec in cleaned:
                    desc_raw = rec.get("description") or ""
                    desc_norm = norm_desc(desc_raw)
                    if not desc_norm:
                        continue

                    cur.execute(
                        """
                        SELECT
                          SET_ID, ITEM_ID, SUBJECTIVE_ID, TITLE, DIFFICULTY, DESCRIPTION,
                          PREREQUISITES, QUESTION_TYPES, SUCCESS_CRITERIA, TAGS
                        FROM EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES
                        WHERE SET_ID = %s
                          AND ITEM_ID = %s
                          AND UPPER(TRIM(DESCRIPTION)) = UPPER(TRIM(%s))
                        LIMIT 1
                        """,
                        (set_id, item_id, desc_raw),
                    )
                    dup = cur.fetchone()
                    if dup:
                        # Return a helpful duplicated record message (no save)
                        duplicated = {
                            "setId": dup[0],
                            "itemId": dup[1],
                            "subjectiveId": dup[2],
                            "title": dup[3],
                            "difficulty": dup[4],
                            "description": dup[5],
                            "prerequisites": dup[6],
                            "question_types": dup[7],
                            "success_criteria": dup[8],
                            "tags": dup[9],
                        }
                        return json_error(
                            f"Duplicate description detected. Record already exists under SET_ID={set_id}, ITEM_ID={item_id}. "
                            f"Existing SUBJECTIVE_ID={dup[2]}",
                            400,
                        )

                # ✅ (3) generate subjective_id = itemId + "-" + seq
                # seq starts from (existing_count + 1). Keep 2-digit padding to preserve 07/08 style.
                for i, rec in enumerate(cleaned):
                    seq = existing_count + i + 1
                    seq_str = f"{seq:02d}"  # 1->01, 7->07, 12->12, 120->120
                    rec["subjective_id"] = f"{item_id}-{seq_str}"

                # ✅ (4) build MERGE dynamically based on columns
                if has_created and has_updated:
                    merge_sql = """
                      MERGE INTO EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES t
                      USING (
                        SELECT
                          %s AS SET_ID,
                          %s AS ITEM_ID,
                          %s AS SUBJECTIVE_ID,
                          %s AS TITLE,
                          %s AS DIFFICULTY,
                          %s AS DESCRIPTION,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS PREREQUISITES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS QUESTION_TYPES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS SUCCESS_CRITERIA,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS TAGS
                      ) s
                      ON t.SET_ID = s.SET_ID AND t.ITEM_ID = s.ITEM_ID AND t.SUBJECTIVE_ID = s.SUBJECTIVE_ID
                      WHEN MATCHED THEN UPDATE SET
                        TITLE = s.TITLE,
                        DIFFICULTY = s.DIFFICULTY,
                        DESCRIPTION = s.DESCRIPTION,
                        PREREQUISITES = s.PREREQUISITES,
                        QUESTION_TYPES = s.QUESTION_TYPES,
                        SUCCESS_CRITERIA = s.SUCCESS_CRITERIA,
                        TAGS = s.TAGS,
                        UPDATED_AT = CURRENT_TIMESTAMP()
                      WHEN NOT MATCHED THEN INSERT
                        (SET_ID, ITEM_ID, SUBJECTIVE_ID, TITLE, DIFFICULTY, DESCRIPTION,
                         PREREQUISITES, QUESTION_TYPES, SUCCESS_CRITERIA, TAGS, CREATED_AT, UPDATED_AT)
                      VALUES
                        (s.SET_ID, s.ITEM_ID, s.SUBJECTIVE_ID, s.TITLE, s.DIFFICULTY, s.DESCRIPTION,
                         s.PREREQUISITES, s.QUESTION_TYPES, s.SUCCESS_CRITERIA, s.TAGS, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
                    """
                elif has_created and (not has_updated):
                    merge_sql = """
                      MERGE INTO EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES t
                      USING (
                        SELECT
                          %s AS SET_ID,
                          %s AS ITEM_ID,
                          %s AS SUBJECTIVE_ID,
                          %s AS TITLE,
                          %s AS DIFFICULTY,
                          %s AS DESCRIPTION,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS PREREQUISITES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS QUESTION_TYPES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS SUCCESS_CRITERIA,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS TAGS
                      ) s
                      ON t.SET_ID = s.SET_ID AND t.ITEM_ID = s.ITEM_ID AND t.SUBJECTIVE_ID = s.SUBJECTIVE_ID
                      WHEN MATCHED THEN UPDATE SET
                        TITLE = s.TITLE,
                        DIFFICULTY = s.DIFFICULTY,
                        DESCRIPTION = s.DESCRIPTION,
                        PREREQUISITES = s.PREREQUISITES,
                        QUESTION_TYPES = s.QUESTION_TYPES,
                        SUCCESS_CRITERIA = s.SUCCESS_CRITERIA,
                        TAGS = s.TAGS
                      WHEN NOT MATCHED THEN INSERT
                        (SET_ID, ITEM_ID, SUBJECTIVE_ID, TITLE, DIFFICULTY, DESCRIPTION,
                         PREREQUISITES, QUESTION_TYPES, SUCCESS_CRITERIA, TAGS, CREATED_AT)
                      VALUES
                        (s.SET_ID, s.ITEM_ID, s.SUBJECTIVE_ID, s.TITLE, s.DIFFICULTY, s.DESCRIPTION,
                         s.PREREQUISITES, s.QUESTION_TYPES, s.SUCCESS_CRITERIA, s.TAGS, CURRENT_TIMESTAMP())
                    """
                elif (not has_created) and has_updated:
                    merge_sql = """
                      MERGE INTO EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES t
                      USING (
                        SELECT
                          %s AS SET_ID,
                          %s AS ITEM_ID,
                          %s AS SUBJECTIVE_ID,
                          %s AS TITLE,
                          %s AS DIFFICULTY,
                          %s AS DESCRIPTION,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS PREREQUISITES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS QUESTION_TYPES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS SUCCESS_CRITERIA,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS TAGS
                      ) s
                      ON t.SET_ID = s.SET_ID AND t.ITEM_ID = s.ITEM_ID AND t.SUBJECTIVE_ID = s.SUBJECTIVE_ID
                      WHEN MATCHED THEN UPDATE SET
                        TITLE = s.TITLE,
                        DIFFICULTY = s.DIFFICULTY,
                        DESCRIPTION = s.DESCRIPTION,
                        PREREQUISITES = s.PREREQUISITES,
                        QUESTION_TYPES = s.QUESTION_TYPES,
                        SUCCESS_CRITERIA = s.SUCCESS_CRITERIA,
                        TAGS = s.TAGS,
                        UPDATED_AT = CURRENT_TIMESTAMP()
                      WHEN NOT MATCHED THEN INSERT
                        (SET_ID, ITEM_ID, SUBJECTIVE_ID, TITLE, DIFFICULTY, DESCRIPTION,
                         PREREQUISITES, QUESTION_TYPES, SUCCESS_CRITERIA, TAGS, UPDATED_AT)
                      VALUES
                        (s.SET_ID, s.ITEM_ID, s.SUBJECTIVE_ID, s.TITLE, s.DIFFICULTY, s.DESCRIPTION,
                         s.PREREQUISITES, s.QUESTION_TYPES, s.SUCCESS_CRITERIA, s.TAGS, CURRENT_TIMESTAMP())
                    """
                else:
                    merge_sql = """
                      MERGE INTO EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES t
                      USING (
                        SELECT
                          %s AS SET_ID,
                          %s AS ITEM_ID,
                          %s AS SUBJECTIVE_ID,
                          %s AS TITLE,
                          %s AS DIFFICULTY,
                          %s AS DESCRIPTION,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS PREREQUISITES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS QUESTION_TYPES,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS SUCCESS_CRITERIA,
                          IFF(%s IS NULL, NULL, PARSE_JSON(%s)) AS TAGS
                      ) s
                      ON t.SET_ID = s.SET_ID AND t.ITEM_ID = s.ITEM_ID AND t.SUBJECTIVE_ID = s.SUBJECTIVE_ID
                      WHEN MATCHED THEN UPDATE SET
                        TITLE = s.TITLE,
                        DIFFICULTY = s.DIFFICULTY,
                        DESCRIPTION = s.DESCRIPTION,
                        PREREQUISITES = s.PREREQUISITES,
                        QUESTION_TYPES = s.QUESTION_TYPES,
                        SUCCESS_CRITERIA = s.SUCCESS_CRITERIA,
                        TAGS = s.TAGS
                      WHEN NOT MATCHED THEN INSERT
                        (SET_ID, ITEM_ID, SUBJECTIVE_ID, TITLE, DIFFICULTY, DESCRIPTION,
                         PREREQUISITES, QUESTION_TYPES, SUCCESS_CRITERIA, TAGS)
                      VALUES
                        (s.SET_ID, s.ITEM_ID, s.SUBJECTIVE_ID, s.TITLE, s.DIFFICULTY, s.DESCRIPTION,
                         s.PREREQUISITES, s.QUESTION_TYPES, s.SUCCESS_CRITERIA, s.TAGS)
                    """

                upserted = 0
                for s in cleaned:
                    cur.execute(
                        merge_sql,
                        (
                            set_id,
                            item_id,
                            s["subjective_id"],
                            s["title"],
                            s["difficulty"],
                            s["description"],
                            s["prereq_json"],
                            s["prereq_json"],
                            s["qtypes_json"],
                            s["qtypes_json"],
                            s["success_json"],
                            s["success_json"],
                            s["tags_json"],
                            s["tags_json"],
                        ),
                    )
                    upserted += 1

                # read back
                select_sql = """
                  SELECT
                    SET_ID, ITEM_ID, SUBJECTIVE_ID, TITLE, DIFFICULTY, DESCRIPTION,
                    PREREQUISITES, QUESTION_TYPES, SUCCESS_CRITERIA, TAGS
                  FROM EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES
                  WHERE SET_ID = %s AND ITEM_ID = %s
                  ORDER BY SUBJECTIVE_ID
                """
                if has_created:
                    select_sql = select_sql.replace("TAGS", "TAGS, CREATED_AT")
                if has_updated:
                    select_sql = select_sql.replace("TAGS", "TAGS, UPDATED_AT")

                cur.execute(select_sql, (set_id, item_id))
                rows = fetch_all_dict(cur)

                try:
                    conn.commit()
                except Exception:
                    pass
                try:
                    conn.autocommit(True)
                except Exception:
                    pass

        return jsonify(
            message="Upsert Subjectives OK",
            setId=set_id,
            itemId=item_id,
            subjectivesUpserted=upserted,
            data=rows,
            time=now_utc_iso(),
        ), 200

    except ValueError as ve:
        return json_error(str(ve), 400)
    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to upsert subjectives: {e}", 500)
# ============================================================
# ✅ Standards Sets Upsert (STD_SET + STD_ITEM)
# POST /api/standards/sets/upsert
#
# Key Fix:
# - Your error is almost certainly from STD_ITEM not having CREATED_AT.
# - This endpoint now auto-detects whether STD_SET/STD_ITEM have CREATED_AT and
#   builds SQL accordingly (no invalid identifier).
# ============================================================

@app.route("/api/standards/sets/upsert", methods=["POST"])
def upsert_standards_set_and_items():
    body = request.get_json(silent=True) or {}

    try:
        set_obj = body.get("set") or {}
        items = body.get("items") or []
        replace_items = optional_bool(body, "replaceItems", default=False)  # 仍保留字段，但不再 delete-all

        # ---- validate set fields ----
        set_id = require_str(set_obj, "setId")
        state = require_str(set_obj, "state")
        subject = require_str(set_obj, "subject")
        grade_range = require_str(set_obj, "gradeRange")
        title = require_str(set_obj, "title")

        version_year = optional_str(set_obj, "versionYear")
        source = optional_str(set_obj, "source")
        description = optional_str(set_obj, "description")

        # ---- validate items ----
        if items is None:
            items = []
        if not isinstance(items, list):
            return json_error("items must be an array", 400)

        cleaned_items = []
        for it in items:
            if not isinstance(it, dict):
                continue
            item_id = (it.get("itemId") or "").strip()
            standard_text = (it.get("standardText") or "").strip()
            course_level = (it.get("courseLevel") or "").strip() or None

            if item_id and standard_text:
                cleaned_items.append({"itemId": item_id, "standardText": standard_text, "courseLevel": course_level})

        # ✅ allow set-only upsert (items optional)
        # if you want to enforce at least one item, you can add back validation.

        # ---- SQL (STD_SET) ----
        merge_set_sql = """
            MERGE INTO EDU_AI_APP.WEBAPP.STD_SET t
            USING (
                SELECT
                    %s AS SET_ID,
                    %s AS STATE,
                    %s AS SUBJECT,
                    %s AS GRADE_RANGE,
                    %s AS TITLE,
                    %s AS VERSION_YEAR,
                    %s AS SOURCE,
                    %s AS DESCRIPTION
            ) s
            ON t.SET_ID = s.SET_ID
            WHEN MATCHED THEN UPDATE SET
                STATE = s.STATE,
                SUBJECT = s.SUBJECT,
                GRADE_RANGE = s.GRADE_RANGE,
                TITLE = s.TITLE,
                VERSION_YEAR = s.VERSION_YEAR,
                SOURCE = s.SOURCE,
                DESCRIPTION = s.DESCRIPTION
            WHEN NOT MATCHED THEN INSERT
                (SET_ID, STATE, SUBJECT, GRADE_RANGE, TITLE, VERSION_YEAR, SOURCE, DESCRIPTION)
            VALUES
                (s.SET_ID, s.STATE, s.SUBJECT, s.GRADE_RANGE, s.TITLE, s.VERSION_YEAR, s.SOURCE, s.DESCRIPTION)
        """

        # ---- read back (return) ----
        select_set_sql = """
            SELECT
              SET_ID, STATE, SUBJECT, GRADE_RANGE, TITLE, VERSION_YEAR, SOURCE, DESCRIPTION, CREATED_AT
            FROM EDU_AI_APP.WEBAPP.STD_SET
            WHERE SET_ID = %s
            LIMIT 1
        """

        select_items_sql_no_created = """
            SELECT
              ITEM_ID, SET_ID, STANDARD_TEXT, COURSE_LEVEL
            FROM EDU_AI_APP.WEBAPP.STD_ITEM
            WHERE SET_ID = %s
            ORDER BY ITEM_ID
        """

        select_items_sql_with_created = """
            SELECT
              ITEM_ID, SET_ID, STANDARD_TEXT, COURSE_LEVEL, CREATED_AT
            FROM EDU_AI_APP.WEBAPP.STD_ITEM
            WHERE SET_ID = %s
            ORDER BY ITEM_ID
        """

        items_upserted = 0

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                # best-effort tx
                try:
                    conn.autocommit(False)
                except Exception:
                    pass

                # ---- upsert STD_SET ----
                cur.execute(
                    merge_set_sql,
                    (
                        set_id,
                        state,
                        subject,
                        grade_range,
                        title,
                        version_year,
                        source,
                        description,
                    ),
                )

                # ✅ IMPORTANT CHANGE:
                # Do NOT delete existing STD_ITEM rows.
                # Because STD_ITEM is one-to-many, and composite key is (SET_ID, ITEM_ID),
                # we should only MERGE each provided item.

                if cleaned_items:
                    std_item_has_created_at = False
                    try:
                        std_item_has_created_at = has_column(
                            cur, "EDU_AI_APP", "WEBAPP", "STD_ITEM", "CREATED_AT"
                        )
                    except Exception:
                        std_item_has_created_at = False

                    if std_item_has_created_at:
                        merge_item_sql = """
                            MERGE INTO EDU_AI_APP.WEBAPP.STD_ITEM t
                            USING (
                                SELECT
                                    %s AS ITEM_ID,
                                    %s AS SET_ID,
                                    %s AS STANDARD_TEXT,
                                    %s AS COURSE_LEVEL
                            ) s
                            ON t.SET_ID = s.SET_ID AND t.ITEM_ID = s.ITEM_ID
                            WHEN MATCHED THEN UPDATE SET
                                STANDARD_TEXT = s.STANDARD_TEXT,
                                COURSE_LEVEL = s.COURSE_LEVEL
                            WHEN NOT MATCHED THEN INSERT
                                (ITEM_ID, SET_ID, STANDARD_TEXT, COURSE_LEVEL, CREATED_AT)
                            VALUES
                                (s.ITEM_ID, s.SET_ID, s.STANDARD_TEXT, s.COURSE_LEVEL, CURRENT_TIMESTAMP())
                        """
                    else:
                        merge_item_sql = """
                            MERGE INTO EDU_AI_APP.WEBAPP.STD_ITEM t
                            USING (
                                SELECT
                                    %s AS ITEM_ID,
                                    %s AS SET_ID,
                                    %s AS STANDARD_TEXT,
                                    %s AS COURSE_LEVEL
                            ) s
                            ON t.SET_ID = s.SET_ID AND t.ITEM_ID = s.ITEM_ID
                            WHEN MATCHED THEN UPDATE SET
                                STANDARD_TEXT = s.STANDARD_TEXT,
                                COURSE_LEVEL = s.COURSE_LEVEL
                            WHEN NOT MATCHED THEN INSERT
                                (ITEM_ID, SET_ID, STANDARD_TEXT, COURSE_LEVEL)
                            VALUES
                                (s.ITEM_ID, s.SET_ID, s.STANDARD_TEXT, s.COURSE_LEVEL)
                        """

                    for it in cleaned_items:
                        cur.execute(
                            merge_item_sql,
                            (it["itemId"], set_id, it["standardText"], it.get("courseLevel"))
                        )
                        items_upserted += 1

                # ---- read back set + items ----
                cur.execute(select_set_sql, (set_id,))
                set_rows = fetch_all_dict(cur)
                set_row = set_rows[0] if set_rows else None

                std_item_has_created_at_for_read = False
                try:
                    std_item_has_created_at_for_read = has_column(
                        cur, "EDU_AI_APP", "WEBAPP", "STD_ITEM", "CREATED_AT"
                    )
                except Exception:
                    std_item_has_created_at_for_read = False

                cur.execute(
                    select_items_sql_with_created if std_item_has_created_at_for_read else select_items_sql_no_created,
                    (set_id,),
                )
                item_rows = fetch_all_dict(cur)

                try:
                    conn.commit()
                except Exception:
                    pass
                try:
                    conn.autocommit(True)
                except Exception:
                    pass

        return jsonify(
            message="Upsert OK",
            setId=set_id,
            itemsUpserted=items_upserted,
            replaceItems=replace_items,  # still returned for compatibility
            data={
                "set": set_row,
                "items": item_rows,
            },
            time=now_utc_iso(),
        ), 200

    except ValueError as ve:
        return json_error(str(ve), 400)
    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to upsert standards set: {e}", 500)

# ============================================================
# Query (GET) - filter by state, subject, grade
#   GET /api/math-questions?state=NE&subject=Math&grade=2
# ============================================================
@app.route("/api/math-questions", methods=["GET"])
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
            COURSE_TITLE
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


# ============================================================
# Update IMAGE_URL_INITIAL by request_id
# ============================================================
@app.route("/api/math-questions/<request_id>/image-url-initial", methods=["PUT"])
def update_image_url_initial(request_id: str):
    body = request.get_json(silent=True) or {}
    try:
        rid = (request_id or "").strip()
        if not rid:
            return json_error("request_id is required", 400)

        new_url = body.get("image_url_initial")
        if new_url is None:
            image_url_initial = None
        else:
            image_url_initial = str(new_url).strip() or None

        update_sql = """
          UPDATE MATH_COURSE_QUESTION_DETAILS
          SET IMAGE_URL_INITIAL = %s
          WHERE REQUEST_ID = %s
        """

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(update_sql, (image_url_initial, rid))
                updated = cur.rowcount

        if not updated:
            return json_error(f"No record found for REQUEST_ID={rid}", 404)

        return jsonify(
            message="Updated IMAGE_URL_INITIAL",
            requestId=rid,
            image_url_initial=image_url_initial,
            rowsAffected=updated,
            time=now_utc_iso(),
        ), 200

    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to update IMAGE_URL_INITIAL: {e}", 500)


# ============================================================
# Update IMAGE_URL_FINAL by request_id
# ============================================================
@app.route("/api/math-questions/<request_id>/image-url-final", methods=["PUT"])
def update_image_url_final(request_id: str):
    body = request.get_json(silent=True) or {}
    try:
        rid = (request_id or "").strip()
        if not rid:
            return json_error("request_id is required", 400)

        new_url = body.get("image_url_final")
        if new_url is None:
            image_url_final = None
        else:
            image_url_final = str(new_url).strip() or None

        update_sql = """
          UPDATE MATH_COURSE_QUESTION_DETAILS
          SET IMAGE_URL_FINAL = %s
          WHERE REQUEST_ID = %s
        """

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(update_sql, (image_url_final, rid))
                updated = cur.rowcount

        if not updated:
            return json_error(f"No record found for REQUEST_ID={rid}", 404)

        return jsonify(
            message="Updated IMAGE_URL_FINAL",
            requestId=rid,
            image_url_final=image_url_final,
            rowsAffected=updated,
            time=now_utc_iso(),
        ), 200

    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to update IMAGE_URL_FINAL: {e}", 500)


# ============================================================
# ✅ NEW: Enrollments APIs (MATHS_COURSE_ENROLLMENTS)
# ============================================================

# ----------------------------
# POST /api/enrollments
# Body:
# {
#   "student_id": 123,
#   "school_id": "310264001234",
#   "math_course_id": "REQUEST_ID_XXX",
#   "enroll_status": "ACTIVE",        # optional
#   "start_date": "2026-02-01",
#   "end_date": "2026-05-30",         # optional
#   "term": "2026-Spring",            # optional
#   "grade_at_enroll": "2",           # optional
#   "teacher_note": "..."             # optional
# }
# ----------------------------
@app.route("/api/enrollments", methods=["POST"])
def create_enrollment():
    body = request.get_json(silent=True) or {}
    try:
        student_id = require_int(body, "student_id")
        school_id = require_str(body, "school_id")
        math_course_id = require_str(body, "math_course_id")

        enroll_status = optional_str(body, "enroll_status") or "ACTIVE"
        start_date = parse_date_yyyy_mm_dd(body.get("start_date"), "start_date", required=True)
        end_date = parse_date_yyyy_mm_dd(body.get("end_date"), "end_date", required=False)

        term = optional_str(body, "term")
        grade_at_enroll = optional_str(body, "grade_at_enroll")
        teacher_note = optional_str(body, "teacher_note")

        enrollment_id = uuid.uuid4().hex

        insert_sql = """
          INSERT INTO MATHS_COURSE_ENROLLMENTS
          (
            ENROLLMENT_ID,
            STUDENT_ID,
            SCHOOL_ID,
            MATH_COURSE_ID,
            ENROLL_STATUS,
            START_DATE,
            END_DATE,
            TERM,
            GRADE_AT_ENROLL,
            TEACHER_NOTE
          )
          VALUES
          (
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
          )
        """

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    (
                        enrollment_id,
                        student_id,
                        school_id,
                        math_course_id,
                        enroll_status,
                        start_date,
                        end_date,
                        term,
                        grade_at_enroll,
                        teacher_note,
                    ),
                )

        return jsonify(
            message="Enrollment Created",
            enrollment_id=enrollment_id,      # ✅ UI-friendly
            ENROLLMENT_ID=enrollment_id,      # ✅ optional compatibility
            data={
                "ENROLLMENT_ID": enrollment_id,
                "STUDENT_ID": student_id,
                "SCHOOL_ID": school_id,
                "MATH_COURSE_ID": math_course_id,
                "ENROLL_STATUS": enroll_status,
                "START_DATE": str(start_date),
                "END_DATE": str(end_date) if end_date else None,
                "TERM": term,
                "GRADE_AT_ENROLL": grade_at_enroll,
                "TEACHER_NOTE": teacher_note,
            },
            time=now_utc_iso(),
        ), 201

    except ValueError as ve:
        return json_error(str(ve), 400)
    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to create enrollment: {e}", 500)

# ----------------------------
# GET /api/enrollments
# Query params (all optional):
#   studentId=123
#   schoolId=...
#   mathCourseId=...
#   status=ACTIVE
#   term=2026-Spring
#   limit=200
#   offset=0
# ----------------------------
@app.route("/api/enrollments", methods=["GET"])
def list_enrollments():
    try:
        student_id = (request.args.get("studentId") or "").strip()
        school_id = (request.args.get("schoolId") or "").strip()
        math_course_id = (request.args.get("mathCourseId") or "").strip()
        status = (request.args.get("status") or "").strip()
        term = (request.args.get("term") or "").strip()

        limit = (request.args.get("limit") or "200").strip()
        offset = (request.args.get("offset") or "0").strip()

        try:
            limit_i = max(1, min(1000, int(limit)))
        except Exception:
            limit_i = 200
        try:
            offset_i = max(0, int(offset))
        except Exception:
            offset_i = 0

        where = []
        params = []

        if student_id:
            where.append("STUDENT_ID = %s")
            params.append(int(student_id))
        if school_id:
            where.append("SCHOOL_ID = %s")
            params.append(school_id)
        if math_course_id:
            where.append("MATH_COURSE_ID = %s")
            params.append(math_course_id)
        if status:
            where.append("ENROLL_STATUS = %s")
            params.append(status)
        if term:
            where.append("TERM = %s")
            params.append(term)

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
          SELECT
            ENROLLMENT_ID,
            STUDENT_ID,
            SCHOOL_ID,
            MATH_COURSE_ID,
            ENROLL_STATUS,
            START_DATE,
            END_DATE,
            TERM,
            GRADE_AT_ENROLL,
            TEACHER_NOTE,
            CREATED_AT,
            UPDATED_AT
          FROM MATHS_COURSE_ENROLLMENTS
          {where_sql}
          ORDER BY CREATED_AT DESC
          LIMIT %s OFFSET %s
        """

        params.extend([limit_i, offset_i])

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = fetch_all_dict(cur)

        return jsonify(
            message="OK",
            filter={
                "studentId": student_id or None,
                "schoolId": school_id or None,
                "mathCourseId": math_course_id or None,
                "status": status or None,
                "term": term or None,
                "limit": limit_i,
                "offset": offset_i,
            },
            count=len(rows),
            data=rows,
            time=now_utc_iso(),
        ), 200

    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to query enrollments: {e}", 500)


# ----------------------------
# PUT /api/enrollments/<enrollment_id>
# Body (any of these optional):
# {
#   "enroll_status": "DROPPED",
#   "end_date": "2026-03-01",
#   "term": "2026-Spring",
#   "grade_at_enroll": "2",
#   "teacher_note": "..."
# }
# ----------------------------
@app.route("/api/enrollments/<enrollment_id>", methods=["PUT"])
def update_enrollment(enrollment_id: str):
    body = request.get_json(silent=True) or {}
    try:
        eid = (enrollment_id or "").strip()
        if not eid:
            return json_error("enrollment_id is required", 400)

        enroll_status = optional_str(body, "enroll_status")
        end_date = parse_date_yyyy_mm_dd(body.get("end_date"), "end_date", required=False)
        term = optional_str(body, "term")
        grade_at_enroll = optional_str(body, "grade_at_enroll")
        teacher_note = optional_str(body, "teacher_note")

        sets = []
        params = []

        if enroll_status is not None:
            sets.append("ENROLL_STATUS = %s")
            params.append(enroll_status)
        if end_date is not None or ("end_date" in body):
            # allow explicit null to clear
            sets.append("END_DATE = %s")
            params.append(end_date)
        if term is not None or ("term" in body):
            sets.append("TERM = %s")
            params.append(term)
        if grade_at_enroll is not None or ("grade_at_enroll" in body):
            sets.append("GRADE_AT_ENROLL = %s")
            params.append(grade_at_enroll)
        if teacher_note is not None or ("teacher_note" in body):
            sets.append("TEACHER_NOTE = %s")
            params.append(teacher_note)

        if not sets:
            return json_error("No updatable fields provided", 400)

        # keep UPDATED_AT fresh
        sets.append("UPDATED_AT = CURRENT_TIMESTAMP()")

        update_sql = f"""
          UPDATE MATHS_COURSE_ENROLLMENTS
          SET {", ".join(sets)}
          WHERE ENROLLMENT_ID = %s
        """
        params.append(eid)

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(update_sql, tuple(params))
                updated = cur.rowcount

        if not updated:
            return json_error(f"No record found for ENROLLMENT_ID={eid}", 404)

        return jsonify(
            message="Enrollment Updated",
            enrollmentId=eid,
            rowsAffected=updated,
            time=now_utc_iso(),
        ), 200

    except ValueError as ve:
        return json_error(str(ve), 400)
    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to update enrollment: {e}", 500)


# ============================================================
# ✅ Query Subjectives (STD_ITEM_SUBJECTIVES)
# GET /api/standards/items/subjectives
#
# Optional query params:
#   setId=NE_MATH_9_12_2022
#   itemId=HS.A1.1
#   limit=200
#   offset=0
#
# Returns ALL columns:
#   SET_ID, ITEM_ID, SUBJECTIVE_ID, TITLE, DIFFICULTY, DESCRIPTION,
#   PREREQUISITES, QUESTION_TYPES, SUCCESS_CRITERIA, TAGS, CREATED_AT, UPDATED_AT
# ============================================================
# ============================================================
# ✅ Query Subjectives (Mapped JSON Response)
# GET /api/standards/items/subjectives
# ============================================================
@app.route("/api/standards/items/subjectives", methods=["GET"])
def list_std_item_subjectives():
    try:
        set_id = (request.args.get("setId") or "").strip()
        item_id = (request.args.get("itemId") or "").strip()

        limit = (request.args.get("limit") or "200").strip()
        offset = (request.args.get("offset") or "0").strip()

        try:
            limit_i = max(1, min(2000, int(limit)))
        except Exception:
            limit_i = 200

        try:
            offset_i = max(0, int(offset))
        except Exception:
            offset_i = 0

        where = []
        params = []

        if set_id:
            where.append("SET_ID = %s")
            params.append(set_id)
        if item_id:
            where.append("ITEM_ID = %s")
            params.append(item_id)

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
          SELECT
            SET_ID,
            ITEM_ID,
            SUBJECTIVE_ID,
            TITLE,
            DIFFICULTY,
            DESCRIPTION,
            PREREQUISITES,
            QUESTION_TYPES,
            SUCCESS_CRITERIA,
            TAGS,
            CREATED_AT,
            UPDATED_AT
          FROM EDU_AI_APP.WEBAPP.STD_ITEM_SUBJECTIVES
          {where_sql}
          ORDER BY SET_ID, ITEM_ID, SUBJECTIVE_ID
          LIMIT %s OFFSET %s
        """
        params.extend([limit_i, offset_i])

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = fetch_all_dict(cur)

        # ==========================
        # ✅ Map DB columns → JSON
        # ==========================
        mapped = []
        for r in rows:
            mapped.append({
                "setId": r.get("SET_ID"),
                "itemId": r.get("ITEM_ID"),
                "subjectiveId": r.get("SUBJECTIVE_ID"),
                "title": r.get("TITLE"),
                "difficulty": r.get("DIFFICULTY"),
                "description": r.get("DESCRIPTION"),
                "prerequisites": r.get("PREREQUISITES"),
                "questionTypes": r.get("QUESTION_TYPES"),
                "successCriteria": r.get("SUCCESS_CRITERIA"),
                "tags": r.get("TAGS"),
                "createdAt": r.get("CREATED_AT"),
                "updatedAt": r.get("UPDATED_AT"),
            })

        return jsonify(
            message="OK",
            filter={
                "setId": set_id or None,
                "itemId": item_id or None,
                "limit": limit_i,
                "offset": offset_i,
            },
            count=len(mapped),
            data=mapped,
            time=now_utc_iso(),
        ), 200

    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to query STD_ITEM_SUBJECTIVES: {e}", 500)

# ============================================================
# Run
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8282))
    app.run(debug=True, host="0.0.0.0", port=port)