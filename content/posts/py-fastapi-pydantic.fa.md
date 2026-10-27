+++
date = '2027-04-22T10:00:00+03:30'
draft = false
title = 'ساخت API با FastAPI و Pydantic'
description = 'FastAPI و Pydantic نسخه‌ی ۲: اعتبارسنجی پارامتر و خطای 422، مدل درخواست، response_model، Depends، handler همگام و ناهمگام، lifespan و SIGTERM.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "fastapi", "pydantic", "api", "validation"]
cover = { image = "/images/covers/py-fastapi-pydantic.fa.png", alt = "ساخت API با FastAPI و Pydantic", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-asyncio/) event loop را یاد گرفتیم؛ حالا handler‌های `async def` روی آن اجرا می‌شوند. FastAPI روی {{< term "pydantic" "Pydantic" >}} ساخته شده و {{< term "type-hint" "type hint" >}}‌های شما را ([type hint و mypy](/fa/posts/py-type-hints-mypy/)) می‌خواند تا ورودی را اعتبارسنجی کند، خروجی را شکل بدهد و مستندات بسازد. اگر Zod را می‌شناسید ([اعتبارسنجی ورودی با Zod](/fa/posts/node-validation-zod/)) مدل ذهنی آشناست.

> Python 3.14.0، fastapi 0.162.0، uvicorn 0.54.0، httpx 0.28.1، Pydantic 2.14.1 (یعنی v2)، email-validator 2.3.0، در یک venv موقت با `uv`. سرور روی `127.0.0.1` و port تصادفی. اسکریپت‌های دمو نمونه‌های محلی‌اند. ترتیب و تعداد منتشر می‌کنم، نه زمان.

## پارامترها و 422

```python
@app.get("/items/{item_id}")
def item(item_id: int, limit: int = 10):
    return {"item_id": item_id, "limit": limit}
```

با `TestClient`، آدرس `/items/5?limit=3` پاسخ `200 {"item_id": 5, "limit": 3}` می‌دهد. `/items/abc` این را می‌دهد:

```text
422 {"detail": [{"type": "int_parsing", "loc": ["path", "item_id"], "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "abc"}]}
```

هر خطا `loc` (کجا)، `msg` و `type` دارد. `?limit=x` همین شکل را با `loc: ["query", "limit"]` می‌دهد. تابع اصلاً اجرا نشد.

## مدل درخواست و response_model

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

`UserOut` فیلد `password` ندارد. ارسال یک body معتبر (با نام `" Ann "`) پاسخ 201 با `{"name": "Ann", "age": 30, "email": "a@example.com", "addresses": [{"city": "Oslo", "zip": "0150"}]}` داد: بدون password و با لیست تودرتو. body نامعتبر همه‌ی خطاها را یکجا گزارش می‌کند:

```text
string_too_long   ["body","name"]   ctx: {"max_length": 20}
greater_than      ["body","age"]    ctx: {"gt": 0}
value_error       ["body","email"]  An email address must have an @-sign.
```

یک `field_validator` نام را trim می‌کند و نام خالی را رد می‌کند: `"  "` پیام `Value error, name must not be blank` داد.

## خود Pydantic

```text
P.model_validate({"n": "5"})   -> P(n=5)
.model_dump() / model_dump_json() -> {'n': 5} / {"n":7}
lax  {'n': 'five'} -> int_parsing
lax  {'n': 5.5}    -> int_from_float
strict '5'         -> int_type | Input should be a valid integer
```

به‌طور پیش‌فرض Pydantic حالت lax دارد: رشته‌ی `"5"` به 5 تبدیل می‌شود ولی `5.5` رد می‌شود. با `ConfigDict(strict=True)` رشته هم رد می‌شود. توجه کنید که query string در HTTP همیشه متن است و برای همین FastAPI آنجا به حالت lax نیاز دارد.

## Depends

```python
def need_token(authorization: Annotated[str | None, Header()] = None):
    if authorization != "Bearer secret":
        raise HTTPException(401, "bad token")
    return "alice"

@app.get("/me")
def me(user: Annotated[str, Depends(need_token)]): ...
```

بدون header: `401 {"detail": "bad token"}`. با `Bearer secret`: `200 {"user": "alice"}`. این {{< term "dependency-injection" "تزریق وابستگی" >}} است: در تست می‌توان وابستگی را عوض کرد و بررسی در بدنه‌ی handler فراموش نمی‌شود. توکن اینجا اسباب‌بازی است؛ احراز هویت واقعی در [session یا JWT](/fa/posts/sec-sessions-vs-jwt/) آمده.

