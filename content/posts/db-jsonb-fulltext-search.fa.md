+++
date = '2027-01-14T10:00:00+03:30'
draft = false
title = 'JSONB و جست‌وجوی متنی'
description = 'JSONB و جست‌وجوی متنی در PostgreSQL با اجرای واقعی: عملگرهای @> و ?، اندازه و buffer ایندکس GIN، tsvector، stemming، متن فارسی و pg_trgm.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "jsonb", "full-text-search", "gin"]
cover = { image = "/images/covers/db-jsonb-fulltext-search.fa.png", alt = "JSONB و جست‌وجوی متنی", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-locks-deadlocks/) سراغ قفل‌ها رفتیم. این بار سؤال دیگری داریم: با داده‌ای که در ستون‌های مرتب جا نمی‌شود (ویژگی‌های محصول، تنظیمات) چه کنیم، و چطور متن را بدون `LIKE '%...%'` که کل جدول را می‌خواند جست‌وجو کنیم؟ PostgreSQL به هر دو با {{< term "gin-index" "ایندکس GIN" >}} جواب می‌دهد؛ هم‌خانواده‌ی [B-tree](/fa/posts/db-indexes-btree-explain/) که می‌شناسید. خواندن planها مثل [پست planner](/fa/posts/db-planner-statistics/) است.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی اجرا شد. داده قطعی است (`i % n`، بدون random). ماشین مشغول بود، پس زمان‌سنجی نیست و فقط تعداد buffer آمده. به جدول ۱۰۰۰ ردیفی `products` از schema مشترک `shop` ستون `attrs` اضافه کردم؛ برای تست ایندکس جدول ۲۰۰ هزار ردیفی ساختم، چون ایندکس روی ۱۰۰۰ ردیف چیزی را ثابت نمی‌کند.

## عملگرهای JSONB

{{< term "jsonb" "JSONB" >}} همان JSON پارس‌شده را نگه می‌دارد. `products.attrs` را با `jsonb_build_object('color', ..., 'size', ..., 'weight_g', ..., 'tags', ...)` پر کردم:

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

`->` مقدار JSONB برمی‌گرداند، `->>` متن، `@>` یعنی «شامل است»، `?` یعنی «کلید یا عنصر رشته‌ای وجود دارد» و `?|` یعنی یکی از آن‌ها. `jsonb_path_*` یک عبارت SQL/JSON path اجرا می‌کند.

## GIN: قبل و بعد

روی ۲۰۰ هزار ردیف، کوئری `attrs @> '{"color":"white","size":"L","batch":1234}'` صد ردیف برمی‌گرداند:

| ایندکس | buffer (ایندکس + heap) | اندازه‌ی ایندکس |
|---|---|---|
| بدون ایندکس (Seq Scan) | ۳۶۴۸ | - |
| `gin (attrs)` (`jsonb_ops`) | ۲۰۱ + ۱۰۰ = ۳۰۱ | 3576 kB |
| `gin (attrs jsonb_path_ops)` | ۳۳ + ۱۰۰ = ۱۳۳ | 2464 kB |

heap برابر ۲۹ مگابایت است. `jsonb_path_ops` کوچک‌تر و برای `@>` سریع‌تر است، ولی طبق مستندات از `?` پشتیبانی نمی‌کند. امتحان کردم: فقط با همین ایندکس، `attrs ? 'gift'` (۴۰ ردیف) به Seq Scan با ۳۶۴۸ buffer برگشت؛ با `jsonb_ops` از ایندکس استفاده کرد و ۵ buffer خواند. بر اساس عملگرهایی که واقعاً می‌زنید انتخاب کنید.

## JSONB یا ستون واقعی؟ (نظر خودم)

JSONB برای ویژگی‌هایی خوب است که از ردیفی به ردیف دیگر فرق می‌کنند یا فقط گاهی رویشان فیلتر می‌کنید. برای هر چیز محوری (join، یکتایی، foreign key) ستون واقعی بگذارید. دو هزینه را توانستم نشان بدهم:

```text
UPDATE products SET attrs = '{"colour":"red","weight_g":"heavy"}' WHERE id = 1;   -- UPDATE 1
```

اگر `CHECK` نگذارید، هیچ‌چیز جلوی غلط املایی در کلید یا رشته‌ای به جای عدد را نمی‌گیرد. و update کل مقدار را دوباره می‌نویسد: ردیفی با سند ۹۶ کیلوبایتی، اندازه‌ی جدول 152 kB. بعد از ۱۰ بار تغییر یک کلید کوچک داخلش با `jsonb_set`، `pg_table_size` شد 1128 kB؛ ۱۰ بار update یک ستون `int` جدا رشد نداد (همان 1128 kB). این همان هزینه‌ی {{< term "mvcc" "MVCC" >}} در [پست VACUUM](/fa/posts/db-mvcc-vacuum/) است، ضرب‌در اندازه‌ی سند.

