+++
date = '2027-02-23T10:00:00+03:30'
draft = false
title = 'خطا و context manager در Python'
description = 'خطا و context manager در Python: try/except/finally، chaining، ExceptionGroup، with، contextlib و ExitStack، همه روی Python 3.14 اجرا شده.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "exceptions", "context-managers"]
cover = { image = "/images/covers/py-errors-context-managers.fa.png", alt = "خطا و context manager در Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-classes-dataclasses/) کلاس و dataclass ساختیم. حالا می‌پردازیم به این‌که وقتی چیزی خراب می‌شود چه اتفاقی می‌افتد و چطور پاک‌سازی را تضمین کنیم. Python خطا را با exception گزارش می‌کند، برخلاف [خطا به‌عنوان مقدار در Go](/fa/posts/go-functions-defer-errors/): خبری از `if err != nil` نیست و exception در پشته‌ی فراخوانی بالا می‌رود تا کسی آن را بگیرد. Node برای کد synchronous همین مدل را دارد و بخش async را در [خطا و unhandled rejection در Node.js](/fa/posts/node-errors-unhandled-rejections/) دیده‌ایم.

> همه‌چیز با Python 3.14.0 روی macOS اجرا شده است (`python3 --version`). دموها سه اسکریپت محلی هستند و مسیر home حذف شده است.

## try، except، else و finally

```python
def f(x):
    try:
        print("try"); r = 10 / x
    except ZeroDivisionError as e:
        print("except:", e); return "from except"
    else:
        print("else"); return "from else"
    finally:
        print("finally")
```

```text
f(2): try, else, finally  -> from else
f(0): try, except: division by zero, finally  -> from except
```

`else` فقط وقتی اجرا می‌شود که چیزی raise نشده باشد و `finally` همیشه اجرا می‌شود، حتی بعد از `return`. اگر داخل `finally` هم `return` بگذارید، `return` قبلی را از بین می‌برد؛ برای همین Python 3.14 پیغام `SyntaxWarning: 'return' in a 'finally' block` را چاپ می‌کند. این کار را نکنید.

## سلسله‌مراتب و گرفتن دقیق

`FileNotFoundError.__mro__` این را چاپ کرد: `FileNotFoundError, OSError, Exception, BaseException, object`. باریک‌ترین کلاسی را بگیرید که می‌توانید مدیریت کنید؛ `except Exception` فقط در مرز برنامه و آخرین راه است و `except` خالی حتی `KeyboardInterrupt` را هم می‌گیرد. `open("/no/such/file")` خطایی داد که `errno` آن `2` و `filename` آن همان مسیر بود.

دو نوع می‌توانند یک handler مشترک داشته باشند. `except (ValueError, TypeError):` همیشه کار می‌کرد و در 3.14 شکل بدون پرانتز `except ValueError, TypeError:` هم بدون مشکل اجرا شد. نسخه‌های قدیمی‌تر را امتحان نکردم؛ تا جایی که می‌دانم قبل از 3.14 این شکل SyntaxError است.

## Chaining

اگر هنگام مدیریت یک خطا خطای دیگری raise کنید، Python اولی را نگه می‌دارد. {{< term "exception-chaining" "Chaining" >}} دو نوع دارد:

```python
raise RuntimeError("config broken") from e   # صریح: __cause__
raise ValueError("oops")                     # داخل except: __context__ ضمنی
```

```text
KeyError('k') True True       # __cause__، context همان cause، suppress_context
None ZeroDivisionError('division by zero') False
```

خروجی `traceback.print_exc()` در حالت ضمنی هر دو traceback را با جمله‌ی `During handling of the above exception, another exception occurred:` به هم وصل کرد. با `from e` جمله‌ی واسط فرق می‌کند (آن را چاپ نکردم؛ مستندات آن را «علت مستقیم» توصیف می‌کنند). وقتی خطای سطح‌پایین را به خطای خودتان ترجمه می‌کنید از `from` استفاده کنید.

## exception سفارشی و note

```python
class AppError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg); self.code = code
```

`AppError("bad", 42)` را raise کردم، با `e.add_note("while loading user 7")` یادداشت اضافه کردم، با `raise` خالی دوباره raise کردم و handler بیرونی این را دید: `42 ['while loading user 7']`. note در traceback هم زیر پیام نشان داده می‌شود.

## ExceptionGroup و except*

یک {{< term "exception-group" "ExceptionGroup" >}} چند خطا را یک‌جا حمل می‌کند، مثلاً از یک batch. نتیجه‌ی چهار job را جمع کردم (دو `ValueError` و یک `TypeError`) و با هم raise کردم:

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

برخلاف `except` معمولی، هر بند `except*` که بخشی از group را بپوشاند روی همان بخش اجرا می‌شود.

## logging و traceback

`logging.exception("lookup failed")` داخل `except` این را لاگ کرد: `ERROR lookup failed` و بعد traceback کامل. به‌جای `print(e)` از آن استفاده کنید، چون `print` پشته را از دست می‌دهد.

## دستور with

یک {{< term "context-manager" "context manager" >}} آماده‌سازی و پاک‌سازی را تضمین می‌کند. `with m as x: body` اول `m.__enter__()` را صدا می‌زند، بعد بدنه و در پایان `m.__exit__(type, value, tb)` را، شبیه یک `finally`. نمونه‌ی دست‌نویس:

```python
class Res:
    def __enter__(self): print("enter", self.name); return self
    def __exit__(self, et, ev, tb):
        self.closed = True; print("exit", self.name, et.__name__ if et else None)
        return self.swallow
```

```text
بدنه‌ی عادی:   enter a, body, exit a None        (closed True)
ValueError:    enter b, exit b ValueError        -> exception عبور کرد
swallow=True:  enter c, exit c ValueError        -> "after swallow" چاپ شد
```

اگر `__exit__` مقدار true برگرداند exception بلعیده می‌شود. تقریباً همیشه `None` برگردانید.

## contextlib

راه ساده، یک {{< term "generator" "generator" >}} با `@contextlib.contextmanager` است؛ پاک‌سازی را در `try/finally` دور `yield` بگذارید:

```python
@contextlib.contextmanager
def opened(name):
    print("setup", name)
    try: yield name
    finally: print("cleanup", name)
```

raise داخل `with` این را چاپ کرد: `setup x`، `cleanup x` و بعد handler من اجرا شد. چیزهای دیگری که اجرا کردم: `contextlib.suppress(FileNotFoundError)` دور `os.remove` روی فایل ناموجود (بی‌صدا ادامه داد) و `contextlib.closing(Conn())` که `close()` را صدا زد (`conn closed`).

برای تعداد متغیر منبع از `ExitStack` استفاده کنید. `r1` و `r2` و `r3` را در یک list comprehension وارد کردم و خروجی‌ها برعکس چاپ شد: `exit r3`، `exit r2`، `exit r1`. با یک فایل واقعی هم امتحان کردم: بعد از بلوک `f.closed` برابر `True` بود، حتی وقتی بدنه `OSError` داد.

## assert اعتبارسنجی نیست

`assert n > 0, "n must be positive"` در حالت عادی `AssertionError` داد. با `python3 -O` مقدار `__debug__` برابر `False` شد و همان `pay(-1)` بی‌صدا `-1` را برگرداند. پس `assert` را فقط برای invariantهای داخلی بگذارید و ورودی را با `raise ValueError` اعتبارسنجی کنید.

## چند نکته‌ی مهم

- exception را باریک بگیرید و هرگز با `except: pass` خفه‌اش نکنید.
- با `raise X from e` علت را نگه دارید و با `raise` خالی بدون تغییر دوباره raise کنید.
- هرگز داخل `finally` از `return` استفاده نکنید.
- برگرداندن True از `__exit__` خطا را پنهان می‌کند.
- `assert` با `-O` حذف می‌شود.

## تمرین

1. یک `@contextmanager` به اسم `timer` بنویسید که حتی اگر بدنه raise کند زمان گذشته را چاپ کند.
2. با یک `ExitStack` دو فایل را باز کنید و ثابت کنید بعد از خطا هر دو بسته شده‌اند.
3. یک `ExceptionGroup` با سه خطا raise کنید و دو نوع را با `except*` مدیریت کنید.

## قدم بعدی

مقاله‌ی بعدی «type hint و mypy» است.
