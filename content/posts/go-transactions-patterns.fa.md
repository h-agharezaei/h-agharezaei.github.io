+++
date = '2027-01-19T10:00:00+03:30'
draft = false
title = 'تراکنش و الگوی Repository در Go'
description = 'تراکنش‌ها با pgx در Go: rollback، تابع کمکی WithTx، unit of work روی repository، lost update، SELECT FOR UPDATE، retry برای serializable و مشکل N+1.'
contentType = 'engineering'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "transactions", "pgx", "repository"]
cover = { image = "/images/covers/go-transactions-patterns.fa.png", alt = "تراکنش و الگوی Repository در Go", hiddenInSingle = true }
+++

alice به carol صد واحد پول می‌فرستد. کد دو کار می‌کند: صد واحد از موجودی alice کم می‌کند و بعد صد واحد به موجودی carol اضافه می‌کند. حالا فرض کنید carol به سقف حسابش نزدیک است و قدم دوم شکست می‌خورد. بر سر قدم اول چه می‌آید؟ اگر چیزی آن را برنگرداند، alice صد واحد از دست داده، carol چیزی نگرفته و پول از سیستم ناپدید شده است.

هر سرویسی که در دیتابیس می‌نویسد دیر یا زود به این وضعیت می‌رسد: یک کار تجاری دو یا چند نوشتن لازم دارد و یا همه‌ی آن‌ها باید انجام شوند یا هیچ‌کدام. ابزار این کار **{{< term "transaction" "تراکنش" >}}** (transaction) است. در store نوشته‌ی [Postgres با pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/) هر فراخوانی دنیای جدا از بقیه است و چیزی دو فراخوانی را به هم نمی‌بندد. در این نوشته اول همین پولِ گم‌شده را بازسازی می‌کنیم، بعد با تراکنش درستش می‌کنیم، بعد می‌بینیم چطور تراکنش را از کد تجاری دور نگه داریم و آخر سراغ مشکل‌هایی می‌رویم که تراکنش به‌تنهایی حل نمی‌کند: دو کلاینت که هم‌زمان به یک ردیف دست می‌زنند.

> همه‌چیز دوباره با Go 1.27 روی macOS (arm64)، pgx نسخه‌ی v5.11.0 و یک PostgreSQL 18.3 واقعی اجرا شده است که ماژول embedded-postgres بالا می‌آورد، مثل نوشته‌ی قبل. دمو یک نسخه‌ی محلی از دموی قبلی است با یک migration دوم که جدول `accounts` و جدول `order_items` را اضافه می‌کند. جدول `accounts` ستون `balance` دارد و دو `CHECK` نام‌دار موجودی را بین 0 و 10000 نگه می‌دارند. دمو یک مثال محلی است و ریپوی منتشرشده ندارد.

## نسخه‌ی خراب: بدون تراکنش

ایده‌ی تراکنش ساده است: گروهی از دستورها که دیتابیس آن‌ها را یک واحد می‌بیند. یا همه اثر می‌کنند یا هیچ‌کدام. برای اینکه ببینیم چرا لازم است، اول انتقال را بدون آن نوشتم. repository دو متد `Debit` و `Credit` دارد و هرکدام یک `UPDATE` اجرا می‌کند:

```go
func (r Repo) add(ctx context.Context, id string, delta int64) error {
	tag, err := r.db.Exec(ctx,
		`UPDATE accounts SET balance = balance + $2 WHERE id = $1`, id, delta)
	// ... maps the CHECK constraint names to ErrInsufficient / ErrLimit ...
}
```

repository اینجا مستقیم روی connection pool ساخته شده، پس انتقال فقط دو فراخوانی پشت سر هم است:

```go
r := pgbank.NewRepo(pool)
err := r.Debit(ctx, "alice", 100)
if err == nil {
	err = r.Credit(ctx, "carol", 100)
}
```

بدون تراکنش، Postgres هر دستور را تراکنشِ جدایی حساب می‌کند و به محض تمام‌شدنش commit می‌کند. پس برداشت ماندگار است، حتی پیش از آنکه واریز شروع شود. alice هزار واحد دارد، carol 9950 و سقف حساب 10000 است، پس واریز صد واحد باید شکست بخورد. خروجی:

