# controller/std_set_routes.py
from flask import Blueprint, jsonify, request
import snowflake.connector

from common.db import get_snowflake_connection
from common.errors import json_error, now_utc_iso

# ✅ Create blueprint
std_set_bp = Blueprint("std_set_bp", __name__)

# ============================================================
# ✅ STD_SET options for UI Select
# GET /api/standards/sets/options
#
# Returns: [{ setId, description }]
#
# Optional query params:
#   limit=200 (default, max 2000)
#   q=...     (optional search on SET_ID/DESCRIPTION)
# ============================================================
@std_set_bp.route("/api/standards/sets/options", methods=["GET"])
def list_std_set_options():
    try:
        limit = (request.args.get("limit") or "200").strip()
        q = (request.args.get("q") or "").strip()

        try:
            limit_i = max(1, min(2000, int(limit)))
        except Exception:
            limit_i = 200

        where = []
        params = []

        if q:
            # case-insensitive contains search on SET_ID or DESCRIPTION
            where.append(
                "(UPPER(SET_ID) LIKE UPPER(%s) OR UPPER(DESCRIPTION) LIKE UPPER(%s))"
            )
            like = f"%{q}%"
            params.extend([like, like])

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
          SELECT
            SET_ID,
            DESCRIPTION
          FROM EDU_AI_APP.WEBAPP.STD_SET
          {where_sql}
          ORDER BY SET_ID
          LIMIT %s
        """
        params.append(limit_i)

        with get_snowflake_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                cols = [c[0] for c in cur.description] if cur.description else []
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        data = [{"setId": r.get("SET_ID"), "description": r.get("DESCRIPTION")} for r in rows]

        return (
            jsonify(
                message="OK",
                count=len(data),
                data=data,
                filter={"q": q or None, "limit": limit_i},
                time=now_utc_iso(),
            ),
            200,
        )

    except snowflake.connector.errors.ProgrammingError as e:
        return json_error(f"Snowflake error: {e}", 500)
    except Exception as e:
        return json_error(f"Failed to query STD_SET options: {e}", 500)