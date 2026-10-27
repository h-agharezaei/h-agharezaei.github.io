+++
date = '2027-01-14T10:00:00+03:30'
draft = false
title = 'JSONB and full-text search'
description = 'PostgreSQL JSONB and full-text search with real runs: @> and ? operators, GIN index sizes and buffers, tsvector, stemming, Persian text and pg_trgm.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "jsonb", "full-text-search", "gin"]
cover = { image = "/images/covers/db-jsonb-fulltext-search.png", alt = "JSONB and full-text search", hiddenInSingle = true }
+++

In the [previous post](/posts/db-locks-deadlocks/) we looked at locks. Here is a different question: what do you do with data that does not fit neat columns (product attributes, settings), and how do you search text without `LIKE '%...%'` scanning the whole table? PostgreSQL answers both with the {{< term "gin-index" "GIN index" >}}, a cousin of the [B-tree](/posts/db-indexes-btree-explain/) that you already know. Plans are read as in [the planner post](/posts/db-planner-statistics/).

> Everything ran on a real PostgreSQL 18.3. The data is deterministic (`i % n`, no random). The machine was busy, so there are no timings, only buffer counts. The 1000-row `products` table from the shared `shop` schema got an `attrs` column; for index tests I built a 200k-row table, because indexes on 1000 rows prove nothing.

## JSONB operators

{{< term "jsonb" "JSONB" >}} stores parsed JSON. I filled `products.attrs` with `jsonb_build_object('color', ..., 'size', ..., 'weight_g', ..., 'tags', ...)`:

```text
 1 | {"size": "M", "tags": ["eco"], "color": "green", "weight_g": 110}
21 | {"size": "M", "tags": ["sale", "new"], "color": "green", "weight_g": 310}

attrs -> 'color'  = "green" (jsonb)     attrs ->> 'color' = green (text)
attrs -> 'tags' -> 0 = "sale"
attrs @> '{"color":"blue","size":"XL"}'      -> 50 rows
attrs -> 'tags' ? 'sale'                     -> 428
attrs -> 'tags' ?| array['new','nothing']    -> 142
attrs @> '{"tags":["sale","new"]}'           -> 142

SELECT jsonb_path_query(attrs, '$.tags[*]') ... WHERE id = 21;   "sale", "new"
jsonb_path_exists(attrs, '$ ? (@.weight_g > 580 && @.color == "white")')  -> ids 49, 99, 149
```

`->` returns JSONB, `->>` returns text, `@>` means "contains", `?` means "key or string element exists", `?|` means any of. `jsonb_path_*` runs a SQL/JSON path expression.

## GIN: before and after

On 200k rows, the query `attrs @> '{"color":"white","size":"L","batch":1234}'` returns 100 rows:

| index | buffers (index + heap) | index size |
|---|---|---|
| none (Seq Scan) | 3648 | - |
| `gin (attrs)` (`jsonb_ops`) | 201 + 100 = 301 | 3576 kB |
| `gin (attrs jsonb_path_ops)` | 33 + 100 = 133 | 2464 kB |

The heap is 29 MB. `jsonb_path_ops` is smaller and faster for `@>`, but according to the docs it does not support `?`. I checked: with only that index, `attrs ? 'gift'` (40 rows) went back to a Seq Scan with 3648 buffers; with `jsonb_ops` it used the index and 5 buffers. Pick by the operators you really use.

## JSONB or real columns? (my judgment)

Use JSONB for attributes that differ per row or that you only filter occasionally. Use real columns for anything central: joins, uniqueness, foreign keys. Two costs I could show:

```text
UPDATE products SET attrs = '{"colour":"red","weight_g":"heavy"}' WHERE id = 1;   -- UPDATE 1
```

Nothing stops a typo in a key or a string where a number belongs, unless you add `CHECK` constraints. And an update rewrites the whole value: a row with a 96 KB document, table 152 kB. After 10 updates of one small key inside it with `jsonb_set`, `pg_table_size` was 1128 kB; 10 updates of a separate `int` column left it at 1128 kB (no growth). That is the {{< term "mvcc" "MVCC" >}} cost from the [VACUUM post](/posts/db-mvcc-vacuum/) times the document size.

## Full-text search

A {{< term "tsvector" "tsvector" >}} is a document turned into normalized words. {{< term "stemming" "Stemming" >}} comes from the configuration:

```text
to_tsvector('english', 'The runners were running; she runs and ran daily')
 'daili':9 'ran':8 'run':4,6 'runner':2
to_tsvector('english','running') @@ to_tsquery('english','run')  -> t
to_tsvector('simple','running')  @@ to_tsquery('simple','run')   -> f
websearch_to_tsquery('english','"red shoes" -boots or sandals')
 'red' <-> 'shoe' & !'boot' | 'sandal'
```

Stop words vanish and `ran` is not reduced to `run`. On 100k generated product texts: `ILIKE '%run%'` found 42857 rows (it also hits "runners"), the `english` search for `run` 28571, and the `simple` search for `running` 14285. `ts_rank` orders results: a text with "shoes" three times scored 0.0827, once 0.0608.

For speed, I stored the vector in a {{< term "generated-column" "generated column" >}} (`tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED`) and indexed it with GIN (7032 kB). Query `tents & hiking` (1428 rows, 1.4%) used 2820 buffers computing the vector on the fly and 2816 with the column alone; with the index, 1444, a modest win because the hits are spread over all pages. A rare query (`tents & hiking & 57`, one row): 2816 buffers before, 15 after.

## Persian text

`\dF` listed 30 configurations: `arabic` and `hindi` exist, **no Persian one**. With `simple`:

```text
to_tsvector('simple', 'سلام دنیا. کتاب‌ها را می‌خوانم و کتابخانه رفتم')
 'دنیا':2 'را':4 'رفتم':8 'سلام':1 'می‌خوانم':5 'و':6 'کتابخانه':7 'کتاب‌ها':3
```

Words are kept whole, the half-space included. A search for `کتاب` did not match `کتاب‌ها`. I tried `arabic` too: it cut `دنیا` to `دنی` and `کتابخانه` to `کتابخ`. I did not test other options (custom dictionaries, an external normalizer).

## Fuzzy matching with pg_trgm

`CREATE EXTENSION pg_trgm` worked here. `similarity('hiking','hikng')` is 0.44444445, and `'kettls' <% body` found the "kettles" rows (10000). A {{< term "trigram" "trigram" >}} GIN index on the text took 11 MB.

## A few things to watch

- Index the exact operators you query with; `@>` and `?` need different operator classes.
- JSONB has no schema. Add `CHECK` constraints for keys you rely on.
- Updating a small key rewrites the whole document.
- Search needs the right language configuration; test your language, do not assume.
- A GIN index costs disk and write time. I did not measure the write cost.

## Exercise

Add a `tags` JSONB array to `products`, find rows containing two tags with `@>`, compare plans with and without a GIN index, then build a `tsvector` over `name` and `category`.

## What's next

Next in the series: Zero-downtime migrations.
