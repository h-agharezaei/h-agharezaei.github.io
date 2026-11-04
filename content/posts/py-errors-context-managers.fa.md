+++
date = '2027-02-23T10:00:00+03:30'
draft = false
title = 'خطا و context manager در Python'
description = 'خطا و context manager در Python: try/except/finally، chaining، ExceptionGroup، with، contextlib و ExitStack، همه روی Python 3.14 اجرا شده.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "exceptions", "context-managers"]
cover = { image = "/images/covers/py-errors-context-managers.fa.png", alt = "خطا و context manager در Python", hiddenInSingle = true }
+++

تابعی را تصور کنید که یک فایل را باز می‌کند، شروع به خواندن می‌کند و وسط کار، چون یک خط داده‌ی خراب دارد، شکست می‌خورد. آیا فایل بسته می‌شود؟ در Go بلافاصله بعد از باز کردن می‌نویسید `defer f.Close()` و بستن انجام می‌شود، هر اتفاقی بیفتد. Python همین نیاز را دارد و در دو قدم جواب می‌دهد. اول، خطاها **exception** هستند: به‌صورت مقدار برگشتی نمی‌آیند، از پشته‌ی فراخوانی بالا می‌روند تا کسی بگیردشان. دوم، بلوک `with` تضمین می‌کند کد پاک‌سازی اجرا شود، بلوک هر طور تمام شود، حتی وقتی یک exception از میانش بگذرد.

این پست هر دو نیمه را پوشش می‌دهد: exceptionها در مسیر بالا رفتنشان چطور رفتار می‌کنند (و Python چه ابزارهایی برای خواندن و شکل‌دادن به آن‌ها می‌دهد)، و `with` و `contextlib` چطور پاک‌سازی را مطمئن می‌کنند. بعد از [کلاس و dataclass](/fa/posts/py-classes-dataclasses/) می‌آید، چون exceptionها کلاس‌اند و `with` روی دو متد بنا شده.

Python خطا را با exception گزارش می‌کند، برخلاف [خطا به‌عنوان مقدار در Go](/fa/posts/go-functions-defer-errors/): بعد از هر فراخوانی `if err != nil` وجود ندارد. Node برای کد synchronous همین مدل را دارد و سمت async را در [خطاها و unhandled rejection در Node.js](/fa/posts/node-errors-unhandled-rejections/) آورده‌ام.

> همه‌چیز با Python 3.14.0 روی macOS اجرا شده است (`python3 --version`). دموها سه اسکریپت محلی `flow.py`، `chain.py` و `cm.py` هستند. در tracebackهای زیر به‌جای مسیر واقعی `<demo>` نوشته‌ام، و چند بررسی اضافه که در یک فایل scratch اجرا کردم مشخص شده‌اند.

## try، except، else و finally

بلوک `try` کدی را اجرا می‌کند که ممکن است شکست بخورد. `except` یک خطای مشخص را می‌گیرد. دو بخش دیگر کمتر شناخته‌اند: `else` فقط وقتی اجرا می‌شود که چیزی پرتاب نشده باشد، و `finally` همیشه اجرا می‌شود. این تابع هر چهار را دارد و چاپ می‌کند کدام بخش اجرا شد:

```python
def f(x):
    try:
        print("try")
        r = 10 / x
    except ZeroDivisionError as e:
        print("except:", e)
        return "from except"
    else:
        print("else")
        return "from else"
    finally:
        print("finally")
print(f(2)); print(f(0))
```

```text
try
else
finally
from else
try
except: division by zero
finally
from except
```

خروجی را در دو نیمه بخوانید، یکی برای هر فراخوانی. `f(2)` درست کار می‌کند: `try` اجرا می‌شود، چیزی پرتاب نمی‌شود، پس `else` اجرا می‌شود و بعد `finally`. فقط بعد از آن مقدار برگشتی، یعنی `from else`، چاپ می‌شود. `f(0)` بر صفر تقسیم می‌کند: `try` شروع می‌شود، خطا مستقیم به `except` می‌پرد و `finally` هم قبل از اینکه تابع `from except` را برگرداند اجرا می‌شود.

نکته‌ی مهم این است که `finally` **حتی وقتی هر دو شاخه قبلاً `return` را اجرا کرده‌اند** اجرا می‌شود. برای همین جای درست پاک‌سازی است. یک لبه‌ی تیز هم دارد: `return` داخل `finally` جای return قبلی را می‌گیرد و هر exceptionی را بی‌صدا دور می‌اندازد. دمو چنین تابعی دارد و Python 3.14 هنگام کامپایل فایل درباره‌اش هشدار می‌دهد:

```text
flow.py:19: SyntaxWarning: 'return' in a 'finally' block
```

## سلسله‌مراتب و گرفتن دقیق

exceptionها یک سلسله‌مراتب کلاس می‌سازند. دمو آن را برای `FileNotFoundError` چاپ می‌کند:

```text
['FileNotFoundError', 'OSError', 'Exception', 'BaseException', 'object']
```

یک `FileNotFoundError` یک `OSError` است و آن یک `Exception`. `except` برای یک کلاس همه‌ی زیرکلاس‌هایش را هم می‌گیرد، پس **تنگ‌ترین** کلاسی را بگیرید که واقعاً می‌توانید مدیریتش کنید. `except Exception` آخرین چاره است و برای مرز بیرونی برنامه، و `except:` خالی بدتر است، چون حتی `KeyboardInterrupt` (Ctrl+C) را هم می‌گیرد. exceptionها داده هم حمل می‌کنند: برای `open("/no/such/file")` دمو خطایی گرفت که `errno` آن `2` و `filename` آن همان مسیر بود.

دو نوع را می‌شود با گذاشتن‌شان در یک tuple در یک handler گرفت: `except (ValueError, TypeError):` همه‌جا کار می‌کند و `int("x")` در دمو با آن به‌عنوان `ValueError` گرفته شد. روی 3.14 دمو `except ValueError, TypeError:` را هم بدون پرانتز اجرا کرد. تا جایی که می‌دانم (PEP 758) این شکل در 3.14 تازه است و قبل از آن خطای syntax است، ولی نسخه‌های قدیمی‌تر را آزمایش نکردم.

## زنجیره‌سازی

اگر وسط مدیریت یک exception، exception تازه‌ای پرتاب کنید، نمی‌خواهید اولی را گم کنید، چون اغلب علت واقعی است. Python آن را نگه می‌دارد و به این {{< term "exception-chaining" "زنجیره‌سازی exception" >}} می‌گویند. دو شکل دارد:

```python
raise RuntimeError("config broken") from e   # explicit: __cause__
raise ValueError("oops")                     # inside except: implicit __context__
```

دمو هر دو را گرفت و attributeهایشان را چاپ کرد:

```text
KeyError('k') True True
None ZeroDivisionError('division by zero') False
```

خط اول `from e` صریح است: `__cause__` همان `KeyError` اصلی است، `__context__` همان شیء است و `__suppress_context__` برابر `True` است. خط دوم حالت ضمنی است (یک `ValueError` که داخل بلوک `except ZeroDivisionError` پرتاب شد): `__cause__` ندارد، ولی `__context__` هنوز `ZeroDivisionError` را ثبت کرده. این دو شکل در traceback فرق دارند. این حالت ضمنی است که با `traceback.print_exc()` چاپ شد:

```text
Traceback (most recent call last):
  File "<demo>/chain.py", line 3, in <module>
    1/0
    ~^~
ZeroDivisionError: division by zero

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<demo>/chain.py", line 5, in <module>
    raise ValueError("oops")
ValueError: oops
```

جمله‌ی `During handling of the above exception, another exception occurred` می‌گوید خطای دوم هنگام مدیریت اولی رخ داده، شاید سهوی. در یک فایل scratch جداگانه حالت صریح را هم بررسی کردم و خط اتصالش فرق دارد: `The above exception was the direct cause of the following exception:`. پس وقتی عمداً یک خطای سطح پایین را به خطای خودتان ترجمه می‌کنید از `raise ... from e` استفاده کنید، تا خواننده‌ی traceback بداند این کار عمدی بوده.

## exceptionهای سفارشی و note

exception سفارشی شما فقط زیرکلاسی از `Exception` است و می‌تواند داده‌ی اضافه حمل کند:

```python
class AppError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code
try:
    try:
        raise AppError("bad", 42)
    except AppError as e:
        e.add_note("while loading user 7")
        raise
except AppError as e:
    print(e.code, e.__notes__)
```

```text
42 ['while loading user 7']
```

handler داخلی با `add_note()` یک note اضافه می‌کند و همان exception را با `raise` ساده دوباره پرتاب می‌کند (که traceback اصلی را نگه می‌دارد). handler بیرونی هم attribute `code` را می‌بیند و هم فهرست noteها را. noteها در traceback چاپ‌شده هم زیر پیام خطا می‌آیند، پس هر لایه می‌تواند بدون پیچیدن exception در یک exception تازه، زمینه («while loading user 7») اضافه کند.

