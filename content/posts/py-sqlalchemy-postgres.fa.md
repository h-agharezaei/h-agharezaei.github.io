+++
date = '2027-05-01T10:00:00+03:30'
draft = false
title = 'SQLAlchemy و Postgres'
description = 'SQLAlchemy 2.1 با Postgres: text() در Core، Session در ORM، شمارش واقعی N+1، محدودیت pool، IntegrityError، isolation، Alembic و async، همه اجرا شده.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "sqlalchemy", "postgres", "alembic", "orm"]
cover = { image = "/images/covers/py-sqlalchemy-postgres.fa.png", alt = "SQLAlchemy و Postgres", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-fastapi-pydantic/) API ما پایگاه داده نداشت؛ اینجا یکی اضافه می‌کنیم. SQLAlchemy دو لایه دارد: Core (SQL به شکل Python، با پارامتر bind‌شده) و {{< term "orm" "ORM" >}} روی آن. اگر در Node از `pg` ([Postgres از Node.js](/fa/posts/node-postgres-pg/)) یا در Go از pgx ([Postgres با pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/)) استفاده کرده‌اید، Core را مثل driver و ORM را یک افزونه‌ی اختیاری ببینید.

> Python 3.14.0، SQLAlchemy 2.1.6، psycopg 3.3.6 (با `[binary]` و libpq همراه نسخه‌ی 18.0.6)، Alembic 1.20.1، greenlet 3.5.6، PostgreSQL 18.3 واقعی روی `127.0.0.1`، در venv موقت. port‌ها با `<port>` جایگزین شده‌اند. تعداد منتشر می‌کنم، نه زمان.

## Core: متن text() و پارامتر

```python
with engine.begin() as c:
    c.execute(text("INSERT INTO customers (email) VALUES (:e)"), [{"e": "a@example.com"}, ...])
    c.execute(text("SELECT count(*) FROM customers WHERE email = :e"), {"e": "x' OR '1'='1"}).scalar()
```

خط دوم `0` چاپ کرد: مقدار به‌عنوان پارامتر می‌رود، پس داده است نه SQL ({{< term "parameterized-query" "parameterized query" >}}). `engine.begin()` یک {{< term "transaction" "transaction" >}} باز می‌کند و در پایان commit می‌کند.

## ORM: Session به‌عنوان unit of work

```python
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
```

`Order` یک `ForeignKey("customers.id")` و رابطه‌ی معکوس `customer` دارد. `Session` یک {{< term "unit-of-work" "unit of work" >}} است: تغییرها را جمع می‌کند و با هم flush می‌کند. یک مشتری اضافه کردم و ردیف‌ها را شمردم:

```text
autoflush sees it: 4
after rollback: 3
after commit: 4
```

query اول، INSERT منتظر را flush کرد (autoflush) و ۴ دید. `rollback()` آن را برگرداند و `commit()` ماندگارش کرد.

## یک IntegrityError واقعی

اضافه‌کردن ایمیل تکراری و commit باعث `IntegrityError` شد؛ خطای driver که داخلش است:

```text
UniqueViolation | duplicate key value violates unique constraint "customers_email_key"
```

آن را بگیرید و `rollback()` بزنید: تا این کار را نکنید session قابل استفاده نیست.

## N+1 با شمارش واقعی

با hook روی `before_cursor_execute` دستورها را شمردم؛ ۴ مشتری و ۵ سفارش:

```text
lazy: 5 queries, result=5
selectinload: 2 queries, result=5
joinedload: 1 queries, result=5
```

پیش‌فرض lazy loading است: یک query برای مشتری‌ها و بعد یکی برای هر مشتری ({{< term "n-plus-one" "N+1" >}}). `selectinload` query دومی با `IN (...)` می‌زند و `joinedload` از JOIN استفاده می‌کند (و روی نتیجه `.unique()` لازم دارد). انتخاب بهتر به شکل داده بستگی دارد؛ نکته این است که بشمارید. نمونه‌اش در [پیدا کردن query کند](/fa/posts/db-slow-query-case-study/).

## دیدن SQL

`create_engine(url, echo=True)` همه‌چیز را log می‌کند. برای `select(Customer).where(Customer.id == 1)`:

```text
BEGIN (implicit)
SELECT customers.id, customers.email
FROM customers
WHERE customers.id = %(id_1)s::INTEGER
[generated ...] {'id_1': 1}
ROLLBACK
```

