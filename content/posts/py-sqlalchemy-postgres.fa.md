+++
date = '2027-05-01T10:00:00+03:30'
draft = false
title = 'SQLAlchemy و Postgres'
description = 'SQLAlchemy 2.1 با Postgres: text() در Core، Session در ORM، شمارش واقعی N+1، محدودیت pool، IntegrityError، isolation، Alembic و async، همه اجرا شده.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "sqlalchemy", "postgres", "alembic", "orm"]
cover = { image = "/images/covers/py-sqlalchemy-postgres.fa.png", alt = "SQLAlchemy و Postgres", hiddenInSingle = true }
+++

این حلقه کاملاً بی‌گناه به نظر می‌رسد:

```python
for customer in session.scalars(select(Customer)):
    print(len(customer.orders))
```

با ۴ مشتری در پایگاه داده، این کد ۵ query به Postgres می‌فرستد: یکی برای بارگذاری مشتری‌ها و بعد یکی دیگر برای هر مشتری، تا سفارش‌هایش را بیاورد. هیچ‌جای کد Python این را نمی‌گوید. `customer.orders` شبیه یک attribute لیستی ساده است، ولی دست زدن به آن بی‌صدا سراغ پایگاه داده می‌رود. با ۴ مشتری بی‌ضرر است. با ۱۰ هزار مشتری یک بعدازظهر بد است.

دلیل اصلی که باید SQLAlchemy را پیش از استفاده بشناسیم همین است. API [پست قبل](/fa/posts/py-fastapi-pydantic/) هنوز پایگاه داده ندارد و پیش از اضافه کردنش می‌خواهم ببینم این کتابخانه زیر کار چه می‌کند. SQLAlchemy دو لایه دارد. **Core** اجازه می‌دهد SQL را به‌شکل Python بنویسید و با پارامترهای bind‌شده بفرستید. **ORM** (نگاشت شیء به جدول، {{< term "orm" "ORM" >}}) روی Core سوار است و جدول‌ها را به کلاس‌های Python نگاشت می‌کند، پس ردیف‌ها به شیء تبدیل می‌شوند. اگر در Node از `pg` ([Postgres از Node.js](/fa/posts/node-postgres-pg/)) یا در Go از pgx ([Postgres با pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/)) استفاده کرده‌اید، Core را مثل driver و ORM را یک افزونه‌ی اختیاری روی آن ببینید.

> دمو را دوباره با Python 3.14.0، SQLAlchemy 2.1.6، psycopg 3.3.6 (نصب `[binary]` با libpq همراه نسخه‌ی 18.0.6)، Alembic 1.20.1 و greenlet 3.5.6 روی یک PostgreSQL 18.3 واقعی در `127.0.0.1` و در یک محیط مجازی موقت اجرا کردم. هر جا port می‌آمد آن را با `<port>` عوض کرده‌ام. تعداد نشان می‌دهم، نه زمان. شناسه‌ی revision در Alembic و زمان `generated in ...s` در SQLAlchemy هر بار فرق می‌کند.

## Core: متن text() و پارامتر bind‌شده

ساده‌ترین راه استفاده از SQLAlchemy این است که SQL را خودتان بنویسید و اتصال را به آن بسپارید:

```python
with engine.begin() as c:
    c.execute(text("INSERT INTO customers (email) VALUES (:e)"), [{"e": "a@example.com"}, ...])
    c.execute(text("SELECT count(*) FROM customers WHERE email = :e"), {"e": "x' OR '1'='1"}).scalar()
```

`:e` یک placeholder نام‌دار است. مقدار هرگز در رشته‌ی SQL چسبانده نمی‌شود. جدا از آن، به‌شکل پارامتر به Postgres می‌رسد ({{< term "parameterized-query" "parameterized query" >}}). برای آزمایش، دستور دوم ایمیلی را جست‌وجو می‌کند که یک رشته‌ی کلاسیک تزریق است. جواب `0` چاپ شد: Postgres دنبال مشتریی گشت که ایمیلش دقیقاً همین متن عجیب باشد، پیدا نکرد، و آن نقل‌قول معنی query را عوض نکرد. این دفاع در برابر {{< term "sql-injection" "SQL injection" >}} است. `engine.begin()` یک {{< term "transaction" "transaction" >}} باز می‌کند و وقتی بلوک `with` تمام شود commit می‌کند (و اگر خطا پرتاب شود rollback).

## ORM: Session به‌عنوان unit of work

ORM اجازه می‌دهد جدول‌ها را به‌شکل کلاس توصیف کنید:

