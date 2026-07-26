# jp-govtenders

Research code for collecting Japanese government procurement notices from the official KKJ API.

## Current scope

- Minimal KKJ HTTP client using `httpx`
- XML parser into Pydantic models
- Simple SQLite storage with duplicate avoidance by KKJ `Key`
- No AI features, web frontend, or FastAPI

## Usage

Count matching notices without saving them:

```bash
uv run python -m src.main count --lg-code 13
uv run python -m src.main count --lg-code 13 --category 3
```

Collect and save notices to SQLite:

```bash
uv run python -m src.main collect --lg-code 13 --category 3 --count 100 --database notices.sqlite
uv run python -m src.main collect --query 官公需 --count 10 --database notices.sqlite
```

The KKJ API guide says one of `Query`, `Project_Name`, `Organization_Name`, or `LG_Code` is required.

## Important terms

### Query

`--query` is a keyword search.

Example:

```bash
uv run python -m src.main collect --query 官公需 --count 1000 --database notices.sqlite
```

This searches for notices matching the keyword `官公需`, roughly meaning public/government procurement.

If you omit `--query` and use only `--lg-code 13 --category 3`, that means no keyword filter is applied. The API searches all Tokyo service notices, not only notices containing a specific word.

### LG_Code

`LG_Code` is the prefecture filter from the KKJ API guide. It likely means local government code. The codes follow Japanese prefecture codes.

Useful starting prefectures:

| LG_Code | Prefecture | Why useful |
| --- | --- | --- |
| `13` | Tokyo | largest public/economic center |
| `27` | Osaka | major urban economy |
| `14` | Kanagawa | large population and industry |
| `23` | Aichi | manufacturing/industrial region |
| `40` | Fukuoka | major Kyushu hub |
| `01` | Hokkaido | large regional/public works market |

### Category

KKJ category codes:

| Category | Japanese | English |
| --- | --- | --- |
| `1` | 物品 | goods / supplies / products |
| `2` | 工事 | construction / public works |
| `3` | 役務 | services |

## One-off analysis scripts

Run these commands from the project root. The scripts query `search_hits` for analysis; they do not insert procurement notices into `notices.sqlite`. Each run overwrites its output CSV unless a different `--output` path is supplied.

### `collect_counts.py`: prefecture/category snapshot

Purpose: retrieve the current total number of matching notices for every combination of the six selected prefectures and three official categories.

```text
6 prefectures × 3 categories = 18 API requests and 18 CSV rows
```

Run with the default output:

```bash
uv run python -m one_off_scripts.collect_counts
```

Output:

```text
one_off_scripts/counts.csv
```

The CSV includes LG code, prefecture, category, total `search_hits`, and the UTC collection timestamp. Use it to compare category totals and category ratios by prefecture.

Choose another output file:

```bash
uv run python -m one_off_scripts.collect_counts --output data/counts.csv
```

### `collect_annual_counts.py`: completed-year trends

Purpose: retrieve annual notice totals by prefecture and category using the documented `CFT_Issue_Date` filter. Use this CSV for annual notice-count trends instead of the capped 1,000-record SQLite samples.

The default range is the completed calendar years 2022–2025:

```bash
uv run python -m one_off_scripts.collect_annual_counts
```

Default output:

```text
one_off_scripts/annual_counts.csv
```

The default run makes:

```text
4 years × 6 prefectures × 3 categories = 72 API requests and 72 CSV rows
```

Choose another inclusive year range:

```bash
uv run python -m one_off_scripts.collect_annual_counts --start-year 2023 --end-year 2025
```

Choose another output file:

```bash
uv run python -m one_off_scripts.collect_annual_counts \
  --start-year 2023 \
  --end-year 2025 \
  --output data/annual_counts.csv
```

`period_start` and `period_end` record the exact inclusive date filter. `collected_at` records when the totals were requested from KKJ. Do not compare a partial current year directly with completed calendar years.

### `collect_ytd_counts.py`: current year-to-date snapshot

Purpose: retrieve current-year totals from January 1 through a chosen cutoff date. Keep this analysis separate from the completed-year trend chart.

Use today's date in Japan as the cutoff:

```bash
uv run python -m one_off_scripts.collect_ytd_counts
```

Default output:

```text
one_off_scripts/ytd_counts.csv
```

This makes 18 API requests and writes 18 rows. Use an explicit cutoff date to make the result reproducible:

```bash
uv run python -m one_off_scripts.collect_ytd_counts --as-of-date 2026-07-26
```

Choose another output file:

```bash
uv run python -m one_off_scripts.collect_ytd_counts \
  --as-of-date 2026-07-26 \
  --output data/ytd_counts_2026-07-26.csv
```

The YTD CSV includes `period_start`, `period_end`, `is_complete_year`, and `collected_at`, making it explicit that the period is not a complete calendar year.

### `collect_prefecture_reference_data.py`: population and land area

Purpose: download official Japanese government spreadsheets and create normalized population and area reference data for the six selected prefectures.

```bash
uv run python -m one_off_scripts.collect_prefecture_reference_data
```

Outputs:

```text
reference_data/prefecture_population.csv
reference_data/prefecture_area.csv
```

The population CSV contains 24 rows (`2022–2025 × 6 prefectures`). The 2022–2024 values are Statistics Bureau Population Estimates published in thousands and converted to people. The 2025 values are preliminary 2025 Population Census counts published in people. The CSV preserves source units, series, status, date, and URL so this methodology difference remains visible.

The area CSV contains the October 1, 2025 area in km² from the GSI area survey, as reproduced in the preliminary 2025 Population Census table. Use population to calculate notices per 100,000 residents. Use area separately to calculate notices per 1,000 km²; it is not part of a per-capita calculation.

The script overwrites both reference CSVs when run.

## Suggested first analysis dataset

Start with counts by prefecture and category:

```bash
uv run python -m src.main count --lg-code 13 --category 1
uv run python -m src.main count --lg-code 13 --category 2
uv run python -m src.main count --lg-code 13 --category 3
```

Repeat for `27`, `14`, `23`, `40`, and `01`.

Then collect rows:

```bash
uv run python -m src.main collect --lg-code 13 --category 1 --count 1000 --database notices.sqlite
uv run python -m src.main collect --lg-code 13 --category 2 --count 1000 --database notices.sqlite
uv run python -m src.main collect --lg-code 13 --category 3 --count 1000 --database notices.sqlite
```

Repeat for the other LG codes.

Note: the KKJ API guide documents `Count` up to 1000, but does not document pagination. If `search hits` is greater than 1000, this first approach will not collect every matching notice. Later we can improve coverage by splitting requests by date range with `--cft-issue-date`.



Questions I want to be answered for my analysis:


1. I want to look at how many procurement notices per capital grouped by each prefecture name (we would have to get km squared per vol)
## TODO: requires a reliable award/contract value data source and a precise definition of "contract price"
2. Obviously but like I would want to know the average contract price?? for each industry

3. Search hits grouped by each category across all prefectures?? and also separate by prefecture
4. Also later, queries with keywords with system, it related software stuff
5. Are there any organizations that are top across all categories for each prefecture? 
6. In general, what are the top common organizations, and which category 
7. Which category is the largest in each prefecture (use the search hits)
8. How does procurement activity chagne over itme
9. 

### We should try to get the contract value, the population, and the area in the future. As well as any other information, and also dates that would be important. Seeing either a growth or decline of these notices over time would be cool.