```
before: alice=1000 carol=9950 total=10950
transfer error: account limit exceeded
after : alice=900 carol=9950 total=10850
```

عدد آخر هر خط مجموع دو موجودی است. در یک انتقال این مجموع هیچ‌وقت نباید عوض شود. از 10950 به 10850 رفت: برداشت commit شد، واریز را قید `CHECK` رد کرد و صد واحد ناپدید شد.

حالا همان انتقال داخل یک تراکنش:

```
transfer error: account limit exceeded | is ErrLimit: true
after : alice=1000 carol=9950 total=10950
```

واریز باز هم با همان خطا شکست می‌خورد، اما این بار برداشت هم برگشت داده می‌شود و مجموع دوباره 10950 است. ویژگی‌ای که دیدیم **atomicity** (تجزیه‌ناپذیری) نام دارد: یا همه، یا هیچ. (حرف «A» در {{< term "acid" "ACID" >}} است.)

## Begin، Commit، Rollback

تراکنش سه حرکت دارد. `Begin` آن را باز می‌کند و هرچه بعد از آن اجرا کنید از چشم بقیه‌ی کلاینت‌ها پنهان می‌ماند. `Commit` همه‌ی آن‌ها را یکجا ماندگار می‌کند. `Rollback` همه را دور می‌ریزد. در pgx این‌طور نوشته می‌شود:

```go
tx, err := pool.Begin(ctx)
if err != nil {
	return err
}
defer tx.Rollback(ctx) // safe to leave in place
// ... tx.Exec, tx.Query ...
return tx.Commit(ctx)
```

خط `defer` مهم‌ترین خط است. وسط کار هرچه پیش بیاید، `return` زودهنگام بعد از یک خطا یا یک panic، تراکنش rollback می‌شود و اتصال به pool برمی‌گردد. بعد از یک `Commit` موفق، `Rollback` دیفرشده کاری ندارد که بکند. یک بار آن را صریح صدا زدم تا ببینم چه می‌گوید:

```
commit: <nil>
rollback after commit: tx is closed | is ErrTxClosed: true
```

commit درست انجام شد (`<nil>` یعنی بدون خطا) و فراخوانی دوم `pgx.ErrTxClosed` برگرداند که بی‌ضرر است. برای همین `defer` می‌تواند در مسیر موفق هم بماند و خطایش را ساده نادیده می‌گیرید.

یک هزینه را فراموش نکنید: تراکنش تا پایانش یک اتصال از pool را نگه می‌دارد. پس تراکنش را کوتاه نگه دارید و داخلش درخواست HTTP یا کار کند دیگری نکنید.

## یک helper به نام WithTx

نوشتن این بلوک در هر تابع آدم را به اشتباه می‌اندازد: فراموش‌کردن rollback در یک شاخه یا فراموش‌کردن panic. برای همین یک بار آن را بسته‌بندی می‌کنم:

```go
func WithTx(ctx context.Context, pool *pgxpool.Pool, opts pgx.TxOptions, fn func(pgx.Tx) error) error {
	tx, err := pool.BeginTx(ctx, opts)
	if err != nil {
		return err
	}
	defer func() {
		if p := recover(); p != nil {
			_ = tx.Rollback(ctx)
			panic(p)
		}
	}()
	if err := fn(tx); err != nil {
		_ = tx.Rollback(ctx)
		return err
	}
	return tx.Commit(ctx)
}
```

قاعده سه خط است. اگر `fn` خطا برگرداند، rollback کن و خطا را برگردان. اگر `fn` panic کند، rollback کن و بگذار panic ادامه پیدا کند. در غیر این صورت commit کن. برای آزمودن حالت panic، دمو `fn` را طوری می‌نویسد که موجودی alice را صفر کند و بعد با `"boom"` panic کند:

```
recovered: boom
after : alice=1000 carol=0 total=1000
```

خط `recovered: boom` از یک `recover` در خودِ دمو می‌آید، بیرون از `WithTx`. موجودی alice هنوز 1000 است، یعنی `UPDATE` نیمه‌کاره rollback شده. تا جایی که از مستندات pgx می‌دانم، pgx هم یک helper مشابه به نام `pgx.BeginFunc` دارد. من نسخه‌ی خودم را نوشتم تا مدیریت panic دیده شود.

