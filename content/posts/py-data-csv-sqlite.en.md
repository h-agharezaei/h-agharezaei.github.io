+++
date = '2027-05-19T10:00:00+03:30'
draft = false
title = 'Small data processing with csv and sqlite3'
description = 'Python csv and sqlite3 from the standard library: quoting, BOM, streaming memory, bulk inserts, parameter binding, indexes, EXPLAIN and WAL.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "csv", "sqlite", "sqlite3", "data"]
cover = { image = "/images/covers/py-data-csv-sqlite.png", alt = "Small data processing with csv and sqlite3", hiddenInSingle = true }
+++

Someone sends you `orders.csv` and asks, "which product made the most money?" You open it, see commas between values, and think: `line.split(",")`, ten minutes of work. Then you hit a customer called `Smith, John`.

My test file has 225,006 physical lines but only 200,000 rows, because some customer names contain a comma, a quote, or even a line break. A lot of real scripts, like the command-line tools from [the previous post](/posts/py-cli-scripts/), end up reading a CSV that someone else produced and answering a question about it. You do not need a heavy framework for that. The standard library has `csv` for reading and writing the format correctly and `sqlite3`, a complete SQL database in one file, for asking questions. This post uses both on that file, with [generators](/posts/py-functions-generators/) for streaming. If you want to compare with another language, see [Files and JSON in Go](/posts/go-file-io-json/).

> I re-ran the demo with Python 3.14.0 and SQLite 3.54.0 (`sqlite3.sqlite_version`), standard library only, in a scratch directory. The orders are invented (seeded random numbers). The machine was busy, so I publish counts and bytes, **not timings**. pandas is not installed here and I did not run it. The demo is a local example.

## Reading CSV correctly

First I generated `orders.csv` with `csv.writer`: columns `id, customer, sku, qty, price, ts`, 200,000 rows, 10,673,000 bytes. The customer names include `Smith, John`, `Anne "Ace" Lee`, a Persian name and one name with a newline inside it. Here is the same row read two ways, with plain `split` and with the `csv` module:

```text
split: 7 ['7', '"Smith', ' John"', 'SKU-001', '2', '19.99', '2027-01-01T10:00:00']
csv:   ['7', 'Smith, John', 'SKU-001', '2', '19.99', '2027-01-01T10:00:00']
```

`split` found 7 pieces where there are 6 columns, because the comma inside the quotes counted as a separator. The `csv` module knows the rules: a field in quotes may contain commas, quotes (written twice, `""`) and line breaks. That is also why the file has 225,006 lines but 200,000 rows: counting lines gives the wrong answer, and counting `csv.reader` rows gives the right one.

Two habits when opening a CSV: pass `newline=""`, so that the csv module sees the original line endings and can handle line breaks inside quoted fields itself, and pass an explicit `encoding`. Then there are two readers:

- `csv.reader` gives each row as a list.
- `csv.DictReader` gives each row as a dict keyed by the header line, so you write `row["qty"]` instead of remembering that qty is column 3.

Every value comes out as a **string**. The first data row looked like this as a dict:

```text
{'id': '1', 'customer': 'Sara', 'sku': 'SKU-001', 'qty': '3', 'price': '41.12', 'ts': '2027-01-08T10:00:00'} dict
```

Note `'3'`, not `3`: convert with `int()` or `float()` yourself. For writing, `csv.DictWriter` adds quotes only where needed. Writing `Anne "Ace" Lee` and `Line` + newline + `Break` produced:

```text
'id,customer\r\n1,"Anne ""Ace"" Lee"\r\n2,"Line\nBreak"\r\n'
```

That is `repr` of the text, so `\r\n` are the line endings (the csv default) and the `\n` inside quotes is the newline that belongs to the name.

## Encodings and the Excel BOM

Persian text round-trips fine as UTF-8. The classic problem comes from files saved by Excel: they often start with a {{< term "byte-order-mark" "byte order mark" >}}, three invisible bytes at the very beginning. If you read such a file as plain `utf-8`, those bytes become part of the first column name. I wrote a small file with `utf-8-sig` to imitate it:

```text
raw bytes start: b'\xef\xbb\xbfid'
utf-8 read keys: ['﻿id', 'name']
utf-8-sig: {'id': '1', 'name': 'نیلوفر'}
```

The first line shows the three bytes `\xef\xbb\xbf` in front of `id`. The second shows the damage: the key is `'﻿id'`, an invisible character plus `id`, so `row["id"]` raises `KeyError` and you stare at a key that looks identical. The third shows the fix, reading with `utf-8-sig`, which removes the mark. To send a file that Excel will show correctly, write with `utf-8-sig` as well.

## Streaming with generators

The 10 MB file is small, but how you read it still matters. I measured peak memory with `tracemalloc`, once loading all rows into a list and once looping over the reader and summing one column:

```text
list rows 200000 peak MB 106
stream qty sum 599692 peak MB 0.19
```

`list(csv.DictReader(f))` held everything: about 106 MB for a 10 MB file, because every row is a dict of strings, and Python objects have overhead. Looping over the reader and keeping only a running total needed 0.19 MB. The reader produces one row at a time, so memory stays flat however large the file is. These numbers are peaks of memory, not timings, so they hold up on a busy machine.

You can wrap the reader in a {{< term "generator" "generator" >}} (a function with `yield from`), and then `itertools.islice(rows(), 3)` peeks at the first three rows (the demo printed ids `1`, `2`, `3`) without reading the rest. It is the same idea as [Streams in Node.js](/posts/node-streams-backpressure/): process data as it flows instead of holding it all.

