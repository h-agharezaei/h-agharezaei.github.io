+++
date = '2027-03-11T10:00:00+03:30'
draft = false
title = 'type hint و mypy'
description = 'type hint و mypy در Python: list[int]، X | None، TypedDict، Protocol، generic با PEP 695، خطاهای واقعی mypy، --strict، cast و type: ignore روی 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "type-hints", "mypy", "typing"]
cover = { image = "/images/covers/py-type-hints-mypy.fa.png", alt = "type hint و mypy", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-errors-context-managers/) خطاها را مدیریت کردیم. این‌جا راهی را می‌بینیم که یک دسته‌ی کامل از آن‌ها را پیش از اجرای برنامه پیدا می‌کند. Python پویا نوع‌دهی می‌شود، اما می‌توانید {{< term "type-hint" "type hint" >}} اضافه کنید و بگذارید یک {{< term "type-checker" "type checker" >}} مثل mypy آن‌ها را بخواند. اگر از [نوع‌های ایستای Go](/fa/posts/go-types-control-flow/) می‌آیید، تفاوت این است که در Python این hintها اختیاری‌اند و مفسر نادیده‌شان می‌گیرد. قبلاً با [dataclass](/fa/posts/py-classes-dataclasses/) کار کردیم؛ با hint خوب کار می‌کند.

> همه‌چیز با Python 3.14.0 و mypy 2.4.0 (`mypy --version`) در یک venv موقت اجرا شده که حذف شده است. دمو چهار فایل کوچک محلی است.

## یک ماژول نوع‌دار

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

`list[int]` و `dict[str, int]` نوع‌های generic داخلی‌اند، `User | None` یعنی «یک User یا None»، `TypedDict` یک dict با کلیدهای معلوم را نوع می‌دهد و `first[T]` یک تابع {{< term "generics" "generic" >}} است که با سینتکس 3.12 به بعد نوشته شده و به `TypeVar` نیازی ندارد. `Protocol` یک شکل را توصیف می‌کند: هر کلاسی که `close()` هم‌امضا داشته باشد قبول است؛ این همان {{< term "structural-typing" "نوع‌دهی ساختاری" >}} و برادر ایستای {{< term "duck-typing" "duck typing" >}} است. با ماژول کامل (یک کلاس `Conn` و تابع `shutdown(c: Closer)` هم داشت) دستور `mypy good.py` چاپ کرد `Success: no issues found in 1 source file` و اجرای آن چاپ کرد `6 {'a': 2, 'b': 1}`، دیکشنری کاربر، `p`، `Order(id=1, total=9.5)` و `closed`.

## خطاهای واقعی

فایل دوم، `bad.py`، چهار اشتباه دارد: لیستی از رشته‌ها به‌جای `list[int]`، استفاده از نتیجه‌ی `int | None` بدون بررسی، تابعی که یک شاخه را فراموش کرده، و کلاسی که `close` آن امضای غلط دارد.

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

(noteها را برای خلاصه‌شدن در یک خط آورده‌ام.) خطای `None` هم‌خانواده‌ی nil dereference در Go است: checker شما را مجبور می‌کند حالت نبودن مقدار را هم مدیریت کنید. راه‌حل `if r is not None:` پیش از استفاده است.

## نوع‌ها در زمان اجرا چک نمی‌شوند

همان فراخوانی غلط، بدون mypy:

```python
def total_of(xs: list[int]) -> int:
    return sum(xs)
print(total_of(['1','2']))
```

