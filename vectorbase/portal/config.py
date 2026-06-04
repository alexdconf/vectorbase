"""
Schema config loader.

The YAML config (`schema.yaml`) is the sole source of truth for:
  - which pgvector table + embedding column to query
  - which sentence-transformers model to use for query encoding
  - which columns to surface in the UI and how to filter them

Call `load_config(path)` once at startup (PortalConfig.ready).
Everywhere else, use `get_config()` to retrieve the singleton.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

FilterType = Literal["range", "category", "value"] | None

# Postgres column types that map to a range filter
_RANGE_TYPES = {
    "integer",
    "bigint",
    "smallint",
    "numeric",
    "real",
    "double precision",
    "float4",
    "float8",
    "date",
    "timestamp without time zone",
    "timestamp with time zone",
    "timestamptz",
}

# Date-like types within the range group (affects widget choice)
_DATE_TYPES = {
    "date",
    "timestamp without time zone",
    "timestamp with time zone",
    "timestamptz",
}


@dataclass
class FieldConfig:
    name: str
    label: str
    show_in_results: bool = True
    filter_type: FilterType = None
    # 'integer' | 'float' | 'date' | 'timestamp' | 'text' | '' …
    # Populated by generate_config; used to pick the right range widget.
    column_type: str = ""
    # Distinct values for category filters; populated at startup.
    choices: list[str] = field(default_factory=list)

    @property
    def is_date_range(self) -> bool:
        return self.filter_type == "range" and self.column_type in {
            "date",
            "timestamp",
            "timestamptz",
            "timestamp without time zone",
            "timestamp with time zone",
        }


@dataclass
class SchemaConfig:
    table: str
    embedding_column: str
    model: str
    top_k: int
    fields: list[FieldConfig]

    @property
    def result_fields(self) -> list[FieldConfig]:
        return [f for f in self.fields if f.show_in_results]

    @property
    def filter_fields(self) -> list[FieldConfig]:
        return [f for f in self.fields if f.filter_type is not None]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_config: SchemaConfig | None = None


def load_config(path: Path | str) -> SchemaConfig:
    """Parse schema.yaml and store it as the module-level singleton."""
    global _config

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"VectorBase schema config not found at {path}. "
            "Run `python manage.py generate_config` to create it."
        )

    with path.open() as fh:
        raw = yaml.safe_load(fh)

    search_cfg = raw.get("search", {})
    table = search_cfg.get("table", "")
    embedding_column = search_cfg.get("embedding_column", "embedding")
    model = search_cfg.get("model", "")
    top_k = int(search_cfg.get("top_k", 4))

    if not table:
        raise ValueError("schema.yaml must specify search.table")
    if not model:
        raise ValueError(
            "schema.yaml must specify search.model "
            "(the sentence-transformers model used when the DB was populated)"
        )

    fields: list[FieldConfig] = []
    for fd in raw.get("fields", []):
        filter_cfg = fd.get("filter") or {}
        filter_type: FilterType = filter_cfg.get("type") if filter_cfg else None
        column_type: str = filter_cfg.get("column_type", "") if filter_cfg else ""

        fields.append(
            FieldConfig(
                name=fd["name"],
                label=fd.get("label", fd["name"].replace("_", " ").title()),
                show_in_results=bool(fd.get("show_in_results", True)),
                filter_type=filter_type,
                column_type=column_type,
            )
        )

    _config = SchemaConfig(
        table=table,
        embedding_column=embedding_column,
        model=model,
        top_k=top_k,
        fields=fields,
    )
    return _config


def get_config() -> SchemaConfig:
    """Return the loaded config singleton. Raises if load_config() was not called."""
    if _config is None:
        raise RuntimeError(
            "VectorBase config not loaded. "
            "Ensure PortalConfig.ready() is calling load_config()."
        )
    return _config


def populate_choices(cfg: SchemaConfig) -> None:
    """
    Fetch distinct values for every category filter field and cache them on
    the FieldConfig object.  Called once at startup after load_config().
    """
    from django.db import connections

    category_fields = [f for f in cfg.filter_fields if f.filter_type == "category"]
    if not category_fields:
        return

    with connections["vectors"].cursor() as cursor:
        for field_cfg in category_fields:
            cursor.execute(
                f'SELECT DISTINCT "{field_cfg.name}" '
                f'FROM "{cfg.table}" '
                f'WHERE "{field_cfg.name}" IS NOT NULL '
                f'ORDER BY "{field_cfg.name}"'
            )
            field_cfg.choices = [str(row[0]) for row in cursor.fetchall()]
