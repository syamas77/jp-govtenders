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

Purpose: download official Japanese government spreadsheets and create normalized reference data for the six selected prefectures.

```bash
uv run python -m one_off_scripts.collect_prefecture_reference_data
```

Outputs:

```text
reference_data/prefecture_population.csv
reference_data/prefecture_area.csv
```

The population file contains 2022–2025 values. The 2022–2024 values are Statistics Bureau estimates converted from thousands to people; 2025 values are preliminary Population Census counts. The area file contains October 1, 2025 GSI area values in km². Source units, dates, status, and URLs are preserved.

## IT services taxonomy

`reference_data/it_service_taxonomy_v1.json` is version `1.0.0` of the researcher-defined title taxonomy for IT-related notices within KKJ category `3` (`役務` / services). It is not an official KKJ classification.

Load it in a notebook:

```python
import json
from pathlib import Path

taxonomy = json.loads(
    Path("reference_data/it_service_taxonomy_v1.json").read_text()
)

it_patterns = taxonomy["patterns"]
core_it_columns = taxonomy["core_it_delivery_subgroups"]
subgroup_definitions = taxonomy["subgroup_definitions"]
```

The JSON documents each subgroup's meaning, examples, and boundaries. Detailed subgroups can overlap. At the exclusive high level, core technical delivery takes priority; `digital_or_ai_adjacent` contains data/digital or AI matches that do not match a core subgroup.

### Validation sample and review process

Validation used the 6,000 sampled service notices in SQLite (`1,000 notices × 6 prefectures`). Because those API responses are capped and their ordering is undocumented, this sample was used to develop the taxonomy—not to estimate the complete IT-services market.

1. Apply the initial regular expressions to `project_name`.
2. Set `it_related=True` when any subgroup matches.
3. Manually inspect samples from every matched subgroup for obvious false positives and boundary cases.
4. Randomly sample 100 unmatched titles with `random_state=42` to look for false negatives.
5. Record `review_decision`, `suggested_it_tag`, and `review_notes` for each title.
6. Update patterns only for clear misses, then inspect all newly matched notices.
7. Randomly sample another 100 unmatched titles with `random_state=43`.
8. Freeze version 1 when the second review finds no clear new core-IT keyword family.

Review decision meanings:

| Decision | Meaning |
| --- | --- |
| `IT` | clear false negative that should inform a taxonomy update |
| `not_IT` | correctly excluded based on the project title |
| `uncertain` | title is insufficient or work sits near the chosen IT/software boundary |

Round one:

```text
90 not IT
4 clear missed IT notices
6 uncertain or boundary cases
```

The four clear misses added conservative support for system provision, software-context licenses, `データ化`, RAG, and PC/device kitting. The updated taxonomy matched 333 of the 6,000 sampled service notices, compared with 322 before the update.

Round two:

```text
89 not IT
0 clear missed core IT notices
11 uncertain, boundary, or insufficient-title cases
```

Review artifacts:

```text
analysis_outputs/unmatched_service_titles_review.csv
analysis_outputs/unmatched_service_titles_reviewed.csv
analysis_outputs/newly_matched_after_taxonomy_update.csv
analysis_outputs/unmatched_service_titles_review_round2.csv
analysis_outputs/unmatched_service_titles_review_round2_reviewed.csv
```

Limitations:

- Most review decisions use titles rather than full linked documents.
- Two samples of 100 do not prove perfect precision or recall.
- Generic titles and filenames require source-document inspection.
- Counts describe notices, not necessarily unique underlying projects.
- Reissued or corrected notices can have different KKJ keys.
- Revalidate for taxonomy drift after collecting the larger historical dataset.

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



## IT services case study: next steps

Research question:

> How has public-sector IT-service procurement changed across six Japanese prefectures, which technology fields are growing, and which organizations drive that demand?

1. **Implement month-partitioned service collection.** Collect category `3` notices for 2022–2025 by prefecture and month. Check `search_hits`; split periods exceeding 1,000 into weeks or days. Deduplicate by KKJ `Key` and record completed periods.
2. **Apply taxonomy version 1.** Tag the more complete historical service dataset and perform a small drift review.
3. **Measure IT-service activity.** Calculate IT notice counts, IT share of services, annual and year-over-year changes, subgroup growth, and prefecture differences.
4. **Analyze issuing organizations.** Identify top IT procurers, top organizations by subgroup, and organizations contributing most to annual increases or decreases. Issuers are not necessarily contract winners.
5. **Investigate repeated projects.** Analyze normalized-title repetition by organization and year; do not present notice counts as unique-project counts without qualification.
6. **Run a contract-detail pilot.** Inspect 50–100 validated IT notices and official pages/attachments. Keep estimated prices, ceilings, bids, winning prices, and final contract amounts separate. Record tax status, deadline, contract period, and source.
7. **Evaluate actionable fields.** Assess link validity, attachments, technical scope, eligibility requirements, and whether notices are current or expired.
8. **Validate user value before a dashboard.** Produce a research report and show it to software consultancies, government contractors, cloud/security vendors, and procurement researchers before building a frontend.

Current limitations:

- The KKJ API documents a maximum return count of 1,000 and no pagination.
- `CftIssueDate` may be the announcement date or KKJ acquisition date when the announcement date is unavailable.
- Notice counts do not measure spending or contract value.
- Price analysis remains a TODO until amount types and extraction reliability are validated.