(زمان‌ها حذف شده‌اند.) `str(query)` همان SQL را با placeholder چاپ می‌کند و اگر با `literal_binds` کامپایل کنید می‌توانید در `EXPLAIN` بگذارید. اینجا Postgres این را انتخاب کرد: `Seq Scan on orders` با `Filter: (customer_id = 1)`؛ جدول کوچک است و روی `customer_id` ایندکسی نیست، چون Postgres برای foreign key خودکار ایندکس نمی‌سازد ([ایندکس B-tree](/fa/posts/db-indexes-btree-explain/)).

## Pool

```python
create_engine(url, pool_size=2, max_overflow=1, pool_pre_ping=True, pool_timeout=1)
```

سه اتصال گرفتم و `engine.pool.status()` گفت: `Pool size: 2  Connections in pool: 0 Current Overflow: 1 Current Checked out connections: 3`. اتصال چهارم بعد از یک ثانیه شکست خورد:

```text
TimeoutError | QueuePool limit of size 2 overflow 1 reached, connection timed out, timeout 1.00
```

بعد از بستن همه، وضعیت `Connections in pool: 2 ... Checked out connections: 0` شد. `pool_pre_ping` اتصال را پیش از استفاده آزمایش می‌کند. پیش‌زمینه: [connection pooling](/fa/posts/db-connection-pooling/).

## سطح‌های isolation

`create_engine(url, isolation_level="REPEATABLE READ")` باعث شد `SHOW transaction_isolation` مقدار `repeatable read` بدهد؛ برای یک اتصال، `execution_options(isolation_level="SERIALIZABLE")` مقدار `serializable` داد. معنای سطح‌ها در [سطح‌های isolation](/fa/posts/db-isolation-levels-anomalies/) است؛ اینجا session هم‌زمان اجرا نکردم.

## Alembic

با Alembic، دستور `revision --autogenerate` مدل‌هایم را با پایگاه خالی مقایسه کرد و یک migration با `op.create_table` برای دو جدول نوشت. `upgrade head --sql` این DDL را چاپ کرد:

```text
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, ...);
CREATE TABLE customers (id SERIAL NOT NULL, email VARCHAR(100) NOT NULL, PRIMARY KEY (id), UNIQUE (email));
CREATE TABLE orders (id SERIAL NOT NULL, customer_id INTEGER NOT NULL, total INTEGER NOT NULL, PRIMARY KEY (id), FOREIGN KEY(customer_id) REFERENCES customers (id));
INSERT INTO alembic_version (version_num) VALUES ('15ffbe55f27f') ...;
```

(فاصله‌ها فشرده شده‌اند.) بعد `upgrade head` آن را اعمال کرد، `current` مقدار `15ffbe55f27f (head)` نشان داد و `alembic check` گفت `No new upgrade operations detected`. تغییر امن روی جدول زنده: [migration بدون downtime](/fa/posts/db-zero-downtime-migrations/). `downgrade` را اجرا نکردم.

## Async

`create_async_engine` با همان URL و psycopg، سه query را با `asyncio.gather` اجرا کرد و `[5, 6, 7]` برگرداند ([asyncio](/fa/posts/py-asyncio/)). تلاش اول با `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed` شکست خورد؛ نصب `greenlet` درستش کرد.

## در برابر sqlc و pgx

در sqlc شما SQL می‌نویسید و تابع Go تولیدشده و type-checked می‌گیرید؛ ORM برعکس است و از شیء، SQL می‌سازد. در هر دو حالت زیرش یک connection pool و bind پارامتر وجود دارد.

## چند نکته‌ی مهم

- query‌ها را در تست بشمارید؛ lazy loading، N+1 را پنهان می‌کند.
- بعد از خطا، پیش از استفاده‌ی دوباره از session، rollback کنید.
- `pool_size + max_overflow` را با `max_connections` در Postgres هماهنگ کنید.
- migration‌های خودکار را مرور کنید؛ کورکورانه اعتماد نکنید.

## تمرین

جدول `order_items` و migration‌اش را اضافه کنید. مشتری‌ها را با سفارش‌ها و آیتم‌ها با `selectinload` تو در تو بخوانید و تعداد query را assert کنید.

## قدم بعدی

مقاله‌ی بعد «بسته‌بندی و انتشار پروژه‌ی Python» است.
