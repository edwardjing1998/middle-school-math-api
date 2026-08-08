import snowflake.connector
from flask import Blueprint, request, jsonify

from common.db import get_snowflake_connection
from common.errors import json_error, now_utc_iso


rag_std_set_vector_bp = Blueprint(
    "rag_std_set_vector_bp",
    __name__,
)


# ============================================================
# Helpers
# ============================================================

def fetch_all_dict(cur):
    """
    Convert Snowflake cursor results into a list of dictionaries.

    Snowflake normally returns unquoted column names in uppercase,
    such as DESCRIPTION, SET_ID, and SCORE.
    """
    columns = [column[0] for column in cur.description] if cur.description else []
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def parse_limit(value, default=5, minimum=1, maximum=50):
    """
    Parse and constrain a result-limit value.
    """
    try:
        parsed_value = int(value)
        return max(minimum, min(maximum, parsed_value))
    except (TypeError, ValueError):
        return default


def parse_min_score(value, default=0.80):
    """
    Parse and constrain cosine similarity.

    VECTOR_COSINE_SIMILARITY normally returns a value from -1 to 1.
    """
    try:
        parsed_value = float(value)
        return max(-1.0, min(1.0, parsed_value))
    except (TypeError, ValueError):
        return default


def build_vector_search_sql():
    """
    Return the common Snowflake vector-search SQL.

    A CTE is used because the calculated SCORE alias cannot reliably
    be referenced by a WHERE clause in the same SELECT level.
    """
    return """
        WITH ranked_results AS (
            SELECT
                DOC_ID,
                SET_ID,
                DESCRIPTION,
                SOURCE_TABLE,
                VECTOR_COSINE_SIMILARITY(
                    EMBEDDING,
                    SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                        'snowflake-arctic-embed-m',
                        %s
                    )
                ) AS SCORE
            FROM EDU_AI_APP.WEBAPP.RAG_STD_SET_VECTOR
        )
        SELECT
            DOC_ID,
            SET_ID,
            DESCRIPTION,
            SOURCE_TABLE,
            SCORE
        FROM ranked_results
        WHERE SCORE >= %s
        ORDER BY SCORE DESC
        LIMIT %s
    """


def execute_vector_search(question, min_score, limit):
    """
    Execute a vector similarity search against Snowflake.
    """
    sql = build_vector_search_sql()

    with get_snowflake_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    question,
                    min_score,
                    limit,
                ),
            )
            return fetch_all_dict(cur)


def map_source(row, rank):
    """
    Convert a Snowflake result row to the REST response format.
    """
    return {
        "rank": rank,
        "docId": row.get("DOC_ID"),
        "setId": row.get("SET_ID"),
        "description": row.get("DESCRIPTION"),
        "sourceTable": row.get("SOURCE_TABLE"),
        "score": row.get("SCORE"),
    }


# ============================================================
# GET /api/rag/std-set-vector/search
# ============================================================

@rag_std_set_vector_bp.route(
    "/api/rag/std-set-vector/search",
    methods=["GET"],
)
def search_std_set_vector():
    """
    Search the Snowflake RAG_STD_SET_VECTOR table.

    Example:

        GET /api/rag/std-set-vector/search
            ?q=geometry
            &limit=5
            &minScore=0.80

    Query parameters:

        q:
            Required natural-language search text.

        limit:
            Optional maximum number of results.
            Default: 5
            Minimum: 1
            Maximum: 50

        minScore:
            Optional minimum cosine similarity.
            Default: 0.80
            Minimum: -1.0
            Maximum: 1.0
    """

    try:
        query = (request.args.get("q") or "").strip()

        if not query:
            return json_error("q is required", 400)

        limit = parse_limit(
            request.args.get("limit"),
            default=5,
        )

        min_score = parse_min_score(
            request.args.get("minScore"),
            default=0.80,
        )

        rows = execute_vector_search(
            question=query,
            min_score=min_score,
            limit=limit,
        )

        data = [
            map_source(row, rank=index + 1)
            for index, row in enumerate(rows)
        ]

        return jsonify(
            message="OK",
            query=query,
            limit=limit,
            minScore=min_score,
            count=len(data),
            data=data,
            time=now_utc_iso(),
        ), 200

    except snowflake.connector.errors.ProgrammingError as error:
        return json_error(
            f"Snowflake error: {error}",
            500,
        )

    except Exception as error:
        return json_error(
            f"Failed to search RAG_STD_SET_VECTOR: {error}",
            500,
        )


# ============================================================
# POST /api/rag/std-set-vector/ask-context
# ============================================================

@rag_std_set_vector_bp.route(
    "/api/rag/std-set-vector/ask-context",
    methods=["POST"],
)
def ask_std_set_vector_context():
    """
    Search the Snowflake vector table and return formatted RAG context.

    This endpoint does not call OpenAI or another LLM. It only retrieves
    relevant context from Snowflake.

    Example request:

        POST /api/rag/std-set-vector/ask-context

        {
            "question": "Which standards are related to geometry?",
            "topK": 5,
            "minScore": 0.80
        }
    """

    body = request.get_json(silent=True) or {}

    try:
        question = (body.get("question") or "").strip()

        if not question:
            return json_error("question is required", 400)

        top_k = parse_limit(
            body.get("topK"),
            default=5,
        )

        min_score = parse_min_score(
            body.get("minScore"),
            default=0.80,
        )

        rows = execute_vector_search(
            question=question,
            min_score=min_score,
            limit=top_k,
        )

        sources = []
        context_blocks = []

        for index, row in enumerate(rows):
            rank = index + 1
            description = row.get("DESCRIPTION") or ""

            source = map_source(
                row=row,
                rank=rank,
            )
            sources.append(source)

            context_blocks.append(
                f"Source {rank}\n"
                f"SET_ID: {row.get('SET_ID')}\n"
                f"SCORE: {row.get('SCORE')}\n"
                f"CONTENT:\n{description}"
            )

        context = "\n\n".join(context_blocks)

        if not sources:
            return jsonify(
                message="No sufficiently relevant context was found",
                question=question,
                topK=top_k,
                minScore=min_score,
                count=0,
                context="",
                sources=[],
                time=now_utc_iso(),
            ), 200

        return jsonify(
            message="OK",
            question=question,
            topK=top_k,
            minScore=min_score,
            count=len(sources),
            context=context,
            sources=sources,
            time=now_utc_iso(),
        ), 200

    except snowflake.connector.errors.ProgrammingError as error:
        return json_error(
            f"Snowflake error: {error}",
            500,
        )

    except Exception as error:
        return json_error(
            f"Failed to get RAG context from RAG_STD_SET_VECTOR: {error}",
            500,
        )