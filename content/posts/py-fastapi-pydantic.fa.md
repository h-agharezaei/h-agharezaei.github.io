+++
date = '2027-04-22T10:00:00+03:30'
draft = false
title = 'ساخت API با FastAPI و Pydantic'
description = 'FastAPI و Pydantic نسخه‌ی ۲: اعتبارسنجی پارامتر و خطای 422، مدل درخواست، response_model، Depends، handler همگام و ناهمگام، lifespan و SIGTERM.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "fastapi", "pydantic", "api", "validation"]
cover = { image = "/images/covers/py-fastapi-pydantic.fa.png", alt = "ساخت API با FastAPI و Pydantic", hiddenInSingle = true }
+++

فرض کنید دارید یک API می‌سازید که یک endpoint به نام `/items/{item_id}` دارد و شناسه باید عدد صحیح باشد. کسی `/items/abc` را می‌فرستد. در بیشتر فریم‌ورک‌ها حالا خودتان باید کدی بنویسید که مقدار را بررسی کند، پیام خطا بسازد، کد وضعیت انتخاب کند و شکل JSON خطا را تعیین کند. بعد همین کار را برای query string تکرار می‌کنید، و بعد برای تک‌تک فیلدهای هر body. کد خسته‌کننده‌ای است و فراموش کردن یک فیلد هم خیلی آسان است.

FastAPI راه دیگری می‌رود. شما فقط می‌گویید هر ورودی چه شکلی باید داشته باشد، با همان {{< term "type-hint" "type hint" >}}‌های معمولی ([type hint و mypy](/fa/posts/py-type-hints-mypy/))، و فریم‌ورک پیش از اجرای تابع شما درخواست را بررسی می‌کند. اگر بررسی رد شود، تابع شما اصلاً صدا زده نمی‌شود و کلاینت خطایی می‌گیرد که روشن می‌گوید کدام ورودی غلط بوده و چرا. همین تعریف‌ها شکل پاسخ را هم تعیین می‌کنند و مستندات API را هم می‌سازند. بررسی را خود {{< term "pydantic" "Pydantic" >}} انجام می‌دهد، کتابخانه‌ای که annotationهای نوع روی یک کلاس را به یک اعتبارسنج تبدیل می‌کند. اگر Zod را از [اعتبارسنجی ورودی با Zod](/fa/posts/node-validation-zod/) می‌شناسید، ایده همان است. handlerهای `async def` که خواهیم دید روی event loop [پست قبل](/fa/posts/py-asyncio/) اجرا می‌شوند.

> همه‌چیز را دوباره با Python 3.14.0، fastapi 0.162.0، uvicorn 0.54.0، httpx 0.28.1، Pydantic 2.14.1 (یعنی نسخه‌ی ۲) و email-validator 2.3.0 در یک محیط مجازی موقت `uv` اجرا کردم. سرورها روی `127.0.0.1` و با port تصادفی بالا آمدند. اسکریپت‌های دمو مثال‌های محلی‌اند. ترتیب‌ها و تعدادها را نشان می‌دهم، نه زمان‌ها را. (با این نسخه‌ی httpx، import کردن `TestClient` در FastAPI یک هشدار deprecation از Starlette چاپ می‌کند؛ روی هیچ‌کدام از نتیجه‌های پایین اثری ندارد.)

## پارامترها و پاسخ 422

کوچک‌ترین مثال این است: یک path parameter و یک query parameter با مقدار پیش‌فرض.

```python
@app.get("/items/{item_id}")
def item(item_id: int, limit: int = 10):
    return {"item_id": item_id, "limit": limit}
```

FastAPI امضای تابع را می‌خواند. `item_id` در مسیر آمده، پس path parameter است. `limit` در مسیر نیست، پس query parameter است (`?limit=3`) و چون مقدار پیش‌فرض دارد اختیاری است. هر دو با `int` علامت خورده‌اند، پس FastAPI متنی را که می‌رسد به عدد صحیح تبدیل می‌کند. هرچه در URL است متن است، برای همین این تبدیل لازم است و اولین کاری است که اعتبارسنجی می‌کند.