```python
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
```

`Order` طرف دیگر است: یک `ForeignKey("customers.id")` و یک attribute به نام `customer` دارد که برمی‌گردد. `relationship` همان چیزی است که `customer.orders` را ممکن می‌کند، و همان‌طور که می‌بینیم query‌های اضافه را هم پنهان می‌کند.

با پایگاه داده از طریق `Session` حرف می‌زنید. بهترین تصویر برای آن یک سبد خرید است، که اسم رسمی‌اش {{< term "unit-of-work" "unit of work" >}} است. شیء اضافه می‌کنید و تغییر می‌دهید، session همه را به یاد می‌سپارد و وقتی flush کند تغییرها را با هم می‌فرستد. برای دیدن رفتارش یک مشتری اضافه کردم و در سه لحظه ردیف‌ها را شمردم. پیش از آن ۳ مشتری داشتیم:

```text
autoflush sees it: 4
after rollback: 3
after commit: 4
```

بعد از `s.add(...)` یک query شمارش زدم و ۴ گرفتم، با اینکه commit نکرده بودم. دلیلش **autoflush** است: session پیش از اجرای query، تغییرهای منتظرش را (داخل transaction باز) به پایگاه داده می‌فرستد تا query آن‌ها را ببیند. بعد `rollback()` درج را برگرداند و شمارش دوباره ۳ شد. بعد از اینکه دوباره اضافه کردم و `commit()` زدم، ردیف ماندگار شد: ۴.

## یک IntegrityError واقعی

وقتی پایگاه داده یک تغییر را نمی‌پذیرد چه می‌شود؟ مشتریی با ایمیل تکراری اضافه کردم و commit زدم. SQLAlchemy `IntegrityError` پرتاب کرد و خطای اصلی driver داخل آن این است:

```text
UniqueViolation | duplicate key value violates unique constraint "customers_email_key"
```

`unique=True` در مدل به یک constraint واقعی در Postgres تبدیل شد، پس پایگاه داده آن را اعمال کرد، نه Python. خطا را بگیرید و بعد `rollback()` بزنید. session بعد از خطا در حالت خراب می‌ماند و تا rollback نکنید برای هیچ کاری قابل استفاده نیست.

## N+1، شمرده‌شده

حالا حلقه‌ی ابتدای پست. برای اینکه query‌ها را بشمارم و حدس نزنم، به رویداد `before_cursor_execute` یک listener وصل کردم، رویدادی که SQLAlchemy پیش از هر دستوری که می‌فرستد آن را اجرا می‌کند، و در آن یک شمارنده زیاد کردم. بعد همان کار را سه‌جور اجرا کردم. هر کدام همه‌ی مشتری‌ها را می‌خواند و طول لیست `orders` آن‌ها را جمع می‌زند. پایگاه داده ۴ مشتری و ۵ سفارش داشت:

```python
def lazy():
    with Session(engine) as s:
        return sum(len(c.orders) for c in s.scalars(select(Customer)))
def selectin():
    with Session(engine) as s:
        return sum(len(c.orders) for c in s.scalars(select(Customer).options(selectinload(Customer.orders))))
def joined():
    with Session(engine) as s:
        return sum(len(c.orders) for c in s.scalars(select(Customer).options(joinedload(Customer.orders))).unique())
```

```text
lazy: 5 queries, result=5
selectinload: 2 queries, result=5
joinedload: 1 queries, result=5
```

هر سه یک جواب می‌دهند، ۵ سفارش. فرق در تعداد رفت‌وبرگشت به پایگاه داده است:

- **Lazy loading** پیش‌فرض است. یک query مشتری‌ها را می‌آورد، و بعد اولین دسترسی هر مشتری به `.orders` یک query دیگر می‌زند. می‌شود ۱ + ۴ = ۵، یعنی الگوی {{< term "n-plus-one" "N+1" >}}: یک query به‌علاوه‌ی N تای دیگر.
- **`selectinload`** مشتری‌ها را می‌آورد و بعد یک query دیگر برای سفارش‌های همه‌ی آن‌ها با هم می‌زند، با `WHERE customer_id IN (...)`. دو query، هر تعداد مشتری که باشد.
- **`joinedload`** از یک JOIN استفاده می‌کند، پس یک query. چون مشتریِ دارای سه سفارش در سه ردیف ظاهر می‌شود، باید روی نتیجه `.unique()` بزنید تا هر مشتری یک بار بیاید.