```text
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

این خطا از خود `sum` آمد نه از hint. با تابع دیگری، `def f(a: int) -> int: return a*2`، فراخوانی `f('ab')` چاپ کرد `abab` و `f.__annotations__` برابر بود با `{'a': <class 'int'>, 'return': <class 'int'>}`. hintها فقط ذخیره می‌شوند. پس mypy را در CI اجرا کنید، چون چیز دیگری آن‌ها را اعمال نمی‌کند.

در 3.14 annotationها تنبل (lazy) ارزیابی می‌شوند. در `lazy.py` تابعی از کلاسی که پایین‌تر در فایل تعریف شده بود به‌شکل `x: Later` استفاده کرد، بدون کوتیشن و بدون `from __future__ import annotations`، و `f.__annotations__` خودِ کلاس `Later` را چاپ کرد. future import هنوز کار می‌کند؛ باعث می‌شود `__annotations__` رشته‌ی ساده نگه دارد (`{'x': 'Later', 'return': 'int'}`).

## --strict

فایل `loose.py` یک تابع `load(s: str)` بدون نوع بازگشتی، یک `risky(x)` بدون نوع و چند ignore داشت. `mypy loose.py` ساده گفت `Success`، چون mypy به‌طور پیش‌فرض بدنه‌ی تابع‌های بدون annotation را رد می‌کند و از نبودن annotation شکایت نمی‌کند. `mypy --strict loose.py` چهار خطا پیدا کرد:

```text
loose.py:5: error: Function is missing a return type annotation  [no-untyped-def]
loose.py:9: error: Function is missing a type annotation  [no-untyped-def]
loose.py:23: error: Unused "type: ignore" comment  [unused-ignore]
loose.py:24: error: Call to untyped function "risky" in typed context  [no-untyped-call]
```

روی `bad.py` تعداد همان ۵ ماند چون آن توابع از قبل annotation داشتند؛ strict بیشتر روی annotationهای جاافتاده گیر می‌دهد.

## راه‌های فرار

- `Any` چک‌کردن یک مقدار را خاموش می‌کند. `json.loads` مقدار `Any` برمی‌گرداند، پس هر چه بعد از آن بیاید چک نمی‌شود.
- `typing.cast(dict[str, Any], json.loads(s))` فقط به checker می‌گوید چه باور کند؛ در زمان اجرا هیچ کاری نمی‌کند و هیچ چیز را چک نمی‌کند.
- `# type: ignore` یک خط را ساکت می‌کند. در `loose.py` عبارت `f("a")  # type: ignore` یک فراخوانی واقعاً غلط را پنهان کرد و `y: int = 5  # type: ignore` بیهوده بود: strict آن را با `Unused "type: ignore" comment` گزارش کرد.

نکته‌ی بهداشتی: همیشه کد خطا را بنویسید (`# type: ignore[assignment]`)، دلیلش را کنارش بگذارید و `warn_unused_ignores` را (که جزو `--strict` است) روشن کنید تا ignoreهای کهنه پیدا شوند.

## مقایسه با Go

Go نوع‌ها را در زمان کامپایل چک می‌کند و راه فراری ندارد؛ چک‌کردن در Python ابزاری جداست که قدم‌به‌قدم واردش می‌کنید. interfaceهای Go هم ساختاری برقرار می‌شوند، دقیقاً همان چیزی که `Protocol` به Python می‌دهد.

## چند نکته‌ی مهم

- hintها در زمان اجرا کاری نمی‌کنند؛ mypy را به CI وصل کنید.
- `X | None` را ترجیح دهید و شاخه‌ی `None` را مدیریت کنید.
- اول امضای تابع‌ها را annotate کنید؛ بدنه‌ها بعد چک می‌شوند.
- از `cast` و `Any` کم استفاده کنید و `type: ignore` را با کد خطا بنویسید.
- `--strict` را روی کد موجود ماژول‌به‌ماژول روشن کنید، نه یک‌جا.

## تمرین

1. به یک اسکریپت کوچک خودتان hint اضافه کنید و mypy را تا پاک‌شدن اجرا کنید.
2. یک `Protocol` با یک متد و دو کلاس نامرتبط بنویسید که آن را برقرار کنند.
3. یک `# type: ignore` بی‌مصرف اضافه کنید و ببینید کدام flag آن را گزارش می‌کند.

## قدم بعدی

مقاله‌ی بعدی «تست در Python با pytest» است.