برنامه را با `TestClient` صدا زدم، که درخواست را بدون شبکه و در همان process به برنامه می‌دهد. `/items/5?limit=3` جواب `200 {"item_id": 5, "limit": 3}` داد: رشته‌های `"5"` و `"3"` به‌شکل عدد وارد تابع شدند. حالا درخواست غلط، `/items/abc`:

```text
422 {"detail": [{"type": "int_parsing", "loc": ["path", "item_id"], "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "abc"}]}
```

422 کد وضعیت HTTP برای این جمله است: «درخواست را فهمیدم، ولی داده‌ی داخلش معتبر نیست.» بدنه یک فهرست است، چون ممکن است چند چیز هم‌زمان غلط باشد. هر عضو چهار چیز دارد:

- `loc`: مشکل کجاست. اینجا در مسیر است، پارامتر `item_id`.
- `type`: یک کد کوتاه برای ماشین، اینجا `int_parsing`.
- `msg`: جمله‌ای برای آدم.
- `input`: مقداری که رد شد.

`?limit=x` همین شکل را با `loc: ["query", "limit"]` می‌دهد. در هر دو حالت تابع من هرگز اجرا نشد. نکته همین است: تابع می‌تواند فرض کند آرگومان‌هایش معتبرند.

## مدل درخواست و response_model

query parameter برای ورودی‌های کوچک خوب است. برای body از نوع JSON، شکل داده را با کلاسی که از `BaseModel` ارث می‌برد توصیف می‌کنید:

```python
class UserIn(BaseModel):
    name: str = Field(max_length=20)
    age: int = Field(gt=0)
    email: EmailStr          # needs email-validator
    password: str
    addresses: list[Address] = []

@app.post("/users", response_model=UserOut, status_code=201)
def create(u: UserIn): return u
```

`Field(...)` روی نوع، قاعده اضافه می‌کند: `name` حداکثر ۲۰ نویسه، `age` بزرگ‌تر از صفر. `EmailStr` بررسی می‌کند متن شبیه یک نشانی ایمیل معتبر باشد (برای این به بسته‌ی جداگانه‌ی `email-validator` نیاز است). `addresses` فهرستی از یک مدل دیگر به نام `Address` با `city` و `zip` است، یعنی Pydantic داده‌ی تودرتو را هم اعتبارسنجی می‌کند.

نیمه‌ی دوم ایده `response_model=UserOut` است. `UserOut` همان فیلدها را دارد جز `password`. handler کل `UserIn` را با password برمی‌گرداند و FastAPI پیش از ارسال آن را از `UserOut` رد می‌کند. این یک تور ایمنی است: فقط به این دلیل که کسی شیء اشتباهی را برگردانده، فیلد محرمانه نشت نمی‌کند. یک body معتبر فرستادم که نامش `" Ann "` بود (با فاصله دو طرفش) و پاسخ 201 با این بدنه گرفتم:

```text
{"name": "Ann", "age": 30, "email": "a@example.com", "addresses": [{"city": "Oslo", "zip": "0150"}]}
```

password نیست، فهرست تودرتو سالم است و فاصله‌های نام حذف شده. این فاصله‌ها را Pydantic به‌تنهایی حذف نکرد، یک validator کوچک که خودم نوشتم:

```python
@field_validator("name")
@classmethod
def no_blank(cls, v):
    if not v.strip():
        raise ValueError("name must not be blank")
    return v.strip()
```

`field_validator` بعد از بررسی‌های پایه اجرا می‌شود و می‌تواند مقدار را رد کند یا نسخه‌ی تمیزشده‌اش را برگرداند. وقتی `"  "` را به‌عنوان نام فرستادم، پیام `Value error, name must not be blank` آمد.

