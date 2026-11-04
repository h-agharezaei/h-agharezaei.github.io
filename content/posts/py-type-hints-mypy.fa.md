+++
date = '2027-03-11T10:00:00+03:30'
draft = false
title = 'type hint و mypy'
description = 'type hint و mypy در Python: list[int]، X | None، TypedDict، Protocol، generic با PEP 695، خطاهای واقعی mypy، --strict، cast و type: ignore روی 3.14.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "type-hints", "mypy", "typing"]
cover = { image = "/images/covers/py-type-hints-mypy.fa.png", alt = "type hint و mypy", hiddenInSingle = true }
+++

تابعی را تصور کنید که قیمت‌های یک سفارش را جمع می‌زند. در همه‌ی تست‌هایی که نوشته‌اید قیمت‌ها عدد هستند و تابع درست کار می‌کند. بعد یک روز از یک فایل JSON قیمتی به شکل رشته‌ی `"12.5"` می‌رسد و تابع با `TypeError` می‌ترکد، آن هم فقط در همان مسیری از کد که هیچ‌کس امتحانش نکرده بود. Python تا خطی واقعاً اجرا نشود به نوع‌ها نگاه نمی‌کند، برای همین این جور اشتباه‌ها ساکت منتظر بدترین لحظه می‌مانند.

type hint جواب Python به این مشکل است. {{< term "type-hint" "type hint" >}} یادداشتی است که کنار یک پارامتر یا مقدار برگشتی می‌نویسید و می‌گوید نوعش چه باید باشد: `def total(prices: list[float]) -> float`. ساده‌ترین راه برای فهمیدنش این است: **type hint مستنداتی است که به شکلی نوشته شده که یک ابزار بتواند آن را بررسی کند**. آن ابزار یک {{< term "type-checker" "type checker" >}} است و رایج‌ترینش mypy است. mypy کد شما را بدون اجرا می‌خواند و می‌گوید کجا hintها و کد با هم نمی‌خوانند. خود مفسر Python hintها را کاملاً نادیده می‌گیرد.

اگر از [نوع‌های ایستای Go](/fa/posts/go-types-control-flow/) می‌آیید، تفاوت بزرگ همین است: در Go کامپایلر برنامه‌ای را که خطای نوع دارد نمی‌سازد. در Python بررسی نوع یک مرحله‌ی جدا است که خودتان اضافه‌اش می‌کنید. پست قبلی، [خطا و context manager در Python](/fa/posts/py-errors-context-managers/)، درباره‌ی خطاهایی بود که وقت اجرا بالا می‌آیند. hint و mypy گروه بزرگی از آن‌ها را زودتر، پیش از اجرای برنامه، پیدا می‌کنند. [dataclassها](/fa/posts/py-classes-dataclasses/) را هم قبلاً دیدیم و با hint خیلی خوب جور هستند.

> بخش‌های Python این پست را با Python 3.14.0 اجرا کرده‌ام (`python3 --version`). خروجی‌های mypy در ادامه (فهرست خطاها و اجرای `--strict`) از اجرای اصلی همین پست هستند، با mypy 2.4.0 در یک virtual environment موقت که بعدش پاک کردم. موقع بازنویسی این پست نتوانستم دوباره mypy نصب کنم، پس آن خروجی‌ها را دوباره اجرا نکرده‌ام. دمو چهار فایل کوچک محلی است.

## مفسر hint را بررسی نمی‌کند

از بخش غافلگیرکننده شروع کنم. این تابع می‌گوید یک `int` می‌گیرد:

```python
def f(a: int) -> int:
    return a * 2
```

صدا زدن `f('ab')` خطا نمی‌دهد و `abab` چاپ می‌کند، چون `'ab' * 2` در Python کاملاً معتبر است. hintها فقط روی تابع ذخیره می‌شوند و کار دیگری نمی‌کنند: `f.__annotations__` برابر `{'a': <class 'int'>, 'return': <class 'int'>}` است.

