+++
date = '2027-05-19T10:00:00+03:30'
draft = false
title = 'Small data processing with csv and sqlite3'
description = 'Python csv and sqlite3 from the standard library: quoting, BOM, streaming memory, bulk inserts, parameter binding, indexes, EXPLAIN and WAL.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "csv", "sqlite", "sqlite3", "data"]
cover = { image = "/images/covers/py-data-csv-sqlite.png", alt = "Small data processing with csv and sqlite3", hiddenInSingle = true }
+++

In the [previous post](/posts/py-cli-scripts/) we wrote command-line tools. A lot of real scripts then do one more thing: read a CSV someone sent, and answer a question about it. The standard library is enough for that. This post uses `csv` and `sqlite3` on a 200,000-row file, with [generators](/posts/py-functions-generators/) for streaming. Compare with [files and JSON in Go](/posts/go-file-io-json/).

> Python 3.14.0, SQLite 3.54.0 (`sqlite3.sqlite_version`), stdlib only, in a throwaway directory. The orders are invented (seeded random). The machine was busy (load around 3), so I publish counts and bytes, **not timings**. pandas is not installed here and I did not run it. The demo is a local example.

## Reading CSV correctly

I generated `orders.csv` with `csv.writer`: columns `id, customer, sku, qty, price, ts`, 10,673,000 bytes. Some customers are `Smith, John`, `Anne "Ace" Lee` and a name with a newline. The file has 225,006 physical lines but 200,000 rows. Naive splitting breaks:

```text
split: 7 ['7', '"Smith', ' John"', 'SKU-001', '2', '19.99', '2027-01-01T10:00:00']
csv:   ['7', 'Smith, John', 'SKU-001', '2', '19.99', '2027-01-01T10:00:00']
```

Always open with `newline=""` and an explicit `encoding`. `csv.reader` gives lists; `csv.DictReader` gives dicts keyed by the header. Every value is a **string**, so `'3'` needs `int()`. `csv.DictWriter` quotes only when needed:

```text
'id,customer\r\n1,"Anne ""Ace"" Lee"\r\n2,"Line\nBreak"\r\n'
```

## Encodings and the Excel BOM

Persian text round-trips fine as UTF-8. The classic problem is a file saved by Excel: it starts with a {{< term "byte-order-mark" "byte order mark" >}}. Reading it as plain `utf-8` pollutes the first column name:

```text
raw bytes start: b'\xef\xbb\xbfid'
utf-8 read keys: ['﻿id', 'name']
utf-8-sig: {'id': '1', 'name': 'نیلوفر'}
```

Read with `utf-8-sig`. To send a file that Excel shows correctly, write with `utf-8-sig` too.

## Streaming with generators

Memory measured with `tracemalloc` (peak, deterministic enough to round):

```text
list rows 200000 peak MB 106
stream qty sum 599692 peak MB 0.19
```

`list(csv.DictReader(f))` held everything, about 106 MB for a 10 MB file, because each row is a dict of strings. Looping over the reader needs 0.19 MB. Wrap the reader in a {{< term "generator" "generator" >}} and `itertools.islice(rows(), 3)` peeks at the first rows without reading the rest. Streaming is the same idea as in [streams in Node.js](/posts/node-streams-backpressure/).

## SQLite: load it in one transaction

`sqlite3` needs no server. I created a table and bulk-loaded with `executemany` and a generator, inside one {{< term "transaction" "transaction" >}} (`with db:`):

```python
with db:
    db.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", gen())
```

That is 200,000 rows and one commit; `PRAGMA journal_mode` said `delete`, the default. The slow way commits per row: with 2,000 rows that is 2,000 commits, each forcing a durable write. I counted commits and did not time them, because of the load. Each commit is a disk sync, so the difference is large, but I am not quoting a number.

## Binding parameters

The `?` placeholders are {{< term "parameterized-query" "parameter binding" >}}. A harmless demo on a `users` table with the input `x' OR '1'='1`:

```text
formatted: [('ali',), ('sara',)] bound: []
```

The f-string version returned every user, the bound one returned none. This is {{< term "sql-injection" "SQL injection" >}}; see [injection and XSS](/posts/sec-injection-xss/). Never build SQL with formatting.

`db.row_factory = sqlite3.Row` lets you use `row["sku"]` and `row.keys()`.

## Indexes and EXPLAIN QUERY PLAN

For `SELECT count(*), sum(qty*price) FROM orders WHERE sku = 'SKU-007'`:

```text
before: SCAN orders
after:  SEARCH orders USING INDEX idx_orders_sku (sku=?)
```

The first reads the whole table; after `CREATE INDEX` the {{< term "query-plan" "plan" >}} uses a {{< term "database-index" "database index" >}}. This is the same idea as [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/). A report is plain SQL:

```text
SELECT sku, count(*), round(sum(qty*price),2) ... GROUP BY sku ORDER BY revenue DESC LIMIT 3
('SKU-002', 4135, 636960.12)
('SKU-010', 4081, 630724.13)
('SKU-029', 4027, 628905.06)
```

## Type affinity surprises

I made `a(n INTEGER)` and inserted `'12'`, `'abc'`, `3.0`, `3.5`. `typeof(n)` returned:

```text
[(12, 'integer'), ('abc', 'text'), (3, 'integer'), (3.5, 'real')]
```

`'12'` was converted, `'abc'` was accepted. That is {{< term "type-affinity" "type affinity" >}}. A `STRICT` table refuses: `IntegrityError cannot store TEXT value in INTEGER column s.n`.

## WAL, ATTACH, export

After `db.commit()`, `PRAGMA journal_mode=WAL` returned `wal`, and `ls` showed:

```text
['shop.db', 'shop.db-shm', 'shop.db-wal']
```

WAL lets readers and a writer work at the same time. The pragma did nothing while a transaction was open in my first run, so commit first. `:memory:` gives a throwaway database; `ATTACH` adds a second one to the same connection. I attached an in-memory one, built a top-3 table and wrote it back with `csv.writer`:

```text
sku,q
SKU-002,12469
SKU-044,12308
SKU-018,12299
```

A single SQLite file is also a common application file format. When you need many writers, a network, or roles, move to Postgres ([SQLAlchemy and Postgres](/posts/py-sqlalchemy-postgres/)).

## A few things to watch

- `newline=""` and an explicit encoding on every CSV file.
- All CSV values are strings; convert them.
- One transaction for bulk loads.
- Bind parameters; never format SQL.
- Commit before changing journal mode.

## Exercise

Add a `--stats` flag that streams a CSV into an in-memory SQLite database and prints revenue per customer. Check the peak memory with `tracemalloc`.

## What's next

The next post is "Calling Rust from Python with ctypes and PyO3".