## sync، async و background task

روی یک سرور واقعی uvicorn نام thread را از هر دو نوع handler برگرداندم:

```text
/sync  -> {"thread":"AnyIO worker thread"}
/async -> {"thread":"MainThread"}
```

`def` معمولی در یک {{< term "thread-pool" "thread pool" >}} اجرا می‌شود؛ `async def` خودِ event loop. کار `BackgroundTasks` بعد از ارسال پاسخ اجرا می‌شود: لاگ اول `handler returning` و بعد `background ran job1` را نشان داد.

## تله: بلاک کردن داخل async def

دو endpoint با `time.sleep` به‌مدت ۰٫۳ ثانیه می‌خوابند، یکی `def` و یکی `async def`. درخواست کند را شروع کردم، ۰٫۱ ثانیه بعد `/ping` فرستادم و ترتیب پایان را چاپ کردم. هرکدام سه بار:

```text
/slow-sync       ['ping', 'slow']
/slow-async-bad  ['slow', 'ping']
```

نسخه‌ی `async def` حلقه را فریز کرد و ping منتظر ماند. همان درس [asyncio](/fa/posts/py-asyncio/): از `def`، `to_thread` یا کتابخانه‌ی async استفاده کنید.

تله‌ی دیگر: `def f(x, acc=[])` لیست را بین فراخوانی‌ها به اشتراک می‌گذارد (فراخوانی دوم `[1, 2]` داد) ولی مدل Pydantic مقدار پیش‌فرض را کپی می‌کند: `tags` مدل دوم `[]` ماند.

## OpenAPI

`/openapi.json` از روی کد ساخته می‌شود: مقدار `openapi` برابر `3.1.0` بود، مسیرها شامل `/items/{item_id}` بودند و پارامتر این بود: `{"name": "item_id", "in": "path", "required": true, "schema": {"type": "integer", "title": "Item Id"}}`. schema ‌ی `UserOut` فقط `addresses, age, email, name` دارد و password ندارد. `/docs` یک UI تعاملی از همین می‌سازد؛ اینجا مرورگر نشان نمی‌دهم و آن را باز نکردم. ببینید [OpenAPI و قرارداد API](/fa/posts/eng-openapi-contracts/).

## lifespan و خاموش شدن

یک context manager ناهمگام به نام `lifespan` قبل از `yield` عبارت `startup` و بعد از آن `shutdown` را چاپ می‌کند. به uvicorn سیگنال {{< term "sigterm" "SIGTERM" >}} فرستادم ([process و سیگنال](/fa/posts/linux-processes-signals/)): لاگ `startup` و `shutdown` بود و shell کد خروج 143 را گزارش کرد (۱۲۸ + ۱۵؛ uvicorn سیگنال را دوباره پرتاب می‌کند). این یک {{< term "graceful-shutdown" "graceful shutdown" >}} است؛ بعدش `ps` هیچ process ‌ی uvicorn نشان نداد.

## در مقایسه با Zod، Go و net/http

Zod در زمان اجرا از schema ‌ای که جدا می‌نویسید اعتبارسنجی می‌کند؛ Pydantic اعتبارسنجی را از annotation‌های نوع روی کلاس می‌سازد. Go اعتبارسنجی struct در خودش ندارد: فیلدها را دستی چک می‌کنید یا کتابخانه اضافه می‌کنید. با `net/http` ([API با net/http](/fa/posts/go-http-api-stdlib/)) decode و اعتبارسنجی با خودتان است؛ FastAPI هر دو را از signature انجام می‌دهد.

## چند نکته‌ی مهم

- مدل ورودی و خروجی را جدا نگه دارید وگرنه فیلد محرمانه نشت می‌کند.
- `def` یا `async def` را آگاهانه انتخاب کنید.
- نسخه‌ها را pin کنید؛ FastAPI و Pydantic سریع تغییر می‌کنند.
- بررسی توکن اسباب‌بازی را کپی نکنید.

## تمرین

یک `PATCH /users/{id}` با مدل فیلدهای اختیاری، یک `Depends` که کاربر را بارگذاری می‌کند یا 404 می‌دهد، و یک تست با `TestClient` اضافه کنید.

## قدم بعدی

مقاله‌ی بعد «SQLAlchemy و Postgres» است.
