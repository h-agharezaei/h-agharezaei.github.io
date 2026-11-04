+++
date = '2027-01-14T10:00:00+03:30'
draft = false
title = 'JSONB and full-text search'
description = 'PostgreSQL JSONB and full-text search with real runs: @> and ? operators, GIN index sizes and buffers, tsvector, stemming, Persian text and pg_trgm.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "jsonb", "full-text-search", "gin"]
cover = { image = "/images/covers/db-jsonb-fulltext-search.png", alt = "JSONB and full-text search", hiddenInSingle = true }
+++

Suppose you run a shop and want every product whose description contains the word "run". The first thing that comes to mind is `ILIKE '%run%'`. It works, but it has two problems: it reads the whole table for every search, and it matches letters, not words: wherever those three letters appear, even in the middle of another word, it finds them (for example it also catches "runners"), and it does not understand what a word means. There is a second problem too: information such as colour, size and tags of each product does not fit into neat table columns, because it differs from product to product. We usually keep it as JSON, and then we have to search inside it.

PostgreSQL has an answer to both problems, and both times the answer is one kind of index: the {{< term "gin-index" "GIN index" >}}. If you have seen the [B-tree](/posts/db-indexes-btree-explain/) index, GIN is a relative of it, but built for values made of many parts: a JSON document, an array, or text made of words. In this post we start with JSON, then move to full-text search, then Persian text and spelling mistakes. We read plans the way we did in [The planner and statistics: why an index is not used](/posts/db-planner-statistics/). After [Locks and deadlocks in the database](/posts/db-locks-deadlocks/), which was about concurrency, this post is about the shape of the data.

> Everything below was re-run on a real PostgreSQL 18.3. The data is deterministic (built with `i % n`, no random). The machine was busy, so there is no timing and I report only buffer counts: each buffer is one 8 KB page the query read, and fewer means the query did less work. I added an `attrs` column to the 1000-row `products` table of the sample `shop` data. To test indexes I built a 200 thousand-row table, because an index on 1000 rows proves nothing. For full-text search I also built a table of 100 thousand product texts.

## JSONB operators

{{< term "jsonb" "JSONB" >}} is JSON that PostgreSQL parses and stores in a binary form. I filled the column `products.attrs` with `jsonb_build_object('color', ..., 'size', ..., 'weight_g', ..., 'tags', ...)`. Two sample rows:

```text
 1 | {"size": "M", "tags": ["eco"], "color": "green", "weight_g": 110}
21 | {"size": "M", "tags": ["sale", "new"], "color": "green", "weight_g": 310}
```

(The key order is not the order I wrote; JSONB does not preserve key order.) Now the operators. Each line is a question, and the last number is the answer:

```text
attrs -> 'color'  = "green" (jsonb)     attrs ->> 'color' = green (text)
attrs -> 'tags' -> 0 = "sale"
attrs @> '{"color":"blue","size":"XL"}'      -> 50 rows
attrs -> 'tags' ? 'sale'                     -> 428
attrs -> 'tags' ?| array['new','nothing']    -> 142
attrs @> '{"tags":["sale","new"]}'           -> 142

SELECT jsonb_path_query(attrs, '$.tags[*]') ... WHERE id = 21;   "sale", "new"
jsonb_path_exists(attrs, '$ ? (@.weight_g > 580 && @.color == "white")')  -> ids 49, 99, 149
```

- `->` takes one key and returns **JSONB** (`"green"` with quotes), while `->>` converts it to **text** (`green`). When you want to compare with a string in `WHERE`, you want `->>`.
- `->` can be chained: `attrs -> 'tags' -> 0` is the first element of the `tags` array (`"sale"`).
- `@>` means "contains". `attrs @> '{"color":"blue","size":"XL"}'` picks every product that is both blue and XL: 50 rows out of 1000.
- `?` means "this key or string element exists". `attrs -> 'tags' ? 'sale'` finds products with the tag `sale`: 428 of them. `?|` means "any of these exists"; 142 products have the tag `new` or `nothing`, and all of them have `new`. The same 142 are what `@> '{"tags":["sale","new"]}'` (both tags) returns too, because in our data every product that has `new` also has `sale`.
- `jsonb_path_*` runs an SQL/JSON path expression, a small query language inside JSON. `$.tags[*]` returns all elements of `tags` for product 21 (`"sale"` and `"new"`). The expression `$ ? (@.weight_g > 580 && @.color == "white")` means "a document whose weight is over 580 and whose colour is white"; with `LIMIT 3` the first ones were products 49, 99 and 149.