## جست‌وجوی متنی

{{< term "tsvector" "tsvector" >}} سندی است که به کلمه‌های نرمال‌شده تبدیل شده. {{< term "stemming" "Stemming" >}} از configuration می‌آید:

```text
to_tsvector('english', 'The runners were running; she runs and ran daily')
 'daili':9 'ran':8 'run':4,6 'runner':2
to_tsvector('english','running') @@ to_tsquery('english','run')  -> t
to_tsvector('simple','running')  @@ to_tsquery('simple','run')   -> f
websearch_to_tsquery('english','"red shoes" -boots or sandals')
 'red' <-> 'shoe' & !'boot' | 'sandal'
```

stop wordها حذف می‌شوند و `ran` به `run` تبدیل نمی‌شود. روی ۱۰۰ هزار متن محصول تولیدشده: `ILIKE '%run%'` تعداد ۴۲۸۵۷ ردیف پیدا کرد (`runners` را هم می‌گیرد)، جست‌وجوی `english` برای `run` تعداد ۲۸۵۷۱ و جست‌وجوی `simple` برای `running` تعداد ۱۴۲۸۵. `ts_rank` نتیجه‌ها را مرتب می‌کند: متنی با سه بار «shoes» امتیاز 0.0827 گرفت و با یک بار 0.0608.

برای سرعت، vector را در یک {{< term "generated-column" "ستون generated" >}} ذخیره کردم (`tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED`) و رویش GIN ساختم (7032 kB). کوئری `tents & hiking` (۱۴۲۸ ردیف، ۱.۴٪) وقتی vector لحظه‌ای ساخته می‌شد ۲۸۲۰ buffer خواند، با ستون به‌تنهایی ۲۸۱۶ و با ایندکس ۱۴۴۴؛ بهبود متوسط، چون ردیف‌ها در همه‌ی pageها پخش‌اند. کوئری کمیاب (`tents & hiking & 57`، یک ردیف): قبلاً ۲۸۱۶ buffer، بعد از ایندکس ۱۵.

## متن فارسی

`\dF` سی configuration نشان داد: `arabic` و `hindi` هست، ولی **configuration فارسی نیست**. با `simple`:

```text
to_tsvector('simple', 'سلام دنیا. کتاب‌ها را می‌خوانم و کتابخانه رفتم')
 'دنیا':2 'را':4 'رفتم':8 'سلام':1 'می‌خوانم':5 'و':6 'کتابخانه':7 'کتاب‌ها':3
```

کلمه‌ها کامل می‌مانند، با نیم‌فاصله. جست‌وجوی `کتاب` با `کتاب‌ها` تطبیق نشد. `arabic` را هم امتحان کردم: `دنیا` را به `دنی` و `کتابخانه` را به `کتابخ` بُرید. گزینه‌های دیگر (dictionary سفارشی، نرمال‌ساز بیرونی) را تست نکردم.

## تطبیق تقریبی با pg_trgm

`CREATE EXTENSION pg_trgm` اینجا کار کرد. `similarity('hiking','hikng')` برابر 0.44444445 شد و `'kettls' <% body` ردیف‌های «kettles» را پیدا کرد (۱۰۰۰۰ ردیف). ایندکس GIN از نوع {{< term "trigram" "trigram" >}} روی متن 11 MB شد.

## چند نکته‌ی مهم

- ایندکس را برای عملگرهایی بسازید که واقعاً می‌زنید؛ `@>` و `?` operator class متفاوت می‌خواهند.
- JSONB schema ندارد. برای کلیدهایی که به آن‌ها تکیه می‌کنید `CHECK` بگذارید.
- تغییر یک کلید کوچک، کل سند را دوباره می‌نویسد.
- جست‌وجو configuration درست زبان می‌خواهد؛ زبان خودتان را تست کنید، فرض نکنید.
- ایندکس GIN دیسک و زمان نوشتن می‌خورد. هزینه‌ی نوشتن را اندازه نگرفتم.

## تمرین

به `products` یک آرایه‌ی JSONB به نام `tags` اضافه کنید، ردیف‌های دارای دو tag را با `@>` پیدا کنید، plan را با GIN و بدون آن مقایسه کنید، و بعد روی `name` و `category` یک `tsvector` بسازید.

## قدم بعدی

در پست بعدی این سری: «migration بدون downtime».