## تراکنش را از کد domain دور نگه داریم

حالا تراکنش داریم، اما یک سؤال طراحی مانده. سرویس تصمیم می‌گیرد چه چیزهایی با هم‌اند (برداشت و واریز در یک انتقال) و repository SQL را می‌شناسد. سرویس چطور بگوید «این‌ها با هم» بی‌آنکه pgx را import کند و `tx` را بشناسد؟

اول اینکه repository نباید اهمیت بدهد داخل تراکنش اجرا می‌شود یا نه. هم `*pgxpool.Pool` و هم `pgx.Tx` همین سه متد را دارند، پس repository به یک interface کوچک وابسته می‌شود. اسم رایجش **DBTX** است:

```go
type DBTX interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type Repo struct{ db DBTX }
func NewRepo(db DBTX) Repo { return Repo{db: db} }
```

می‌توانید به `NewRepo` خودِ pool بدهید (هر فراخوانی جداگانه commit می‌شود، مثل نسخه‌ی خراب) یا یک `tx` (هر فراخوانی عضو تراکنش می‌شود). همان کد repository در هر دو حالت کار می‌کند.

دوم اینکه سرویس تصمیم مرز تراکنش را با یک interface به نام {{< term "unit-of-work" "unit of work" >}} (واحد کار) می‌گیرد: «این تابع را طوری اجرا کن که هرچه داخلش هست با هم commit یا با هم rollback شود». بسته‌ی سرویس آن را تعریف می‌کند و pgx را import نمی‌کند. بسته‌ی Postgres آن را پیاده می‌کند:

```go
// package bank (no pgx import)
type UnitOfWork interface {
	Do(ctx context.Context, fn func(Accounts) error) error
}

func (s *Service) Transfer(ctx context.Context, from, to string, cents int64) error {
	return s.uow.Do(ctx, func(a Accounts) error {
		if err := a.Debit(ctx, from, cents); err != nil {
			return err
		}
		return a.Credit(ctx, to, cents)
	})
}

// package pgbank
func (u UoW) Do(ctx context.Context, fn func(bank.Accounts) error) error {
	return WithTx(ctx, u.Pool, pgx.TxOptions{}, func(tx pgx.Tx) error {
		return fn(NewRepo(tx))
	})
}
```

`Transfer` را مثل یک جمله‌ی ساده بخوانید: «در یک واحد کار، برداشت کن و بعد واریز کن». سرویس نمی‌داند تراکنشی وجود دارد. `Do` آن را باز می‌کند، به `fn` یک repository وصل‌شده به آن می‌دهد و بسته به آنچه `fn` برمی‌گرداند commit یا rollback می‌کند. این همان شکل interfaceهای repository در نوشته‌های قبل است: سرویس می‌گوید چه لازم دارد و بسته‌ی دیتابیس آن را برآورده می‌کند ([ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/)).

یک نکته‌ی دیگر: repository نام قیدها را به خطای domain ترجمه می‌کند (`non_negative` می‌شود `ErrInsufficient` و `under_limit` می‌شود `ErrLimit`)، مثل [config، logging و خطاها](/fa/posts/go-config-logging-errors/). اجرای سرویس دو بار، یک بار با مبلغ معتبر و یک بار با مبلغی بزرگ‌تر از موجودی:

```
transfer 100: <nil>
after : alice=900 carol=100 total=1000
transfer 5000: insufficient funds
after : alice=900 carol=100 total=1000
```

انتقال اول صد واحد را جابه‌جا کرد و مجموع 1000 ماند. انتقال دوم می‌خواست از موجودی 900 مبلغ 5000 بردارد، قید `non_negative` آن را رد کرد و چیزی تغییر نکرد.

## دو تراکنش هم‌زمان: lost update

