"""
Search backend: embed a query string, apply metadata filters,
and return the top-k most similar rows from the vectors DB.
"""

from __future__ import annotations

from django.db import connections

# ---------------------------------------------------------------------------
# Embedding model (loaded once, on first use)
# ---------------------------------------------------------------------------
_model = None


def get_embedding_model():
    """Return the sentence-transformers model specified in the schema config."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        from portal.config import get_config

        model_name = get_config().model
        _model = SentenceTransformer(model_name)
    return _model


def encode_query(text: str) -> list[float]:
    """Encode a query string into a list of floats."""
    return get_embedding_model().encode(text).tolist()


def _vector_literal(vec: list[float]) -> str:
    """Format a float list as a pgvector literal string: '[1.0,2.0,...]'."""
    return "[" + ",".join(map(str, vec)) + "]"


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search(
    query_text: str,
    filters: dict,
    top_k: int,
) -> list[dict]:
    """
    Execute a semantic + metadata search against the vectors database.

    Parameters
    ----------
    query_text:
        Free-text query to embed.  May be empty, in which case only metadata
        filters are applied and results are returned in table order.
    filters:
        A dict keyed by filter spec:
          - range fields  → ``{field}__gte`` and/or ``{field}__lte``
          - category fields → ``{field}``  (list of selected values)
          - value fields   → ``{field}``  (substring match string)
    top_k:
        Maximum number of results to return.

    Returns
    -------
    List of dicts, each containing the result-column values plus a
    ``similarity`` key (float 0–1, or None if no query was given).
    """
    from portal.config import get_config

    cfg = get_config()

    # --- Build SELECT columns -------------------------------------------
    result_fields = cfg.result_fields
    result_cols = ", ".join(f'"{f.name}"' for f in result_fields)

    # --- Build WHERE clauses -------------------------------------------
    where_clauses: list[str] = []
    params: list = []

    for field_cfg in cfg.filter_fields:
        fname = field_cfg.name

        if field_cfg.filter_type == "range":
            gte = filters.get(f"{fname}__gte")
            lte = filters.get(f"{fname}__lte")
            if gte is not None and str(gte).strip():
                where_clauses.append(f'"{fname}" >= %s')
                params.append(gte)
            if lte is not None and str(lte).strip():
                where_clauses.append(f'"{fname}" <= %s')
                params.append(lte)

        elif field_cfg.filter_type == "category":
            values = filters.get(fname) or []
            if isinstance(values, str):
                values = [values]
            values = [v for v in values if v]
            if values:
                placeholders = ", ".join(["%s"] * len(values))
                where_clauses.append(f'"{fname}" IN ({placeholders})')
                params.extend(values)

        elif field_cfg.filter_type == "value":
            val = (filters.get(fname) or "").strip()
            if val:
                where_clauses.append(f'"{fname}" ILIKE %s')
                params.append(f"%{val}%")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    table = cfg.table
    emb_col = cfg.embedding_column

    # --- Build full SQL -------------------------------------------------
    if query_text.strip():
        vec = encode_query(query_text)
        vec_literal = _vector_literal(vec)
        sql = (
            f"SELECT {result_cols}, "
            f"1 - (\"{emb_col}\" <=> %s::vector) AS similarity "
            f'FROM "{table}" '
            f"{where_sql} "
            f'ORDER BY "{emb_col}" <=> %s::vector '
            f"LIMIT %s"
        )
        final_params = params + [vec_literal, vec_literal, top_k]
    else:
        sql = (
            f"SELECT {result_cols}, NULL AS similarity "
            f'FROM "{table}" '
            f"{where_sql} "
            f"LIMIT %s"
        )
        final_params = params + [top_k]

    # --- Execute --------------------------------------------------------
    with connections["vectors"].cursor() as cursor:
        cursor.execute(sql, final_params)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]
