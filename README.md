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

### Apply the taxonomy to historical notices

Run the reproducible classifier against the completed historical database:

```bash
uv run python -m one_off_scripts.classify_it_service_notices
```

Default inputs:

```text
service_history.sqlite
reference_data/it_service_taxonomy_v1.json
```

Outputs:

```text
analysis_outputs/service_notices_classified_v1.csv
analysis_outputs/it_service_notices_v1.csv
analysis_outputs/it_service_classification_v1_metadata.json
```

The first CSV contains every historical service notice and the second contains only `it_related=True` notices. Both include detailed subgroup booleans, `matched_subgroups`, `subgroup_count`, `core_it_delivery`, `digital_or_ai_adjacent`, and `taxonomy_version`. Large `raw_xml` and `project_description` fields remain in SQLite rather than being duplicated in the CSVs. The metadata file records the taxonomy SHA-256 hash, source paths, row counts, and subgroup counts.

The version 1 run classified 15,230 services and identified 712 IT-related notices: 628 core IT-delivery notices and 84 exclusively digital/AI-adjacent notices. These counts remain provisional until historical taxonomy-drift validation is complete.

Override any paths when needed:

```bash
uv run python -m one_off_scripts.classify_it_service_notices \
  --database service_history.sqlite \
  --taxonomy reference_data/it_service_taxonomy_v1.json \
  --output analysis_outputs/service_notices_classified_v1.csv \
  --it-output analysis_outputs/it_service_notices_v1.csv \
  --metadata-output analysis_outputs/it_service_classification_v1_metadata.json
```

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

Note: the KKJ API guide documents `Count` up to 1000, but does not document pagination. If `search hits` is greater than 1000, this first approach will not collect every matching notice.

## Historical service collection

The restartable historical collector requests category `3` (`役務` / services) by calendar month. If a period has more than 1,000 hits, it recursively splits the inclusive date range in half until each leaf period is within the documented return cap. A one-day period above the cap is recorded as failed rather than silently treated as complete.

Collect 2022–2025 for all six selected prefectures:

```bash
uv run python -m src.main collect-services-history \
  --start-year 2022 \
  --end-year 2025 \
  --database service_history.sqlite
```

Collect one prefecture, or repeat `--lg-code` for a subset:

```bash
uv run python -m src.main collect-services-history \
  --start-year 2022 \
  --end-year 2025 \
  --lg-code 13 \
  --database service_history.sqlite
```

The default prefecture codes are `01`, `13`, `14`, `23`, `27`, and `40`. The collector uses a reusable HTTP connection and waits at least 0.2 seconds between requests; override this with `--request-delay` if needed.

Collection state is stored in the same database in `collection_periods`. Leaf periods are marked `completed` only when the number returned equals `search_hits`; oversized parents are marked `split`, and errors are marked `failed`. Notices are deduplicated by KKJ `Key` in `notices`.

Rerun the same command safely after interruption or failure. Completed leaves are skipped, split parents resume their children, and failed periods are retried. The command exits nonzero if any periods remain failed.

Inspect progress:

```sql
SELECT status, COUNT(*)
FROM collection_periods
GROUP BY status;
```

## IT services case study: project checklist

Research question:

> How has public-sector IT-service procurement changed across six Japanese prefectures, which technology fields are growing, and which organizations drive that demand?

### Completed

- [x] Implement the documented KKJ API client, XML parser, Pydantic models, SQLite persistence, and `count`/`collect` CLI commands.
- [x] Build the initial `notices.sqlite` exploratory sample with 18,000 notices across six prefectures and three official categories.
- [x] Collect complete search-hit totals by prefecture/category, completed year, and current year-to-date.
- [x] Collect population and land-area reference data with source metadata.
- [x] Select category `3` (`役務` / services) as the official scope for the IT-services case study.
- [x] Define the researcher-created, multi-label IT subgroup taxonomy and core-versus-adjacent high-level logic.
- [x] Validate the initial taxonomy with matched-title inspection and two deterministic random samples of 100 unmatched titles.
- [x] Freeze and document `reference_data/it_service_taxonomy_v1.json`, including subgroup meanings, examples, boundaries, and limitations.
- [x] Implement restartable monthly collection with recursive date splitting, response-count verification, KKJ-key deduplication, and persistent period status.
- [x] Complete 2022–2025 historical service collection for all six prefectures in `service_history.sqlite`.
- [x] Verify 288 completed monthly periods, zero failed periods, and 15,230 expected/returned/stored service notices. No month required splitting.
- [x] Create and run a reproducible classification script that loads taxonomy version 1, tags all 15,230 historical notices, and exports analysis-ready data plus provenance metadata.
- [x] Save a 24-row collection-completeness audit by year and prefecture; annual search hits, completed-period hits, returned notices, and 15,230 stored notices all agree.
- [x] Generate deterministic historical validation samples: 100 unmatched notices and 100 unique matched notices stratified across active subgroups, years, and prefectures.