تا اینجا هر بار یک تراکنش داشتیم. سرور واقعی چندتا را هم‌زمان اجرا می‌کند و تراکنش به‌تنهایی جلوی دخالت آن‌ها در کار هم را نمی‌گیرد. مثال کلاسیکش این است. دو worker هرکدام می‌خواهند صد واحد به موجودی alice اضافه کنند. هرکدام سه کار می‌کند: موجودی را می‌خواند، کمی «فکر می‌کند» (دمو 300 میلی‌ثانیه می‌خوابد تا دو worker روی هم بیفتند) و `balance + 100` را می‌نویسد. اگر پشت سر هم اجرا شوند alice به 1200 می‌رسد. ببینید وقتی هم‌زمان‌اند چه می‌شود:

```
plain read      : alice=1100 carol=0 total=1100
SELECT FOR UPDATE: alice=1200 carol=0 total=1200
```

در خط اول هر دو worker عدد 1000 را خواندند، هر دو 1100 حساب کردند و هر دو 1100 نوشتند. یکی از دو افزایش گم شد. این را {{< term "lost-update" "lost update" >}} (به‌روزرسانی گم‌شده) می‌گویند. در سطح {{< term "isolation-level" "isolation" >}} پیش‌فرض Postgres، یعنی **READ COMMITTED**، پیش می‌آید. در این سطح هر دستور آنچه را می‌بیند که پیش از شروعش commit شده بود. هر دو خواندن پیش از هر دو نوشتن بود، پس هر دو 1000 دیدند.

خط دوم همان کد است، اما خواندنش `SELECT balance ... FOR UPDATE` است. این از Postgres می‌خواهد موقع خواندن روی ردیف {{< term "lock" "قفل" >}} (row lock) بگذارد. حالا `SELECT` worker دوم باید صبر کند تا تراکنش اول commit شود و بعد مقدار تازه‌ی 1100 را می‌خواند. نتیجه همان 1200 مورد انتظار است.

## راه دوم: serializable و تکرار

قفل یک راه امن‌بودن است. راه دیگر این است که از Postgres سخت‌گیرترین سطح isolation را بخواهید، یعنی **SERIALIZABLE**: SQL معمولی می‌نویسید، بدون `FOR UPDATE`، و Postgres مطمئن می‌شود نتیجه همان باشد که تراکنش‌ها یکی‌یکی اجرا شده بودند. وقتی نتواند این را تضمین کند یکی از آن‌ها را abort می‌کند:

```go
pgx.TxOptions{IsoLevel: pgx.Serializable}
```

```
worker 1: <nil>
worker 0: ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)
no retry: alice=1100 carol=0 total=1100
```

یک worker موفق شد و دیگری خطایی با کد {{< term "sqlstate" "SQLSTATE" >}} برابر `40001` گرفت. موجودی 1100 است، یعنی فقط یک افزایش اعمال شده. اینکه کدام worker شکست بخورد از اجرایی به اجرای دیگر فرق می‌کند، چون به زمان‌بندی بستگی دارد. این شکست باگ کد شما نیست. روش کار حالت serializable همین است و جوابش اجرای دوباره‌ی کل تراکنش است:

```go
func retry(fn func() error) error {
	for attempt := 1; ; attempt++ {
		err := fn()
		if err == nil || !isCode(err, "40001") || attempt == 5 {
			return err
		}
		fmt.Printf("  attempt %d failed with 40001, retrying\n", attempt)
	}
}
```

(`isCode` یک helper کوچک در دمو است که با `errors.As` مقدار `*pgconn.PgError` را پیدا می‌کند و `Code` آن را مقایسه می‌کند.) با همین retry دور همان دو worker:

```
  attempt 1 failed with 40001, retrying
with retry: alice=1200 carol=0 total=1200
total attempts: 3
```

موجودی نهایی همان 1200 مورد انتظار است. یک worker دو تلاش لازم داشت و دیگری یک تلاش، پس در مجموع سه تلاش. دو قاعده همراه این کار می‌آید. تابعی که تکرار می‌کنید باید اجرای دوباره‌اش بی‌خطر باشد، پس داخلش ایمیل نفرستید. و کل تراکنش را تکرار کنید، نه فقط آخرین دستور را، چون خواندن‌های قبلی حالا ممکن است کهنه شده باشند.

## Deadlock