اگر چند فیلد هم‌زمان غلط باشند چه می‌شود؟ bodyای فرستادم با نامی ۲۱ حرفی، `age: 0` و ایمیل `"nope"`. پاسخ هر سه خطا را با هم داشت، پس کلاینت می‌تواند همه را در یک رفت‌وبرگشت درست کند. این‌ها خلاصه‌شده به بخش‌های مفید:

```text
string_too_long   ["body","name"]   ctx: {"max_length": 20}
greater_than      ["body","age"]    ctx: {"gt": 0}
value_error       ["body","email"]  value is not a valid email address: An email address must have an @-sign.
```

`ctx` حدی را که شکسته شده نگه می‌دارد، که برای ساختن پیام دوستانه در کلاینت به درد می‌خورد.

## Pydantic چه چیزی را بررسی و چه چیزی را تبدیل می‌کند

تا اینجا Pydantic بی‌هیچ اعتراضی `"5"` را به `5` تبدیل کرد. یعنی نوع را بررسی می‌کند یا درستش می‌کند؟ هر دو، و خوب است بدانیم مرز دقیقاً کجاست. Pydantic را تنها و بدون FastAPI روی مدلی با یک فیلد `n: int` اجرا کردم:

```text
P.model_validate({"n": "5"})   -> P(n=5)
.model_dump() / model_dump_json() -> {'n': 5} / {"n":7}
lax  {'n': 'five'} -> int_parsing
lax  {'n': 5.5}    -> int_from_float
strict '5'         -> int_type | Input should be a valid integer
```

Pydantic به‌طور پیش‌فرض در **حالت lax** کار می‌کند. وقتی تبدیل بی‌خطر و بدیهی باشد انجامش می‌دهد: رشته‌ی `"5"` می‌شود عدد صحیح 5. وقتی نباشد رد می‌کند: `"five"` قابل تبدیل نیست، و `5.5` با `int_from_float` رد می‌شود چون عدد صحیح کردنش بی‌صدا `.5` را دور می‌ریزد. اگر تبدیل اصلاً نمی‌خواهید، `ConfigDict(strict=True)` مدل را strict می‌کند و آن‌وقت حتی `"5"` هم با `int_type` رد می‌شود. همین تبدیل lax برای JSON هم هست: `P.model_validate_json('{"n": "5"}')` هم `n=5` داد.

حالت lax برای HTTP پیش‌فرض درستی است، چون query string و path parameter همیشه متن‌اند. اگر FastAPI آنجا strict بود، هیچ پارامتر عددی هرگز کار نمی‌کرد. برای داده‌ی داخلی که خودتان کنترل می‌کنید، strict ارزش فکر کردن دارد. دو خط آخر خروجی جهت برعکس را نشان می‌دهند: `model_dump()` مدل را به dict ساده و `model_dump_json()` به رشته‌ی JSON برمی‌گرداند.

## Depends: منطق مشترک به‌شکل پارامتر

بسیاری از endpointها آماده‌سازی یکسانی لازم دارند، مثلاً بررسی اینکه صدازننده کیست. FastAPI اجازه می‌دهد آن را یک بار به‌شکل تابع بنویسید و نتیجه‌اش را با `Depends` به‌شکل پارامتر بخواهید:

```python
def need_token(authorization: Annotated[str | None, Header()] = None):
    if authorization != "Bearer secret":
        raise HTTPException(401, "bad token")
    return "alice"

@app.get("/me")
def me(user: Annotated[str, Depends(need_token)]): ...
```

`need_token` سربرگ `Authorization` را می‌خواند (معنی `Header()` همین است). اگر غلط باشد `HTTPException` پرتاب می‌کند و کلاینت 401 می‌گیرد؛ وگرنه نام کاربر را برمی‌گرداند و FastAPI آن را به‌عنوان `user` به `me` می‌دهد. بدون header جواب `401 {"detail": "bad token"}` گرفتم و با `Bearer secret` جواب `200 {"user": "alice"}`.