## SQLite: load it in one transaction

Summing one column while streaming is easy. A question like "revenue per product" is easier in SQL. `sqlite3` is in the standard library and needs no server: the database is one file. I created a table and loaded the CSV with `executemany`, feeding it from a generator, inside a single {{< term "transaction" "transaction" >}} (`with db:` commits when the block ends):

```python
with db:
    db.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", gen())
```

The demo printed `rows 200000 journal_mode delete`: 200,000 rows loaded in one commit, with the default journal mode `delete`. The slow way is to commit after every row. A commit forces the database to make the data durable on disk, which is the expensive step, so 200,000 commits would mean 200,000 durable writes. I counted rather than timed: with 2,000 rows the loop made 2,000 commits against 1 for the bulk load (`per-row commits: 2000 vs bulk commits: 1`). The time difference is large, but I am not quoting a number.

## Binding parameters

The `?` in the `INSERT` are placeholders, filled in separately from the SQL ({{< term "parameterized-query" "parameter binding" >}}). It matters because of what happens when you build the SQL text from input yourself. A harmless demo on a `users` table, with the input `x' OR '1'='1`:

```text
formatted: [('ali',), ('sara',)] bound: []
```

With an f-string, the quote in the input closed the string and `OR '1'='1'` made the condition always true: both users came back. With a bound parameter the whole text is just a value, nobody has that name, and the result is empty. This is {{< term "sql-injection" "SQL injection" >}}; see [Injection and XSS](/posts/sec-injection-xss/). Never build SQL with string formatting.

One convenience: `db.row_factory = sqlite3.Row` lets you read columns by name. The demo's `row["sku"]` gave `SKU-001` and `row.keys()` gave `['id', 'sku', 'qty']`.

## Indexes and EXPLAIN QUERY PLAN

Now a question: how much was sold for one product? `SELECT count(*), sum(qty*price) FROM orders WHERE sku = 'SKU-007'`. To see how SQLite answers it, put `EXPLAIN QUERY PLAN` in front. I ran it before and after creating an index on `sku`:

```text
before: SCAN orders
after:  SEARCH orders USING INDEX idx_orders_sku (sku=?)
```

`SCAN` means SQLite reads the whole table, row by row. After `CREATE INDEX`, the {{< term "query-plan" "plan" >}} says `SEARCH ... USING INDEX`: it goes straight to the matching rows with a {{< term "database-index" "database index" >}}, like using the index at the back of a book. This is the same idea as in [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/). A report is then just SQL; the three products with the most revenue:

```text
SELECT sku, count(*), round(sum(qty*price),2) ... GROUP BY sku ORDER BY revenue DESC LIMIT 3
('SKU-002', 4135, 636960.12)
('SKU-010', 4081, 630724.13)
('SKU-029', 4027, 628905.06)
```

Each tuple is the product, the number of orders and the revenue. There is the answer to the question at the top: SKU-002.

## Type affinity surprises

SQLite is more relaxed about types than most databases. I created `a(n INTEGER)` and inserted four values: the text `'12'`, the text `'abc'`, `3.0` and `3.5`. Then I asked for each value and its `typeof`:

```text
[(12, 'integer'), ('abc', 'text'), (3, 'integer'), (3.5, 'real')]
```

`'12'` was converted to the integer 12, `3.0` became the integer 3, and `3.5` stayed real. But `'abc'` was accepted as text in an INTEGER column without any complaint. This is {{< term "type-affinity" "type affinity" >}}: the column type is a preference, not a rule. If you want a rule, create the table as `STRICT`; then the same insert fails with `IntegrityError cannot store TEXT value in INTEGER column s.n`.

## WAL, ATTACH and export

In the default journal mode, a writer that is committing blocks readers. The `WAL` (write-ahead log) journal mode lets readers and one writer work at the same time. After `db.commit()`, `PRAGMA journal_mode=WAL` returned `wal`, and the directory then had two extra files next to the database:

```text
['shop.db', 'shop.db-shm', 'shop.db-wal']
```

Commit first. In a scratch test I ran the pragma while a transaction was still open and it returned `delete`, so nothing changed; after the commit it returned `wal`.

`:memory:` gives a throwaway database that lives only in RAM, and `ATTACH` adds a second database to the same connection. To finish, I attached an in-memory one, built a top-3 table of quantities per product in it and wrote it back out with `csv.writer`:

```text
sku,q
SKU-002,12469
SKU-044,12308
SKU-018,12299
```

So the whole path is: read a CSV, load it into SQLite, ask a question in SQL, write a CSV back. A single SQLite file is also a common application file format. When you need many writers at once, a network, or roles and permissions, move to Postgres ([SQLAlchemy and Postgres](/posts/py-sqlalchemy-postgres/)).

## Common CSV and SQLite mistakes

- Open every CSV with `newline=""` and an explicit encoding; otherwise line breaks inside fields and the BOM will bite you.
- All CSV values are strings. Convert them before comparing or summing, or `'10' < '9'` will surprise you.
- Use one transaction for a bulk load, not one commit per row.
- Bind parameters; never format SQL from input.
- Commit before changing the journal mode.

## Exercise

Add a `--stats` flag that streams a CSV into an in-memory SQLite database and prints revenue per customer. Check the peak memory with `tracemalloc`.

## What's next

Next is "Calling Rust from Python with ctypes and PyO3", for the hot loops that are too slow in Python.