## GIN: before and after

On 1000 rows the `@>` operator is a `Seq Scan` as expected (28 buffers). To see the real effect of an index, I tried the query `attrs @> '{"color":"white","size":"L","batch":1234}'` on 200 thousand rows, which returns 100 rows. (This table also has a `batch` key.) I built two kinds of GIN index and compared the buffer counts:

| Index | buffers (index + heap) | index size |
|---|---|---|
| none (Seq Scan) | 3648 | - |
| `gin (attrs)` (`jsonb_ops`) | 201 + 100 = 301 | 3576 kB |
| `gin (attrs jsonb_path_ops)` | 33 + 100 = 133 | 2464 kB |

Without an index, Postgres reads all 3648 pages of the table to find 100 rows. With an index, it first reads the index (201 or 33 buffers) and then only the 100 heap pages where the rows are. The heap itself is 29 MB.

What is the difference between the two kinds of index? `jsonb_ops` (the default) indexes all keys and values separately, so it supports more operators. `jsonb_path_ops` indexes paths, is smaller and faster for `@>`, but according to the documentation it does not support `?`. I tried that too: when only the `jsonb_path_ops` index existed, `attrs ? 'gift'` (40 rows) fell back to a Seq Scan with 3648 buffers; with `jsonb_ops` it used the index and read only 5 buffers. So choose the index by the operators you actually use in your queries.

## JSONB or a real column? (my opinion)

JSONB is good for attributes that differ from row to row, or that you only filter on occasionally. For anything central, such as joins, uniqueness and foreign keys, use a real column. I could show two costs. First, JSONB has no rules of its own:

```text
UPDATE products SET attrs = '{"colour":"red","weight_g":"heavy"}' WHERE id = 1;   -- UPDATE 1
```

That `UPDATE` succeeded. The key `color` was misspelled as `colour` and `weight_g` became the string "heavy" instead of a number. Without a `CHECK`, nothing stops a misspelled key or a string where a number belongs. (I restored the row afterwards.)

Second, every update rewrites the whole JSONB value. I made a row with a 96034-byte document (about 96 kilobytes) and a separate `int` column called `views`. The table size (`pg_table_size`) was 152 kB. Then I changed one small key inside the document 10 times with `jsonb_set`; the size became 1128 kB, about 98 kilobytes per update, close to the size of the whole document. But 10 updates of the separate `int` column did not grow it (still 1128 kB). Why? The document is too big to fit inside the row itself and PostgreSQL stores it separately (with `has_toast = 1` I saw that the table has a separate area for large values). `jsonb_set` builds and writes a complete new document, while updating the `int` column leaves the old document alone. This is the {{< term "mvcc" "MVCC" >}} cost from [MVCC and VACUUM](/posts/db-mvcc-vacuum/), multiplied by the size of the document.

## Full-text search

Back to the first problem: finding "run". PostgreSQL full-text search first breaks the text into normalized words. A {{< term "tsvector" "tsvector" >}} is a document in that form, and normalization includes {{< term "stemming" "stemming" >}}: reducing each word to its root, for example `running` and `runs` both become `run`. Which root is produced depends on the language configuration. Real output:

```text
to_tsvector('english', 'The runners were running; she runs and ran daily')
 'daili':9 'ran':8 'run':4,6 'runner':2
to_tsvector('english','running') @@ to_tsquery('english','run')  -> t
to_tsvector('simple','running')  @@ to_tsquery('simple','run')   -> f
websearch_to_tsquery('english','"red shoes" -boots or sandals')
 'red' <-> 'shoe' & !'boot' | 'sandal'
```