گاهی هم فراخوانی اشتباه شکست می‌خورد، ولی خطا از خود کد می‌آید نه از hint. این تابع و یک فراخوانی از همان نوع را ببینید:

```python
def total_of(xs: list[int]) -> int:
    return sum(xs)
print(total_of(['1', '2']))
```

```text
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

این خطا از `sum` آمد، وقتی خواست `'1'` را به مقدار شروعش یعنی `0` اضافه کند. hint یعنی `list[int]` هیچ نقشی نداشت. پس قاعده‌ی اول این است: **hintها وقت اجرا هیچ کاری نمی‌کنند**. اگر می‌خواهید از شما محافظت کنند، کسی باید آن‌ها را بخواند، و آن کس checkerی است که خودتان یا CI اجرا می‌کنید.

## یک ماژول با hint

این‌ها hintهایی هستند که بیشتر از همه به کارتان می‌آیند. فایل دمو `good.py` است:

```python
class User(TypedDict):
    name: str
    age: int

@dataclass
class Order:
    id: int
    total: float

def count_words(words: list[str]) -> dict[str, int]: ...
def find_user(users: dict[str, User], name: str) -> User | None:
    return users.get(name)

def first[T](xs: list[T]) -> T:      # PEP 695 syntax
    return xs[0]

class Closer(Protocol):
    def close(self) -> None: ...