به این می‌گویند {{< term "dependency-injection" "تزریق وابستگی" >}}: handler می‌گوید چه لازم دارد و فریم‌ورک آن را می‌رساند. از دو جهت مفید است. بررسی در بدنه‌ی یک handler فراموش نمی‌شود، چون بخشی از امضاست. و در تست می‌شود وابستگی را با یک نسخه‌ی جعلی عوض کرد. توکن اینجا البته اسباب‌بازی است؛ احراز هویت واقعی در [session یا JWT](/fa/posts/sec-sessions-vs-jwt/) آمده.

## def، async def و background task

شاید دیده باشید که بعضی handlerها `def` هستند و بعضی `async def`. فرقی می‌کند؟ دو endpoint ساختم که نام thread اجرایشان را برمی‌گردانند و روی یک سرور واقعی uvicorn صدایشان زدم (نه با `TestClient`، چون test client handlerهای async را روی thread خودش اجرا می‌کند و جواب گمراه‌کننده می‌شد):

```text
/sync  -> {"thread":"AnyIO worker thread"}
/async -> {"thread":"MainThread"}
```

handler معمولی `def` در یک {{< term "thread-pool" "thread pool" >}} اجرا می‌شود، پس کندبودنش سرور را نمی‌ایستاند. handler با `async def` مستقیم روی event loop و روی thread اصلی اجرا می‌شود. این با قاعده‌ای همراه است که بخش بعد نشان می‌دهد.

FastAPI می‌تواند کاری را بعد از ارسال پاسخ هم اجرا کند، با `BackgroundTasks`. handler دمو یک job را در صف گذاشت و یک خط چاپ کرد، و لاگ سرور اول `handler returning` و بعد `background ran job1` را نشان داد. کلاینت تا آن لحظه جوابش را گرفته بود.

## تله: بلاک کردن داخل async def

handler با `async def` روی event loop اجرا می‌شود، پس اگر بلاک شود همه‌چیز بلاک می‌شود، همان‌طور که در [asyncio در Python](/fa/posts/py-asyncio/) دیدیم. برای آزمایشش دو endpoint نوشتم که هر دو `time.sleep(0.3)` را صدا می‌زنند. یکی `def` است و دیگری `async def`. کلاینت درخواستی به endpoint کند می‌فرستد، ۰٫۱ ثانیه صبر می‌کند، `/ping` می‌فرستد و چاپ می‌کند کدام درخواست زودتر تمام شد. سه بار اجرا برای هرکدام همین نتیجه را داد:

```text
/slow-sync       ['ping', 'slow']
/slow-async-bad  ['slow', 'ping']
```

با `def`، خواب در یک worker thread اتفاق می‌افتد و `ping` وقتی جواب داده می‌شود که درخواست کند هنوز خواب است. با `async def`، خواب خود event loop را بلاک می‌کند و `ping` باید صبر کند تا handler کند تمام شود. راه‌حل همان قبلی است: `def` معمولی بنویسید، تماس بلاک‌کننده را به `asyncio.to_thread` بدهید یا از کتابخانه‌ی async استفاده کنید.

یک تله‌ی دیگر هم هست، درباره‌ی مقدار پیش‌فرض. در تابع معمولی، `def f(x, acc=[])` لیست را یک بار می‌سازد و بین فراخوانی‌ها به اشتراک می‌گذارد: فراخوانی دوم `[1, 2]` داد. Pydantic این کار را نمی‌کند. فیلد مدل با پیش‌فرض `[]` برای هر مدل لیست جداگانه‌ی خودش را می‌گیرد، و در دمو بعد از اینکه به مدل اول چیزی اضافه کردم، `tags` مدل دوم `[]` ماند.

## مستندات خودکار