کدام بهتر است به شکل داده بستگی دارد، و JOIN همیشه ارزان‌تر نیست. چیزی که باید با خودتان ببرید این است که بشمارید. برای نمونه‌ی واقعی پیدا کردن یک query کند، [پیدا کردن query کند](/fa/posts/db-slow-query-case-study/) را ببینید.

## دیدن SQL

اگر می‌خواهید ببینید ORM چه می‌فرستد، `create_engine(url, echo=True)` هر دستور را لاگ می‌کند. برای یک `select(Customer).where(Customer.id == 1)` لاگ این بود:

```text
BEGIN (implicit)
SELECT customers.id, customers.email
FROM customers
WHERE customers.id = %(id_1)s::INTEGER
[generated ...] {'id_1': 1}
ROLLBACK
```

زمان‌ها را برداشتم، و همچنین سه query راه‌اندازی که SQLAlchemy اولین بار که وصل می‌شود می‌زند (نسخه، schema جاری و تنظیم رشته‌ها). از بالا بخوانید: session یک transaction شروع کرد، یک `SELECT` با placeholder فرستاد و مقدار `1` را جدا فرستاد. `ROLLBACK` آخر فقط بسته شدن session بدون هیچ تغییری است.

می‌توانید یک query را بدون اجرا هم چاپ کنید: `str(query)` همان SQL را با placeholder می‌دهد. اگر آن را با `literal_binds` کامپایل کنید مقدارها داخلش می‌نشینند و می‌شود بعد از `EXPLAIN` پیست کرد. برای `select(Order).where(Order.customer_id == 1)` جواب Postgres `Seq Scan on orders` با `Filter: (customer_id = 1)` بود: کل جدول را خواند. جدول کوچک است و اینجا اشکالی ندارد، ولی توجه کنید که روی `customer_id` ایندکس نیست. Postgres خودش برای foreign key ایندکس نمی‌سازد. روی جدول بزرگ باید اضافه‌اش کنید ([ایندکس B-tree](/fa/posts/db-indexes-btree-explain/)).

## connection pool

باز کردن اتصال به پایگاه داده کند است، برای همین SQLAlchemy تعدادی اتصال را در یک استخر ({{< term "connection-pool" "connection pool" >}}) نگه می‌دارد و قرض می‌دهد. استخر حد دارد و ارزش دارد یک بار ببینیم سر حد چه می‌شود:

```python
create_engine(url, pool_size=2, max_overflow=1, pool_pre_ping=True, pool_timeout=1)
```

این استخر ۲ اتصال نگه می‌دارد و زیر فشار می‌تواند ۱ اتصال اضافه باز کند، یعنی حداکثر ۳. سه اتصال برداشتم و `engine.pool.status()` را چاپ کردم:

```text
Pool size: 2  Connections in pool: 0 Current Overflow: 1 Current Checked out connections: 3
```

چیزی در استخر نمانده و یک اتصال overflow در حال استفاده است. درخواست چهارم باید صبر می‌کرد و بعد از `pool_timeout=1` ثانیه شکست خورد:

```text
TimeoutError | QueuePool limit of size 2 overflow 1 reached, connection timed out, timeout 1.00
```

بعد از اینکه هر سه را بستم، وضعیت `Connections in pool: 2 ... Checked out connections: 0` بود: اتصال‌ها برای استفاده‌ی دوباره به استخر برگشتند و اتصال overflow بسته شد. `pool_pre_ping=True` باعث می‌شود استخر پیش از دادن اتصال، آن را با یک query کوچک امتحان کند، پس اتصالی که در حالت بیکاری مرده، عوض می‌شود و درخواست شما خطا نمی‌گیرد. اینکه چرا استخر لازم است در [connection pooling](/fa/posts/db-connection-pooling/) آمده.

## سطح‌های isolation

transactionهایی که هم‌زمان اجرا می‌شوند، بسته به سطح isolation، تغییرهای هم را به شکل‌های متفاوتی می‌بینند. SQLAlchemy اجازه می‌دهد آن را برای کل engine یا برای یک اتصال تنظیم کنید. `create_engine(url, isolation_level="REPEATABLE READ")` باعث شد `SHOW transaction_isolation` مقدار `repeatable read` برگرداند، و `execution_options(isolation_level="SERIALIZABLE")` روی یک اتصال `serializable` برگرداند. معنی واقعی سطح‌ها در [سطح‌های isolation](/fa/posts/db-isolation-levels-anomalies/) آمده. اینجا session هم‌زمان اجرا نکردم و فقط دیدم که تنظیم به Postgres می‌رسد.