### Next session

- [x] Manually review both historical validation samples. The unmatched sample found 3 clear false negatives, 93 non-IT notices, and 4 uncertain cases; the matched sample found 89 correct IT matches, 7 clear false positives, and 4 uncertain cases. Because sampling was stratified, these ratios are diagnostic rather than population error-rate estimates.
- [x] Draft taxonomy `1.1.0-candidate`, add targeted subgroup exclusions, reclassify the full dataset, and inspect all changed rows.
- [x] Run the first independent simple-random holdout after excluding development samples. The matched holdout found 135 correct IT, 9 clear false positives, 6 uncertain, and 4 correct IT notices with tag concerns; the unmatched holdout found 7 clear false negatives, 1 uncertain, and 192 non-IT notices.
- [x] Treat the first holdout as a validation failure, create `1.1.0-candidate2`, address physical-system false positives and remaining terminology gaps, and inspect all 180 changes from v1.
- [x] Generate a fresh final holdout for candidate 2 after excluding 873 previously reviewed/development keys.
- [x] Manually adjudicate the final candidate-2 holdout: 136 correct IT, 12 false positives, and 2 uncertain among 150 matched notices; 191 non-IT, 8 false negatives, and 1 uncertain among 200 unmatched notices. Six otherwise correct IT notices also had subgroup or core/adjacent concerns.
- [x] Reject candidate 2 for publication rather than freezing a taxonomy that failed its untouched holdout.
- [x] Stop example-by-example Candidate 3 patching and create a simplified concept-based v1.1 candidate directly from frozen v1. The lean rules cover general IT concepts and short activity-level boundaries without enumerating particular medical devices, cameras, or equipment models.
- [x] Review all 189 lean-candidate differences from v1: 88 concept additions, 38 concept removals, and 63 retags.
- [x] Generate one final untouched lean-candidate holdout after excluding 1,269 previously reviewed/development keys.
- [x] Adjudicate the final lean holdout without further regex tuning: 138 correct IT, 7 false positives, and 5 uncertain among 150 matched notices; 186 non-IT, 12 false negatives, and 2 uncertain among 200 unmatched notices. Six otherwise correct IT notices had tag concerns.
- [x] Freeze lean taxonomy v1.1 strictly as a reproducible title-based IT-services indicator—not a comprehensive census—and generate final classified report datasets and metadata.
- [ ] If clear new terminology is found, create a new taxonomy version rather than silently changing version 1.
- [ ] Freeze the validated historical classification before interpreting trends.

### Core analysis

- [ ] Calculate annual IT notice counts, IT share of all services, and year-over-year changes.
- [ ] Analyze subgroup counts, shares, overlaps, and growth by year.
- [ ] Compare prefectures using counts, IT share of services, and notices per 100,000 residents.
- [ ] Identify top issuing organizations overall and by subgroup, plus organizations contributing most to annual increases or decreases.
- [ ] Investigate normalized-title repetition by organization and year; do not present notice counts as unique projects without qualification.
- [ ] Keep incomplete 2026 year-to-date results separate from completed 2022–2025 calendar years.

### Case report and later validation

- [ ] Write the case-study methodology, completeness audit, taxonomy validation, results, and limitations.
- [ ] Run a 50–100 notice contract-detail pilot using official pages and attachments.
- [ ] Keep estimated prices, ceilings, bids, winning prices, and final contract amounts separate; record tax status and source evidence.
- [ ] Assess link validity, attachment availability, technical scope, eligibility requirements, deadlines, and contract periods.
- [ ] Validate the report's usefulness with software consultancies, government contractors, cloud/security vendors, and procurement researchers before considering a dashboard.

Current limitations:

- The KKJ API documents a maximum return count of 1,000 and no pagination.
- `CftIssueDate` may be the announcement date or KKJ acquisition date when the announcement date is unavailable.
- Notice counts do not measure spending or contract value.
- Price analysis remains a TODO until amount types and extraction reliability are validated.