```

یکی‌یکی مرورشان کنیم:

- `list[str]` و `dict[str, int]` می‌گویند داخل یک ظرف چه چیزی است: فهرستی از رشته‌ها، دیکشنری‌ای از رشته به عدد صحیح. با همان نام‌های ساده‌ی داخلی نوشته می‌شوند.
- `User | None` یعنی «یا یک `User` یا `None`». `dict.get` وقتی کلید نباشد `None` برمی‌گرداند، پس کد صادق باید این را در نوع برگشتی بگوید.
- `TypedDict` دیکشنری‌ای را توصیف می‌کند که کلیدهایش معلوم است، اینجا `name` و `age`. وقت اجرا همچنان یک `dict` معمولی است.
- `first[T]` یک تابع {{< term "generics" "generic" >}} است: برای فهرستی از هر چیزی کار می‌کند و نوع نتیجه همان نوع عضوهای فهرست است. `first(["p", "q"])` یک `str` است و `first([1, 2])` یک `int`. این نوشتار `[T]` به Python 3.12 یا بالاتر نیاز دارد (از PEP 695 آمده) و جای `TypeVar` قدیمی را می‌گیرد.
- `Protocol` به‌جای نام، یک «شکل» را توصیف می‌کند. هر کلاسی که متد `close()` بدون آرگومان داشته باشد یک `Closer` حساب می‌شود، حتی اگر اسم `Closer` را هرگز نبرده باشد. این همان {{< term "structural-typing" "structural typing" >}} است، یعنی نسخه‌ی ایستای {{< term "duck-typing" "duck typing" >}}: «اگر `close()` دارد، می‌شود بستش».

فایل کامل یک کلاس `Conn` و یک تابع `shutdown(c: Closer)` هم دارد. اجرای `python3 -I good.py` این را چاپ کرد:

```text
6 {'a': 2, 'b': 1}
{'name': 'x', 'age': 3} p Order(id=1, total=9.5)
closed
```

و در اجرای اصلی، `mypy good.py` چاپ کرد `Success: no issues found in 1 source file`.

## mypy چه چیزی را پیدا می‌کند

فایل دوم، `bad.py`، عمداً چهار اشتباه دارد. خط‌هایی که مهم‌اند را با شماره‌ی خطشان می‌آورم:

```python
12  def sign(n: int) -> str:
13      if n > 0:
14          return "pos"
15      elif n < 0:
16          return "neg"        # no else: n == 0 returns nothing
...
23  class Bad:
24      def close(self, force: bool) -> None: ...
...
31  print(total_of(["1", "2"]))          # list of str, expected list of int
32  print(find({"a": 1}, "a").bit_length())   # find() may return None
33  shutdown(Bad())                      # Bad.close needs an argument
```

mypy این را گفت (اجرای اصلی):

```text
bad.py:12: error: Missing return statement  [return]
bad.py:31: error: List item 0 has incompatible type "str"; expected "int"  [list-item]
bad.py:31: error: List item 1 has incompatible type "str"; expected "int"  [list-item]
bad.py:32: error: Item "None" of "int | None" has no attribute "bit_length"  [union-attr]
bad.py:33: error: Argument 1 to "shutdown" has incompatible type "Bad"; expected "Closer"  [arg-type]
bad.py:33: note:     Expected:  def close(self) -> None
bad.py:33: note:     Got:       def close(self, force: bool) -> None
Found 5 errors in 1 file (checked 1 source file)
```

(هر note را در یک خط گذاشتم.) از بالا بخوانیم:

- خط ۱۲: `sign` قول می‌دهد یک `str` برگرداند، ولی وقتی `n` برابر `0` است هیچ شاخه‌ای چیزی برنمی‌گرداند. Python بی‌صدا `None` برمی‌گرداند.
- خط ۳۱، دو بار: فهرست دو رشته دارد و تابع عدد صحیح می‌خواهد. mypy هر عضو را جدا گزارش می‌کند.
- خط ۳۲: `find` مقدار `int | None` برمی‌گرداند و `None` متد `bit_length` ندارد. این از همان خانواده‌ی خطای dereference کردن nil در Go است: checker شما را مجبور می‌کند حالت «نبودن» را مدیریت کنید. راهش این است که نتیجه را در `r` بگیرید و پیش از استفاده بنویسید `if r is not None:`.
- خط ۳۳: `Bad` متد `close` دارد، ولی با یک آرگومان اجباری اضافه، پس با شکل `Closer` نمی‌خواند. دو خط `note` تفاوت را نشان می‌دهند.

هر چهار اشتباه فقط وقتی آن خط اجرا می‌شد خودشان را نشان می‌دادند. mypy همه را بدون اجرا پیدا کرد.

## در Python 3.14 annotationها تنبل ارزیابی می‌شوند

یک جزئیات عملی. قبلاً annotationها وقتی تابع تعریف می‌شد ارزیابی می‌شدند، پس hintی که اسم کلاسی را می‌برد که پایین‌تر در فایل تعریف شده خطا بود و مردم آن را داخل کوتیشن می‌نوشتند (`"Later"`) یا از `from __future__ import annotations` استفاده می‌کردند. در Python 3.14 annotationها تنبل ارزیابی می‌شوند، یعنی فقط وقتی لازم شوند. فایل دمو `lazy.py` یک کلاس را پیش از تعریفش به کار می‌برد، بدون کوتیشن و بدون future import:

```python
def f(x: Later) -> Later:
    return x

class Later: ...