## Alembic: تغییر schema به‌شکل کد

تا اینجا دمو جدول‌ها را با `create_all` می‌ساخت، که برای دمو خوب است ولی نمی‌تواند جدول موجود را تغییر دهد. **Alembic** تاریخچه‌ی schema را به‌شکل فایل‌های migration شماره‌دار نگه می‌دارد. دستور `alembic revision --autogenerate` مدل‌های شما را با پایگاه داده‌ی واقعی مقایسه می‌کند و برای تفاوت یک migration می‌نویسد. روی پایگاه داده‌ی خالی، یک migration با `op.create_table` برای هر دو جدول نوشت. بعد `alembic upgrade head --sql` به‌جای اجرا، SQLی را که اجرا می‌کرد چاپ کرد:

```text
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, ...);
CREATE TABLE customers (id SERIAL NOT NULL, email VARCHAR(100) NOT NULL, PRIMARY KEY (id), UNIQUE (email));
CREATE TABLE orders (id SERIAL NOT NULL, customer_id INTEGER NOT NULL, total INTEGER NOT NULL, PRIMARY KEY (id), FOREIGN KEY(customer_id) REFERENCES customers (id));
INSERT INTO alembic_version (version_num) VALUES ('15ffbe55f27f') ...;
```

(فاصله‌ها فشرده شده‌اند؛ شناسه‌ی revision یعنی `15ffbe55f27f` از اجرای اولیه است و اجرای تازه شناسه‌ی دیگری می‌سازد.) جدول اول، `alembic_version`، دفتر حساب خود Alembic است: ذخیره می‌کند پایگاه داده روی کدام revision است، و خط آخر همان را ثبت می‌کند. بعد `upgrade head` migration را اجرا کرد، `alembic current` همان revision را با `(head)` نشان داد و `alembic check` جواب داد `No new upgrade operations detected`، یعنی مدل‌ها و پایگاه داده با هم می‌خوانند. `downgrade` را اجرا نکردم. اینکه یک جدول زنده را بدون توقف چطور تغییر دهید در [migration بدون downtime](/fa/posts/db-zero-downtime-migrations/) آمده.

## Async

SQLAlchemy با asyncio هم کار می‌کند. `create_async_engine` با همان URL مربوط به psycopg، سه query را هم‌زمان با `asyncio.gather` اجرا کرد و `[5, 6, 7]` برگرداند (هر query مقدار `i + count(*)` را روی ۵ سفارش حساب می‌کند، برای `i` برابر ۰، ۱، ۲؛ به [asyncio در Python](/fa/posts/py-asyncio/) نگاه کنید). اجرای اول من با `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed` شکست خورد؛ نصب `greenlet` درستش کرد.

## در مقایسه با sqlc و pgx

با sqlc خودتان SQL را می‌نویسید و تابع‌های Go تولیدشده و نوع‌بررسی‌شده می‌گیرید؛ ORM برعکس عمل می‌کند و از روی شیءها SQL می‌سازد. در هر دو حالت زیرش connection pool و bind کردن پارامتر هست، و در هر دو باید همچنان به SQLی که واقعاً اجرا می‌شود نگاه کنید.

## چه چیزهایی را بشمارید و مرور کنید

- query‌ها را در تست بشمارید. lazy loading مشکل N+1 را پنهان می‌کند و کد کاملاً سالم به نظر می‌رسد.
- بعد از خطا، پیش از استفاده‌ی دوباره از session، rollback بزنید؛ وگرنه فراخوانی بعدی با پیام گیج‌کننده شکست می‌خورد.
- `pool_size + max_overflow` را با `max_connections` در Postgres بسنجید، و یادتان باشد هر process برنامه استخر خودش را دارد.
- migrationهای تولیدشده را پیش از اجرا بخوانید؛ بی‌چون‌وچرا به آن‌ها اعتماد نکنید. طبق مستندات Alembic، autogenerate همه‌چیز را تشخیص نمی‌دهد، مثلاً تغییر نام یک ستون شبیه حذف به‌علاوه‌ی اضافه است.

## تمرین

جدول `order_items` و یک migration برایش اضافه کنید. مشتری‌ها را با سفارش‌ها و آیتم‌هایشان با `selectinload` تودرتو بارگذاری کنید و تستی بنویسید که تعداد query را بررسی کند.

## قدم بعدی

قدم بعد: «بسته‌بندی و انتشار پروژه‌ی Python»، چون کد وقتی برای دیگران مفید می‌شود که بتوانند آن را نصب کنند.