First line: unimportant words (stop words) such as `the`, `were`, `she` and `and` were dropped, `running` and `runs` both became `run` (at positions 4 and 6), but `ran` stayed `ran` and `runners` became `runner`; the English stemmer does not turn `ran` into `run`. The numbers are word positions in the text. The second and third lines show the difference between configurations: with `english`, the word `running` matches the query `run` (`t`), but with `simple`, which only lowercases, it does not (`f`). The last line: `websearch_to_tsquery` understands the syntax people type into a search engine: a quoted phrase becomes `<->` (next to each other), `-boots` becomes `!'boot'` and `or` becomes `|`.

Now the experiment on 100 thousand generated product texts. The number of results:

- `ILIKE '%run%'`: 42857 rows. This search takes anything that contains those three letters, including `runners` and `Runs`.
- `english` search for `run`: 28571 rows. Only words whose root is exactly `run` (`running` and `runs`); `runners` has the root `runner` and did not match.
- `simple` search for `running`: 14285 rows. Only the word `running` itself.

Three different answers to one question, and none of them is wrong; each method means something different by "the same". You have to know which one you want. `ts_rank` also orders results by relevance: a text with "shoes" three times scored 0.0827 and a text with it once scored 0.0608.

For speed, two steps are needed. First, instead of building the vector at query time, I stored it in a {{< term "generated-column" "generated column" >}} (`tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED`). Second, I built a GIN index on it (7032 kB). With this, the query `tents & hiking`, which returns 1428 rows (1.4% of the table), read:

- when the vector was built on the fly: 2820 buffers.
- with the stored column but no index: 2816 buffers.
- with the GIN index: 1444 buffers.

The improvement is only moderate, because the 1428 result rows are spread over about 1428 different pages and we have to read almost all of them. When the result is small, the index really shines: the query `tents & hiking & 57` returns just one row. It used to read 2816 buffers; after the index it read 15.

## Persian text

Now the problem that matters to us: Persian. `\dF` showed thirty configurations. `arabic` and `hindi` exist, but **there is no Persian configuration**. So I started with `simple`:

```text
to_tsvector('simple', 'سلام دنیا. کتاب‌ها را می‌خوانم و کتابخانه رفتم')
 'دنیا':2 'را':4 'رفتم':8 'سلام':1 'می‌خوانم':5 'و':6 'کتابخانه':7 'کتاب‌ها':3
```

The words stay whole, with their half-spaces (ZWNJ), and no stemming happens. As a result, searching for `کتاب` does not match `کتاب‌ها` (`exact = t` but `plural = f`). It does not match the spelling without the half-space (`کتابها`) either. I also tried `arabic`, hoping its stemming would help, but it cut `دنیا` to `دنی` and `کتابخانه` to `کتابخ`, which is not good for Persian. I did not test other options, such as a custom dictionary or an external normalizer.

## Approximate matching with pg_trgm

There is one more thing: spelling mistakes. The `pg_trgm` extension breaks text into three-letter pieces ({{< term "trigram" "trigrams" >}}) and computes the similarity of two strings from the pieces they share. `CREATE EXTENSION pg_trgm` worked without trouble on this instance. `similarity('hiking','hikng')` was 0.44444445 (so `'hikng' % 'hiking'` is true), and `'kettls' <% body` found the "kettles" rows (10000 rows). A trigram GIN index on the text was 11 MB, larger than the `tsvector` index.

## GIN and JSONB surprises

- **Build the index for the operators you actually use.** `@>` and `?` may need different operator classes, as we saw.
- **JSONB has no schema.** Add a `CHECK` for keys you rely on.
- **Changing one small key rewrites the whole document.** Do not keep large, frequently updated documents in JSONB.
- **Full-text search needs the right language configuration.** Test your own language instead of assuming it works; for Persian there is nothing ready-made.
- **A GIN index costs disk and write time.** I did not measure the write cost; I only saw index sizes and the number of buffers read.

## Exercise

Add a JSONB array called `tags` to `products`, find the rows that have two tags with `@>`, and compare the plan with and without GIN. Then build a `tsvector` on `name` and `category` and search for a word that should match its other forms because of stemming.

## What's next

[Zero-downtime migrations](/posts/db-zero-downtime-migrations/): the same indexes we built here also have to be built on a live table, and building an index on a live table can freeze the application.
