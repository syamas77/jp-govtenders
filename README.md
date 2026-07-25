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

## Count matrix

Generate current KKJ search-hit totals for all six selected prefectures and three categories:

```bash
uv run python -m one_off_scripts.collect_counts
```

This makes 18 API requests and writes `one_off_scripts/counts.csv`. The CSV records the prefecture, category, total matching `search_hits`, and collection timestamp. It does not add notices to SQLite.

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
