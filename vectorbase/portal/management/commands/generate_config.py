"""
Management command: generate_config

Introspects the configured `vectors` database and writes a `schema.yaml`
starter file.  Developers then:
  1. Set ``search.model`` to the sentence-transformers model used at populate time.
  2. Remove any fields they don't want to expose in the UI.
  3. Adjust ``label`` values for display names.
  4. Run ``python manage.py migrate`` to set up the app DB tables.

Usage
-----
    python manage.py generate_config
    python manage.py generate_config --table my_table
    python manage.py generate_config --table my_table --output path/to/schema.yaml
    python manage.py generate_config --table my_table --force
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

# Postgres types that map to a range filter
_RANGE_INTEGER_TYPES = {"integer", "bigint", "smallint", "int2", "int4", "int8"}
_RANGE_FLOAT_TYPES = {
    "numeric",
    "real",
    "double precision",
    "float4",
    "float8",
    "decimal",
}
_RANGE_DATE_TYPES = {
    "date",
    "timestamp without time zone",
    "timestamp with time zone",
    "timestamptz",
}
_RANGE_TYPES = _RANGE_INTEGER_TYPES | _RANGE_FLOAT_TYPES | _RANGE_DATE_TYPES

# Maximum distinct values before a text column is treated as `value` not `category`
_CATEGORY_THRESHOLD = 50

# How many rows we scan to estimate distinct counts (avoids full-table scans)
_DISTINCT_SAMPLE_LIMIT = _CATEGORY_THRESHOLD + 1


class Command(BaseCommand):
    help = "Introspect the vectors DB schema and generate schema.yaml"

    def add_arguments(self, parser):
        parser.add_argument(
            "--table",
            help="Table name to introspect.  If omitted, available tables are listed.",
        )
        parser.add_argument(
            "--output",
            help="Output file path (default: schema.yaml next to manage.py)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite an existing schema.yaml without prompting.",
        )

    def handle(self, *args, **options):
        table_name = options.get("table")
        output_path = Path(options.get("output") or self._default_output())
        force = options.get("force", False)

        with connections["vectors"].cursor() as cursor:
            # --- Resolve table name ------------------------------------
            if not table_name:
                table_name = self._choose_table(cursor)

            # --- Validate table exists ---------------------------------
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name   = %s
                """,
                [table_name],
            )
            if cursor.fetchone()[0] == 0:
                raise CommandError(
                    f"Table '{table_name}' not found in the public schema "
                    "of the vectors database."
                )

            # --- Introspect columns ------------------------------------
            cursor.execute(
                """
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = %s
                ORDER BY ordinal_position
                """,
                [table_name],
            )
            columns = cursor.fetchall()

        # --- Build YAML structure -------------------------------------
        embedding_column = None
        fields = []

        with connections["vectors"].cursor() as cursor:
            for col_name, data_type, udt_name in columns:
                # pgvector columns appear with udt_name = 'vector'
                if udt_name == "vector" or data_type == "USER-DEFINED" and "vector" in udt_name:
                    if embedding_column is None:
                        embedding_column = col_name
                    # Don't add the embedding column to the fields list
                    continue

                filter_cfg, column_type = self._infer_filter(
                    cursor, table_name, col_name, data_type
                )

                field_entry: dict = {
                    "name": col_name,
                    "label": col_name.replace("_", " ").title(),
                    "show_in_results": True,
                }
                if filter_cfg:
                    field_entry["filter"] = {"type": filter_cfg}
                    if column_type:
                        field_entry["filter"]["column_type"] = column_type
                else:
                    field_entry["filter"] = None

                fields.append(field_entry)

        if embedding_column is None:
            self.stderr.write(
                self.style.WARNING(
                    "No pgvector column detected.  Set `search.embedding_column` "
                    "manually in the generated file."
                )
            )
            embedding_column = "embedding"

        config = {
            "search": {
                "table": table_name,
                "embedding_column": embedding_column,
                "model": "FILL_IN_MODEL_NAME",  # e.g. sentence-transformers/all-MiniLM-L6-v2
                "top_k": 4,
            },
            "fields": fields,
        }

        # --- Write output ---------------------------------------------
        if output_path.exists() and not force:
            self.stderr.write(
                self.style.WARNING(f"{output_path} already exists.")
            )
            confirm = input("Overwrite? [y/N] ").strip().lower()
            if confirm != "y":
                self.stdout.write("Aborted.")
                sys.exit(0)

        with output_path.open("w") as fh:
            fh.write(
                "# VectorBase schema config\n"
                "# Generated by: python manage.py generate_config\n"
                "#\n"
                "# 1. Set search.model to the sentence-transformers model used\n"
                "#    when the database was populated.\n"
                "# 2. Remove fields you don't want to expose in the UI.\n"
                "# 3. Adjust `label` values for display names.\n"
                "# 4. Run: python manage.py migrate\n"
                "\n"
            )
            yaml.dump(config, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

        self.stdout.write(self.style.SUCCESS(f"Schema config written to {output_path}"))
        self.stdout.write(
            "  Next step: edit schema.yaml, then run `python manage.py migrate`"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _default_output(self) -> Path:
        """Return schema.yaml relative to manage.py (the Django project root)."""
        from django.conf import settings

        return settings.BASE_DIR / "schema.yaml"

    def _choose_table(self, cursor) -> str:
        """List user tables and ask the developer to choose one."""
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type   = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        tables = [row[0] for row in cursor.fetchall()]
        if not tables:
            raise CommandError("No tables found in the public schema of the vectors database.")

        if len(tables) == 1:
            self.stdout.write(f"Found one table: {tables[0]}")
            return tables[0]

        self.stdout.write("Available tables:")
        for i, t in enumerate(tables, 1):
            self.stdout.write(f"  {i}. {t}")

        while True:
            choice = input(f"Choose a table [1–{len(tables)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(tables):
                return tables[int(choice) - 1]
            self.stderr.write("Invalid choice. Enter a number from the list.")

    def _infer_filter(
        self,
        cursor,
        table: str,
        col: str,
        data_type: str,
    ) -> tuple[str | None, str]:
        """
        Return ``(filter_type, column_type)`` for a column.

        ``filter_type`` is one of ``'range'``, ``'category'``, ``'value'``,
        or ``None`` (no filter widget).
        ``column_type`` is a normalised type string used by the form builder.
        """
        dt = data_type.lower()

        if dt in _RANGE_INTEGER_TYPES:
            return "range", "integer"
        if dt in _RANGE_FLOAT_TYPES:
            return "range", "float"
        if dt in _RANGE_DATE_TYPES:
            return "range", dt  # preserve 'date' vs 'timestamp …'

        if dt in ("boolean",):
            return "category", "boolean"

        if dt in ("text", "character varying", "character", "varchar", "char"):
            # Sample distinct count to decide category vs value
            try:
                cursor.execute(
                    f'SELECT COUNT(*) FROM ('
                    f'SELECT DISTINCT "{col}" FROM "{table}" LIMIT %s'
                    f') _sub',
                    [_DISTINCT_SAMPLE_LIMIT],
                )
                distinct_count = cursor.fetchone()[0]
            except Exception:  # noqa: BLE001
                distinct_count = _DISTINCT_SAMPLE_LIMIT + 1

            if distinct_count <= _CATEGORY_THRESHOLD:
                return "category", "text"
            return "value", "text"

        # uuid, jsonb, arrays, etc. — offer value (substring) filter
        if dt in ("uuid",):
            return "value", dt

        # Unknown or complex types — no filter by default
        return None, dt