قفل یک مشکل دیگر هم می‌آورد. فرض کنید تراکنش A روی alice قفل می‌گذارد و بعد carol را می‌خواهد، و تراکنش B اول carol را قفل کرده و حالا alice را می‌خواهد. هرکدام برای همیشه منتظر دیگری می‌ماند. این یک {{< term "deadlock" "deadlock" >}} (بن‌بست) است. Postgres آن را تشخیص می‌دهد (طبق مستنداتش به‌طور پیش‌فرض بعد از حدود یک ثانیه انتظار) و یکی از دو تراکنش را می‌کشد:

```
  worker 1 (carol then alice): ERROR: deadlock detected (SQLSTATE 40P01)
  worker 0 (alice then carol): <nil>
```

باز هم اینکه کدام worker قربانی شود فرق می‌کند. بهترین دفاع این است که همیشه ردیف‌ها را به یک ترتیب لمس کنید، مثلاً مرتب‌شده بر اساس id، تا انتظار دایره‌ای هرگز شکل نگیرد. و چون `40P01` هم یعنی «دوباره اجرا کن»، در helper تکرارتان مثل `40001` با آن رفتار کنید.

## کوئری‌های N+1

این یکی به تراکنش ربطی ندارد، اما در همان لایه‌ی repository است و هزینه‌ی زیادی دارد، برای همین اینجا آورده‌ام. فرض کنید 20 سفارش را بارگذاری می‌کنید و هر سفارش چند آیتم دارد. کد وسوسه‌انگیز سفارش‌ها را با یک کوئری می‌خواند و بعد در یک حلقه برای هر سفارش یک کوئری دیگر می‌زند. این می‌شود 1 + 20 کوئری، یعنی الگوی {{< term "n-plus-one" "N+1" >}}. با یک tracer در pgx (قلابی که pgx روی هر کوئری صدا می‌زند) تعداد کوئری‌ها را برای سه نسخه‌ی همین بارگذاری شمردم، با 20 سفارش و 60 آیتم:

```
N+1          orders=20 items=60 queries=21
= ANY($1)    orders=20 items=60 queries=2
JOIN         orders=20 items=60 queries=1
```

حلقه 21 کوئری می‌فرستد. `WHERE order_id = ANY($1)` کل slice شناسه‌ها را یک پارامتر می‌گیرد و همه‌ی آیتم‌ها را با کوئری دوم می‌آورد، یعنی روی هم 2 کوئری. `JOIN` سفارش‌ها و آیتم‌ها را با یک دستور می‌آورد. داده یکی است و فقط تعداد رفت‌وبرگشت به دیتابیس فرق می‌کند. تعداد کوئری‌ها را در کلاینت با tracer شمردم و `pg_stat_statements` را اینجا امتحان نکردم.

## جاهایی که تراکنش دردسر می‌سازد

- **تراکنش طولانی ضرر دارد.** تراکنش یک اتصال pool را اشغال می‌کند و تا پایانش قفل‌هایش را نگه می‌دارد. کوتاهش کنید و داخلش سرویس دیگری را صدا نزنید.
- **برای هر عملیات یک راهبرد انتخاب کنید.** یا با `FOR UPDATE` قفل ردیف بگیرید، یا SERIALIZABLE با retry. ترکیب بی‌دقت آن‌ها گفتن اینکه چه چیزی تضمین شده را سخت می‌کند.
- **`RowsAffected()` را بررسی کنید.** `UPDATE` روی ردیفی که وجود ندارد خطا نیست و فقط صفر ردیف را عوض می‌کند. برای همین `add` وقتی شمارش صفر است `ErrNotFound` برمی‌گرداند.
- **کدی که ممکن است دوبار اجرا شود نباید اثر جانبی بیرون از دیتابیس داشته باشد.** retry ممکن است تابع شما را دوباره اجرا کند و ایمیل یا فراخوانی پرداخت داخلش آن‌وقت دو بار انجام می‌شود.

## قدم بعدی

تا اینجا هم‌زمانی در این نوشته بین کلاینت‌های دیتابیس بود. نوشته‌ی بعد، «الگوهای concurrency: worker pool و errgroup»، به هم‌زمانی داخل خود پروسه‌ی Go می‌رود: goroutineهای زیاد و اینکه چطور آن‌ها را تحت کنترل نگه داریم.