print(f.__annotations__)
```

```text
{'x': <class '__main__.Later'>, 'return': <class '__main__.Later'>}
```

کار می‌کند و annotationها خود کلاس را نگه می‌دارند. future import هم هنوز کار می‌کند و در آن حالت رشته‌ی ساده نگه می‌دارد: در یک فایل scratch جدا با `from __future__ import annotations` نتیجه `{'x': 'Later', 'return': 'int'}` چاپ شد.

## --strict

mypy به‌طور پیش‌فرض با کد قدیمی و بدون annotation مدارا می‌کند: بدنه‌ی تابعی را که annotation ندارد رد می‌کند و از نبودن annotation شکایت نمی‌کند. فایل دمو `loose.py` یک `load(s: str)` بدون نوع برگشتی دارد، یک `risky(x)` کاملاً بدون نوع، و چند کامنت `type: ignore`. در اجرای اصلی، `mypy loose.py` ساده نوشت `Success`. با `--strict` چهار خطا پیدا شد:

```text
loose.py:5: error: Function is missing a return type annotation  [no-untyped-def]
loose.py:9: error: Function is missing a type annotation  [no-untyped-def]
loose.py:23: error: Unused "type: ignore" comment  [unused-ignore]
loose.py:24: error: Call to untyped function "risky" in typed context  [no-untyped-call]
```

دو مورد اول annotation‌های جاافتاده‌ی `load` و `risky` هستند. سومی یک کامنت ignore است که لازم نبود، و چهارمی فراخوانی تابعی بدون نوع از داخل کدی است که نوع دارد. روی `bad.py` در اجرای اصلی شمار خطاها همان ۵ ماند، چون آن توابع از قبل annotation داشتند. `--strict` بیشتر روی کدی اثر می‌گذارد که فقط بخشی از آن annotation دارد.

## راه‌های فرار، و استفاده‌ی امن از آن‌ها

گاهی checker چیزی را نمی‌تواند بداند، یا باید جلو بروید. Python سه راه برای گفتن «به من اعتماد کن» دارد و هر کدام بررسی را کمی خاموش می‌کنند:

- `Any` یعنی «هر نوعی». بررسی آن مقدار متوقف می‌شود. `json.loads` مقدار `Any` برمی‌گرداند، پس هر چیزی که از نتیجه‌اش بخوانید بررسی نمی‌شود.
- `typing.cast(dict[str, Any], json.loads(s))` به checker می‌گوید چه چیزی را باور کند. وقت اجرا هیچ کاری نمی‌کند و هیچ چیزی را بررسی نمی‌کند، پس cast غلط دروغی است که هیچ ابزاری نمی‌گیرد.
- `# type: ignore` همه‌ی خطاهای یک خط را ساکت می‌کند. در `loose.py` خط `f("a")  # type: ignore` یک فراخوانی واقعاً غلط را پنهان می‌کند. خط `y: int = 5  # type: ignore` بی‌فایده بود و حالت strict آن را با پیام `Unused "type: ignore" comment` گزارش کرد.

برای کنترل این‌ها، کد خطا را بنویسید (`# type: ignore[assignment]`) تا فقط همان خطایی را ساکت کنید که می‌خواستید، کنارش دلیلش را بنویسید، و `warn_unused_ignores` را روشن کنید (در `--strict` هست) تا ignoreهای دیگر لازم نشده پیدا شوند.

## چطور hint را وارد پروژه می‌کنم

- یادتان باشد hintها وقت اجرا کاری نمی‌کنند. mypy را در CI اجرا کنید، وگرنه فقط کامنت هستند.
- `X | None` را ترجیح بدهید و حالت `None` را مدیریت کنید، به‌جای اینکه امیدوار باشید مقدار هست.
- اول امضای تابع‌ها را annotate کنید. mypy بدنه‌ی تابع را وقتی بررسی می‌کند که annotation داشته باشد، پس امضاها با کمترین کار بیشترین سود را می‌دهند.
- `cast` و `Any` را کم به کار ببرید و `type: ignore` را همیشه با کد خطا.
- در پروژه‌ی موجود، `--strict` را یکی‌یکی برای ماژول‌ها روشن کنید، نه یک‌جا برای کل کد.

interfaceهای Go هم ساختاری برآورده می‌شوند، و `Protocol` دقیقاً همین را به Python می‌دهد. تفاوت این است که در Go کامپایلر آن را اجباری می‌کند و در Python checker را قدم‌به‌قدم خودتان وارد کار می‌کنید.

## تمرین

۱. به یک اسکریپت کوچک خودتان hint اضافه کنید و mypy را اجرا کنید تا تمیز شود.
۲. یک `Protocol` با یک متد بنویسید و دو کلاس بی‌ربط که آن را برآورده می‌کنند.
۳. یک `# type: ignore` اضافی بگذارید و ببینید کدام flag آن را گزارش می‌کند.

## قدم بعدی

نوع‌ها فقط یک دسته از باگ‌ها را می‌گیرند، پس پست بعد «تست در Python با pytest» است، درباره‌ی بررسی رفتاری که نوع‌ها نمی‌توانند توصیف کنند.
