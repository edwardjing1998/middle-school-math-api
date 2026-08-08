import os
from typing import List, Dict

from flask import Blueprint, request, jsonify
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

from common.db import get_snowflake_connection
from common.errors import json_error, now_utc_iso

rag_bp = Blueprint("rag_bp", __name__)

# Lazy global objects
_embedding_model = None
_chroma_client = None
_collection = None
_openai_client = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
    return _embedding_model


def get_chroma_collection():
    global _chroma_client, _collection

    if _chroma_client is None:
        chroma_path = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
        _chroma_client = chromadb.PersistentClient(path=chroma_path)

    if _collection is None:
        _collection = _chroma_client.get_or_create_collection(
            name="standards_collection"
        )

    return _collection


def get_openai_client():
    global _openai_client

    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        _openai_client = OpenAI(api_key=api_key)

    return _openai_client


def load_standards_from_snowflake(limit: int = 100) -> List[Dict]:
    """
    Load standard-set data from Snowflake.

    Source table:
      EDU_AI_APP.WEBAPP.STD_SET

    You can later expand this to STD_ITEM or STD_ITEM_SUBJECTIVES.
    """

    sql = """
        SELECT
            SET_ID,
            DESCRIPTION
        FROM EDU_AI_APP.WEBAPP.STD_SET
        ORDER BY SET_ID
        LIMIT %s
    """

    rows = []

    with get_snowflake_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            for set_id, description in cur.fetchall():
                rows.append(
                    {
                        "id": str(set_id),
                        "text": f"SET_ID: {set_id}\nDESCRIPTION: {description}",
                        "set_id": str(set_id),
                        "description": description or "",
                    }
                )

    return rows


@rag_bp.route("/api/rag/index-standards", methods=["POST"])
def index_standards():
    """
    Read standards from Snowflake, create embeddings, and store them in ChromaDB.

    Example:
      POST /api/rag/index-standards
      {
        "limit": 100
      }
    """

    try:
        payload = request.get_json(silent=True) or {}

        try:
            limit = int(payload.get("limit", 100))
            limit = max(1, min(2000, limit))
        except Exception:
            limit = 100

        rows = load_standards_from_snowflake(limit=limit)

        if not rows:
            return jsonify(
                message="No rows found from Snowflake",
                count=0,
                time=now_utc_iso(),
            ), 200

        ids = []
        documents = []
        metadatas = []

        for row in rows:
            ids.append(row["id"])
            documents.append(row["text"])
            metadatas.append(
                {
                    "set_id": row["set_id"],
                    "description": row["description"],
                    "source": "snowflake:EDU_AI_APP.WEBAPP.STD_SET",
                }
            )

        embedding_model = get_embedding_model()
        collection = get_chroma_collection()

        embeddings = embedding_model.encode(documents).tolist()

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return jsonify(
            message="Indexed standards into ChromaDB",
            count=len(rows),
            data={
                "collection": "standards_collection",
                "source": "EDU_AI_APP.WEBAPP.STD_SET",
            },
            time=now_utc_iso(),
        ), 200

    except Exception as e:
        return json_error(f"Failed to index standards: {e}", 500)


@rag_bp.route("/api/rag/search", methods=["GET"])
def search_standards():
    """
    Search ChromaDB without calling the LLM.

    Example:
      GET /api/rag/search?q=math&limit=5
    """

    try:
        q = (request.args.get("q") or "").strip()

        try:
            limit = int(request.args.get("limit") or 5)
            limit = max(1, min(50, limit))
        except Exception:
            limit = 5

        if not q:
            return json_error("Missing query parameter q", 400)

        embedding_model = get_embedding_model()
        collection = get_chroma_collection()

        query_embedding = embedding_model.encode([q]).tolist()

        results = collection.query(
            query_embeddings=query_embedding,
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )

        data = []

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, distance in zip(docs, metas, distances):
            data.append(
                {
                    "document": doc,
                    "metadata": meta,
                    "distance": distance,
                }
            )

        return jsonify(
            message="OK",
            query=q,
            count=len(data),
            data=data,
            time=now_utc_iso(),
        ), 200

    except Exception as e:
        return json_error(f"Failed to search RAG collection: {e}", 500)


@rag_bp.route("/api/rag/ask", methods=["POST"])
def ask_rag():
    """
    Ask a question using RAG.

    Flow:
      question
        -> embedding
        -> ChromaDB search
        -> context
        -> OpenAI LLM
        -> JSON answer

    Example:
      POST /api/rag/ask
      {
        "question": "Which standard sets are related to math?",
        "topK": 5
      }
    """

    try:
        payload = request.get_json(silent=True) or {}

        question = (payload.get("question") or "").strip()

        try:
            top_k = int(payload.get("topK", 5))
            top_k = max(1, min(20, top_k))
        except Exception:
            top_k = 5

        if not question:
            return json_error("Missing question", 400)

        embedding_model = get_embedding_model()
        collection = get_chroma_collection()
        openai_client = get_openai_client()

        query_embedding = embedding_model.encode([question]).tolist()

        results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            return jsonify(
                message="OK",
                question=question,
                answer="I could not find relevant context in the indexed standards data.",
                sources=[],
                time=now_utc_iso(),
            ), 200

        context_blocks = []

        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            context_blocks.append(
                f"Source {i + 1}:\n"
                f"Metadata: {meta}\n"
                f"Content:\n{doc}"
            )

        context = "\n\n".join(context_blocks)

        prompt = f"""
You are an education AI assistant.

Answer the user's question using ONLY the context below.
If the context does not contain enough information, say that the available data is insufficient.

Context:
{context}

Question:
{question}
"""

        response = openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You answer questions using retrieved education standards context.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
        )

        answer = response.choices[0].message.content

        sources = []
        for i in range(len(docs)):
            sources.append(
                {
                    "document": docs[i],
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                }
            )

        return jsonify(
            message="OK",
            question=question,
            answer=answer,
            sources=sources,
            time=now_utc_iso(),
        ), 200

    except ValueError as ve:
        return json_error(str(ve), 400)
    except Exception as e:
        return json_error(f"Failed to ask RAG question: {e}", 500)