## ExceptionGroup و except*

گاهی چند چیز با هم شکست می‌خورند، مثلاً در یک دسته کار. {{< term "exception-group" "ExceptionGroup" >}} چند خطا را با هم حمل می‌کند. دمو چهار کار را اجرا می‌کند، شکست‌ها را جمع می‌کند (دو `ValueError` و یک `TypeError`) و همه را به‌شکل یک گروه پرتاب می‌کند:

```python
try:
    raise ExceptionGroup("batch", errs)
except* ValueError as eg: print("values:", [str(x) for x in eg.exceptions])
except* TypeError as eg:  print("types:", [str(x) for x in eg.exceptions])
```

```text
values: ['v1', 'v3']
types: ['t2']
```

یک `except ValueError` ساده اینجا اصلاً تطبیق نمی‌کند، چون خود گروه یک `ValueError` نیست. با `except*`، Python داخل گروه را نگاه می‌کند و هر clause مطابق روی بخش مخصوص خودش اجرا می‌شود: clause مربوط به `ValueError` مقدارهای `v1` و `v3` را دید و clause مربوط به `TypeError` مقدار `t2` را.

## لاگ و traceback

وقتی خطایی را می‌گیرید معمولاً می‌خواهید ردی از آن بماند. `logging.exception("lookup failed")` که داخل بلوک `except` صدا زده شود، پیام و traceback کامل را لاگ می‌کند:

```text
ERROR lookup failed
Traceback (most recent call last):
  File "<demo>/chain.py", line 11, in <module>
    {}["k"]
    ~~^^^^^
KeyError: 'k'
```

از آن به‌جای `print(e)` استفاده کنید؛ `print(e)` فقط پیام را چاپ می‌کند (اینجا فقط `'k'`) و پشته را از دست می‌دهد.

## دستور with

برگردیم به مسئله‌ی اول. {{< term "context-manager" "context manager" >}} شیئی است که می‌داند چیزی را چطور آماده و چطور پاک کند. دستور `with` از آن استفاده می‌کند. نوشتن `with m as x: body` تقریباً یعنی: `m.__enter__()` را صدا بزن و نتیجه را به `x` وصل کن، بدنه را اجرا کن، و بعد `m.__exit__(type, value, traceback)` را صدا بزن، چه بدنه عادی تمام شده باشد چه exception انداخته باشد. وقتی بدنه موفق است این سه آرگومان همه `None` هستند؛ وقتی exception پرتاب شده، آن را توصیف می‌کنند.

یک manager کوچک نوشتم که هنگام ورود و خروج چاپ می‌کند تا ترتیب دیده شود:

```python
class Res:
    def __init__(self, name, swallow=False):
        self.name, self.swallow, self.closed = name, swallow, False
    def __enter__(self):
        print("enter", self.name); return self
    def __exit__(self, et, ev, tb):
        self.closed = True
        print("exit", self.name, et.__name__ if et else None)
        return self.swallow
```

سه اجرا از آن: یکی با بدنه‌ی عادی، یکی که بدنه `ValueError` می‌اندازد، و یکی که می‌اندازد ولی `swallow=True` است:

```text
enter a
body
exit a None
closed: True
enter b
exit b ValueError
propagated boom True
enter c
exit c ValueError
after swallow
```

- **`a`:** `enter`، بدنه، بعد `exit a None` (exception نبود، پس نوع `None` است). بعدش `closed` برابر `True` است.
- **`b`:** بدنه exception انداخت، ولی `__exit__` باز هم اجرا شد (`exit b ValueError`) و بعد exception راهش را ادامه داد. `except` بیرونی آن را گرفت و `closed` برابر `True` بود: پاک‌سازی انجام شد و خطا هم پنهان نشد.
- **`c`:** همان، ولی `__exit__` مقدار درست برگرداند، پس exception **بلعیده شد** و برنامه ادامه داد و `after swallow` را چاپ کرد. تقریباً همیشه می‌خواهید `None` (یا هیچ) برگردانید و بگذارید خطا بالا برود.

دمو معادل دستی را هم نوشت: یک فراخوانی `__enter__` و بعد `try: ... finally: m.__exit__(None, None, None)` (`enter d` و `exit d None` چاپ شد). ایده همین است: `with` یک `try/finally` است که نوشتنش را نمی‌توانید فراموش کنید.

