# vectorbase

An open source Django framework for serving semantic + metadata search over a pre-populated [pgvector](https://github.com/pgvector/pgvector) database. Designed for openly sharing curated information — no JavaScript required, works with Lynx.

## How it works

Point vectorbase at any pgvector table, generate a YAML config from the schema, edit it, and deploy. The app embeds user queries locally using [sentence-transformers](https://www.sbert.net/), applies metadata filters as SQL `WHERE` clauses, and returns the top-k most similar rows.

```
User types a query + optional filters
        ↓
Query text is embedded locally (sentence-transformers)
        ↓
pgvector cosine similarity search with metadata filters
        ↓
Top-k results rendered in plain HTML
```

## Features

- **Arbitrary schema** — no code changes needed across deployments; the YAML config drives the UI
- **Three filter types** auto-detected from column types: `range` (numeric/date), `category` (select from distinct values), `value` (substring match)
- **Local embeddings** — sentence-transformers runs in-process; no external API calls at query time
- **No JavaScript** — pure server-rendered HTML, fully functional in Lynx
- **Rate limiting** — per-IP limit and a global daily quota, both configurable via env vars
- **GDPR logging** — every search is logged (query text, filters, result count, timestamp); viewable in a dashboard and the Django admin
- **Two-database architecture** — the pgvector DB is read-only; Django app state (audit log, sessions) lives in a separate DB

## Requirements

- Python 3.14+
- PostgreSQL with the [pgvector extension](https://github.com/pgvector/pgvector) (pre-populated)
- [uv](https://docs.astral.sh/uv/)

## Developer workflow

### 1. Clone and install

```bash
git clone https://github.com/your-org/vectorbase
cd vectorbase
uv sync
```

### 2. Configure environment

```bash
cp vectorbase/.env.example vectorbase/.env
$EDITOR vectorbase/.env
```

Set at minimum:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `VECTORS_DB_NAME` | Name of the pgvector database |
| `VECTORS_DB_USER` | Database user |
| `VECTORS_DB_PASSWORD` | Database password |
| `VECTORS_DB_HOST` | Database host (default: `localhost`) |
| `VECTORS_DB_PORT` | Database port (default: `5432`) |

### 3. Generate the schema config

```bash
uv run python vectorbase/manage.py generate_config
```

This introspects the pgvector database and writes `vectorbase/schema.yaml`. If there are multiple tables, you'll be prompted to choose one.

### 4. Edit `schema.yaml`

```yaml
search:
  table: my_table
  embedding_column: embedding        # auto-detected
  model: sentence-transformers/all-MiniLM-L6-v2  # set this to match your DB
  top_k: 4

fields:
  - name: title
    label: Title
    show_in_results: true
    filter: null

  - name: author
    label: Author
    show_in_results: true
    filter:
      type: category      # select from distinct values

  - name: year
    label: Year
    show_in_results: true
    filter:
      type: range         # min/max inputs
      column_type: integer
```

**Key rules:**
- Presence of a field in `fields:` means it appears in the UI. Remove a field to hide it.
- `search.model` **must** match the sentence-transformers model used when the database was populated.
- See `vectorbase/schema.yaml.example` for all filter types and options.

### 5. Migrate and run

```bash
uv run python vectorbase/manage.py migrate
uv run python vectorbase/manage.py runserver
```

The search UI is at `http://localhost:8000/`.  
The audit log dashboard is at `http://localhost:8000/audit/`.  
The Django admin is at `http://localhost:8000/admin/`.

## Configuration reference

All settings are driven by environment variables. See `vectorbase/.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | Django secret key |
| `DEBUG` | `False` | Enable Django debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `VECTORS_DB_*` | *(required)* | pgvector DB connection |
| `DEFAULT_DB_URL` | SQLite | Django app DB (audit log, sessions) |
| `CACHE_URL` | in-memory | Cache backend for rate limiting (use Redis in production) |
| `SCHEMA_CONFIG_PATH` | `schema.yaml` | Path to the schema config |
| `SEARCH_RATE_LIMIT` | `100/d` | Per-IP rate limit (`N/s\|m\|h\|d`) |
| `GLOBAL_DAILY_QUOTA` | `10000` | Max total searches per calendar day (UTC) |

## Project structure

```
vectorbase/
├── pyproject.toml
├── schema.yaml.example          # annotated config reference
├── README.md
└── vectorbase/                  # Django project root
    ├── manage.py
    ├── .env.example
    ├── schema.yaml              # your generated + edited config (commit this)
    ├── vectorbase/              # project settings, urls
    ├── portal/                  # search UI, rate limiting, quota
    │   ├── config.py            # YAML config loader
    │   ├── search.py            # embedding + pgvector SQL
    │   ├── forms.py             # dynamic filter form
    │   ├── views.py             # search view
    │   └── management/commands/generate_config.py
    └── logs/                    # GDPR logging dashboard
        ├── models.py            # SearchLog
        └── views.py             # dashboard
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