چون FastAPI هر پارامتر و مدل را می‌شناسد، می‌تواند کل API را توصیف کند. `/openapi.json` از روی کد ساخته می‌شود. در دمو مقدار `openapi` برابر `3.1.0` بود، مسیرها شامل `/items/{item_id}` بودند و توصیف آن پارامتر این بود:

```text
{"name": "item_id", "in": "path", "required": true, "schema": {"type": "integer", "title": "Item Id"}}
```

schema ‌ی `UserOut` فقط `addresses`، `age`، `email` و `name` را دارد و password ندارد، همان‌طور که باید. FastAPI یک صفحه‌ی تعاملی هم در `/docs` از همین JSON می‌سازد. اینجا مرورگر نشان نمی‌دهم و آن را باز نکردم. اینکه چرا قراردادی که ماشین بتواند بخواند به درد می‌خورد را در [OpenAPI و قرارداد API](/fa/posts/eng-openapi-contracts/) ببینید.

## شروع، خاموش شدن و SIGTERM

یک API معمولاً باید موقع شروع کاری بکند (مثلاً اتصالی باز کند) و موقع توقف کار دیگری (آن را ببندد). `lifespan` در FastAPI برای این است، یک context manager ناهمگام: کد قبل از `yield` موقع شروع و کد بعد از آن موقع خاموش شدن اجرا می‌شود. دمو فقط `startup` و `shutdown` چاپ می‌کند.

به process در حال اجرای uvicorn سیگنال {{< term "sigterm" "SIGTERM" >}} فرستادم ([process و سیگنال](/fa/posts/linux-processes-signals/)). لاگ `startup` و بعد `shutdown` بود و shell کد خروج 143 را گزارش کرد، یعنی ۱۲۸ به‌اضافه‌ی ۱۵ که شماره‌ی SIGTERM است. خط `shutdown` ثابت می‌کند کد بعد از `yield` اجرا شد، پس این یک {{< term "graceful-shutdown" "graceful shutdown" >}} بود. بعد از آن `ps` هیچ process ‌ی uvicorn نشان نداد.

## در مقایسه با Zod، Go و net/http

Zod در زمان اجرا با schemaای اعتبارسنجی می‌کند که جدا از نوع‌هایتان می‌نویسید؛ Pydantic اعتبارسنجی را از annotationهای نوع روی کلاس می‌سازد. Go اعتبارسنجی فیلدهای struct را در خودش ندارد: یا دستی چک می‌کنید یا کتابخانه اضافه می‌کنید. با `net/http` ([API با net/http](/fa/posts/go-http-api-stdlib/)) decode و اعتبارسنجی همه با خودتان است، ولی FastAPI هر دو را از امضای تابع انجام می‌دهد.

## پیش از استفاده‌ی جدی

- مدل ورودی و خروجی را جدا نگه دارید. اگر یک مدل برای هر دو باشد، دیر یا زود فیلد محرمانه‌ای مثل `password` در یک پاسخ نشت می‌کند.
- `def` یا `async def` را آگاهانه انتخاب کنید. اگر handler کتابخانه‌ی بلاک‌کننده صدا می‌زند، `def` انتخاب امن است؛ `async def` داخلش کتابخانه‌ی async می‌خواهد.
- نسخه‌ها را pin کنید. FastAPI و Pydantic سریع تغییر می‌کنند و پیام خطاها یا مقدارهای پیش‌فرض بین نسخه‌ها فرق می‌کند.
- بررسی توکن اسباب‌بازی این پست را در کد واقعی کپی نکنید.

## تمرین

یک `PATCH /users/{id}` با مدلی که همه‌ی فیلدهایش اختیاری‌اند، یک `Depends` که کاربر را بارگذاری می‌کند یا 404 می‌دهد، و یک تست با `TestClient` اضافه کنید.

## قدم بعدی

قدم بعد: «SQLAlchemy و Postgres»، چون این API هنوز پایگاه داده‌ای ندارد که کاربرانش را در آن نگه دارد.
