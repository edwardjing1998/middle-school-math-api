# standards_items_routes.py
from flask import Blueprint, jsonify, request

from common.db import get_snowflake_connection
from common.errors import json_error, now_utc_iso

std_items_bp = Blueprint("std_items_bp", __name__)

@std_items_bp.route("/api/standards/items/by-set", methods=["GET"])
def get_std_items_by_set():

    set_id = request.args.get("setId")

    if not set_id:
        return json_error("setId is required", 400)

    conn = None
    cur = None

    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()

        sql = """
            SELECT
                SET_ID,
                ITEM_ID,
                STANDARD_TEXT
            FROM STD_ITEM
            WHERE SET_ID = %s
            ORDER BY ITEM_ID
        """

        cur.execute(sql, (set_id,))
        rows = cur.fetchall()

        result = [
            {
                "setId": r[0],
                "itemId": r[1],
                "standardText": r[2],
            }
            for r in rows
        ]

        return jsonify(
            {
                "message": "OK",
                "count": len(result),
                "filter": {"setId": set_id},
                "time": now_utc_iso(),
                "data": result,
            }
        )

    except Exception as e:
        return json_error(str(e), 500)

    finally:
        try:
            if cur:
                cur.close()
            if conn:
                conn.close()
        except Exception:
            pass