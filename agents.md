# Agents Guide — jp-govtenders

Research tool for collecting Japanese government procurement notices from the KKJ (官公需情報ポータルサイト) API.

## Project overview

- Fetches XML from the KKJ search API via `httpx`
- Parses XML into Pydantic models (`src/models.py`, `src/parser.py`)
- Stores notices in SQLite with deduplication by KKJ `Key` (`src/database.py`)
- CLI entry point: `src/main.py` (subcommands: `count`, `collect`)
- No AI features, no web server, no frontend — pure data collection

## Running the project

```bash
# Count notices (no DB write)
uv run python -m src.main count --lg-code 13 --category 3

# Collect and save to SQLite
uv run python -m src.main collect --lg-code 13 --category 3 --count 1000 --database notices.sqlite

# Keyword search
uv run python -m src.main collect --query 官公需 --count 100 --database notices.sqlite
```

At least one of `--query`, `--project-name`, `--organization-name`, or `--lg-code` is required by the KKJ API.

## Key domain terms

| Term | Meaning |
|------|---------|
| KKJ | 官公需情報ポータルサイト — the official JP government procurement portal |
| `LG_Code` | Prefecture code (e.g. `13` = Tokyo, `27` = Osaka, `01` = Hokkaido) |
| `Category` | `1` = 物品 (goods), `2` = 工事 (construction), `3` = 役務 (services) |
| `CFT_Issue_Date` | Date range filter, e.g. `2026-07-01/2026-07-31` |
| `Key` | Unique notice identifier used for deduplication in SQLite |
| `search_hits` | Total API result count — may exceed the max `Count` of 1000 |

## Source layout

```
src/
  client.py     # KkjClient — wraps httpx, builds query params, calls the API
  parser.py     # XML → SearchResponse (Pydantic)
  models.py     # Pydantic models: SearchResponse, Notice, etc.
  database.py   # SQLite helpers: connect(), insert_notices()
  collector.py  # collect_once() — orchestrates client → parser → DB
  main.py       # argparse CLI: count / collect subcommands
main.py         # Thin wrapper so `python main.py` works alongside `python -m src.main`
```

## Known limitations / gotchas

- **No pagination**: The KKJ API does not document an offset parameter. `collect_once()` makes a single request. If `search_hits > count` (max 1000), results are incomplete.
- **Workaround**: Split large result sets by date range using `--cft-issue-date` (e.g. one month per run).
- **Deduplication**: Re-running the same query is safe — existing rows are skipped by KKJ `Key`.
- **Python 3.14+** required (`requires-python = ">=3.14"` in `pyproject.toml`).

## When adding new features

- New API parameters → add to `KkjClient.search()` in `src/client.py`, then surface via `_add_search_arguments()` in `src/main.py`.
- New data fields → update `src/models.py` (Pydantic) and `src/parser.py` (XML parsing), then add the column in `src/database.py`.
- Keep things minimal — no FastAPI, no AI layer, no web frontend unless explicitly requested.