## contextlib

نوشتن کلاس با دو متد برای موردهای کوچک سنگین است. راه آسان یک {{< term "generator" "generator" >}} است که با `@contextlib.contextmanager` تزیین شده: کد قبل از `yield` آماده‌سازی است، کد بعد از آن پاک‌سازی، و `try/finally` دور `yield` مطمئن می‌کند وقتی بدنه خطا بیندازد پاک‌سازی اجرا شود:

```python
@contextlib.contextmanager
def opened(name):
    print("setup", name)
    try: yield name
    finally: print("cleanup", name)
try:
    with opened("x") as n: raise RuntimeError("fail")
except RuntimeError: print("caught after cleanup")
```

```text
setup x
cleanup x
caught after cleanup
```

خطا داخل `with` پرتاب شد، پاک‌سازی باز هم چاپ شد و بعد از آن handler خودمان اجرا شد. ابزارهای دیگر دمو: `contextlib.suppress(FileNotFoundError)` دور `os.remove` برای فایلی که وجود ندارد (بی‌صدا ادامه داد و دمو `suppressed` چاپ کرد)، و `contextlib.closing(Conn())` که برای شیئی که `__exit__` ندارد `close()` را صدا می‌زند (`using conn` و بعد `conn closed` چاپ شد).

برای تعداد متغیری از منبع‌ها از `ExitStack` استفاده کنید. در دمو `r1` و `r2` و `r3` را در یک list comprehension وارد کردم و خروج‌ها برعکس اجرا شدند:

```text
enter r1
enter r2
enter r3
body 3
exit r3 None
exit r2 None
exit r1 None
```

آخرین‌ورودی، اولین‌خروجی، که وقتی منبع بعدی ممکن است به قبلی وابسته باشد همان چیزی است که می‌خواهید. و در نهایت یک فایل واقعی: `f.closed` بعد از بلوک `with` برابر `True` بود، و وقتی بدنه `OSError` انداخت هم `True` بود.

## assert اعتبارسنجی نیست

`assert n > 0, "n must be positive"` وقتی شرط نادرست باشد `AssertionError` می‌اندازد، و دمو در اجرای عادی `assert: n must be positive` را چاپ کرد (`__debug__` برابر `True` بود). ولی Python را می‌شود با `-O` اجرا کرد که دستورهای `assert` را حذف می‌کند. در یک فایل scratch بررسی کردم: زیر `python3 -O` مقدار `__debug__` برابر `False` بود و `pay(-1)` بدون هیچ خطایی `-1` برگرداند. پس `assert` را فقط برای بررسی‌های داخلی که هرگز نباید شکست بخورند به کار ببرید و ورودی واقعی را با `raise ValueError(...)` اعتبارسنجی کنید.

## عادت‌های بد در مدیریت خطا

- **`except: pass` خالی.** همه‌ی خطاها را پنهان می‌کند، از جمله باگ‌ها و Ctrl+C. exceptionهای تنگ بگیرید و کار مفیدی با آن‌ها بکنید.
- **از دست دادن علت.** وقتی خطایی را ترجمه می‌کنید از `raise X from e` برای نگه‌داشتن علت استفاده کنید، و از `raise` ساده برای پرتاب مجدد بدون تغییر.
- **`return` در `finally`.** return‌های قبلی را لغو می‌کند و exceptionها را می‌بلعد. Python 3.14 حتی هشدار هم می‌دهد.
- **برگرداندن مقدار درست از `__exit__`.** خطا را از فراخواننده پنهان می‌کند، آن هم بی‌صدا.
- **تکیه بر `assert` برای اعتبارسنجی.** با `-O` ناپدید می‌شود.

## تمرین

1. یک `@contextmanager` به اسم `timer` بنویسید که حتی وقتی بدنه خطا بیندازد زمان سپری‌شده را چاپ کند.
2. دو فایل را با یک `ExitStack` باز کنید و ثابت کنید بعد از خطا هر دو بسته شده‌اند.
3. یک `ExceptionGroup` از سه خطا پرتاب کنید و دو نوع را با `except*` مدیریت کنید.

## قدم بعدی

پست بعدی «type hint و mypy» است. بخشی از این خطاها را پیش از اجرای برنامه پیدا می‌کند، و این نیمه‌ی دیگر ماجراست وقتی exceptionها فقط موقع اجرا پیدا می‌شوند.
