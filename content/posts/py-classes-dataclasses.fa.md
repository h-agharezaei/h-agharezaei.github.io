+++
date = '2027-02-07T10:00:00+03:30'
draft = false
title = 'کلاس و dataclass در Python'
description = 'کلاس و dataclass در Python برای برنامه‌نویس‌های Go و Node.js: property، متدهای dunder، slots، MRO، Protocol و enum، همه روی Python 3.14 اجرا شده.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "classes", "dataclasses"]
cover = { image = "/images/covers/py-classes-dataclasses.fa.png", alt = "کلاس و dataclass در Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-functions-generators/) تابع، closure و generator نوشتیم. حالا داده و رفتار را کنار هم می‌گذاریم: کلاس. اگر از Go آمده‌اید، نزدیک‌ترین چیز [Struct و متد در Go](/fa/posts/go-structs-methods-interfaces/) است و مقایسه را فقط جایی آورده‌ام که از واقعیتش مطمئنم.

> همه‌چیز با Python 3.14.0 روی macOS اجرا شده است (`python3 --version`). دموها سه اسکریپت محلی هستند. تعداد بایت‌ها مخصوص همین ماشین و نسخه است.

## کلاس، attribute و متد

```python
class Account:
    bank = "Demo"            # class attribute
    history = []             # mutable مشترک در کلاس
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance
    def deposit(self, n):
        self.balance += n
        self.history.append(n)
    @classmethod
    def from_string(cls, s):
        o, b = s.split(":")
        return cls(o, int(b))
    @staticmethod
    def valid(n): return n > 0

a, b = Account("ali", 10), Account.from_string("sara:5")
a.deposit(3); b.deposit(7)
print(a.history, b.history, a.history is b.history)
a.bank = "Mine"
print(a.bank, b.bank, Account.bank)
```

```text
[3, 7] [3, 7] True
Mine Demo Demo
```

`self` صریح است و فقط پارامتر اول متد است. `@classmethod` خود کلاس را می‌گیرد (یک constructor جایگزین) و `@staticmethod` چیزی نمی‌گیرد. نکته‌ی خطرناک: `history` روی کلاس است، پس هر دو حساب یک لیست را شریک‌اند. نوشتن `a.bank = ...` یک attribute روی نمونه می‌سازد و کلاس را عوض نمی‌کند. state تغییرپذیر را در `__init__` بسازید.

## Property

`@property` ظاهر attribute را نگه می‌دارد ولی کد اجرا می‌کند:

```python
@property
def celsius(self): return self._c
@celsius.setter
def celsius(self, v):
    if v < -273.15: raise ValueError("below absolute zero")
    self._c = v
```

```text
212.0                              # Temp(100).fahrenheit، یک property محاسبه‌شده
ValueError: below absolute zero    # t.celsius = -300
```

پس می‌توانید با یک attribute ساده شروع کنید و بعداً بدون تغییر در کدهای صدازننده، اعتبارسنجی اضافه کنید.

## متدهای dunder

{{< term "dunder-method" "متد dunder" >}} چیزی است که Python پشت syntax صدا می‌زند. `__repr__` برای برنامه‌نویس (و داخل لیست‌ها) است و `__str__` برای نمایش:

```text
repr(p) = P(1, 2)   str(p) = (1; 2)   [p] = [P(1, 2)]   p == q -> True
TypeError: cannot use 'P' as a set element (unhashable type: 'P')
```

اگر `__eq__` را بدون `__hash__` تعریف کنید، `__hash__` برابر `None` می‌شود و `{p}` خطا می‌دهد. با افزودن `__hash__` روی همان فیلدها درست شد: دو نقطه‌ی برابر یک set به طول ۱ ساختند. برای ترتیب، `__eq__` و `__lt__` را بنویسید و بگذارید `functools.total_ordering` بقیه‌ی `<=` و `>` و `>=` را بسازد: `V(1) <= V(2)` و `sorted(...)` کار کردند.

## dataclass

این‌ها boilerplate زیادی است، پس {{< term "dataclass" "dataclass" >}} آن را تولید می‌کند:

```python
@dataclass
class Item:
    name: str
    price: float = 0.0
    tags: list[str] = field(default_factory=list)
    def __post_init__(self):
        if self.price < 0: raise ValueError("price must be >= 0")
```

```text
Item(name='pen', price=1.5, tags=[]) True False
ValueError: price must be >= 0
ValueError: mutable default <class 'list'> for field xs is not allowed: use default_factory
```

خط اول `__repr__` تولیدشده است، بعد `==` روی دو Item برابر و غیربرابر. اعتبارسنجی در `__post_init__` می‌رود و مقدار پیش‌فرض `[]` رد می‌شود، که شما را از دردسر لیست مشترک بالا نجات می‌دهد.

`@dataclass(frozen=True, order=True)` باعث شد `Ver(1, 2) < Ver(1, 10)` درست باشد، انتساب `FrozenInstanceError: cannot assign to field 'major'` بدهد و نمونه hashable باشد (set از دو مقدار برابر طول ۱ داشت). `NamedTuple` جایگزین نامتغیر و شبیه tuple است: `NT(x=1, y=2)` مثل tuple unpack و index می‌شود. من وقتی متد، مقدار پیش‌فرض یا تغییرپذیری می‌خواهم dataclass را برمی‌دارم.

## حافظه و slots

نمونه‌های معمولی attributeها را در یک `__dict__` جدا نگه می‌دارند. با `@dataclass(slots=True)` فهرست {{< term "slots" "slots" >}} ثابت است. ۱۰۰٬۰۰۰ نمونه از کلاسی با سه int ساختم و با `tracemalloc` اندازه گرفتم:

```text
Plain    10403616 bytes  (104 per object)
Slotted   6400928 bytes  (64 per object)
AttributeError: 'Slotted' object has no attribute 'd' and no __dict__ for setting new attributes
```

اینجا حدود ۴۰ بایت برای هر شیء صرفه‌جویی شد، به قیمت اینکه نمی‌توان attribute تازه اضافه کرد. برای میلیون‌ها شیء کوچک می‌ارزد، وگرنه نه.

## ارث‌بری، MRO و composition

```python
class Dog(Animal):
    def speak(self): return super().speak() + " (woof)"
```

این `rex makes a sound (woof)` چاپ کرد. در حالت الماسی (`D(B, C)` که هر دو از `A` ارث می‌برند) ترتیب را {{< term "mro" "MRO" >}} تعیین می‌کند و `super()` همان را دنبال می‌کند:

```text
['D', 'B', 'C', 'A', 'object']
D>B>C>A
```

هر `who()` یک بار `super().who()` را صدا زد، پس هر کلاس دقیقاً یک بار اجرا شد. قاعده‌ی من: composition را ترجیح بدهید (`Car` یک `Engine` دارد و `self.engine.start()` را صدا می‌زند که `vroom` چاپ کرد) و فقط برای رابطه‌ی واقعی «است یک» ارث‌بری کنید.

## Protocol: duck typing صریح

Python از {{< term "duck-typing" "duck typing" >}} استفاده می‌کند: هر چیزی که `speak()` دارد کار می‌کند. `typing.Protocol` این شکل را به‌صورت {{< term "structural-typing" "نوع‌دهی ساختاری" >}} می‌نویسد:

```python
class Speaker(Protocol):
    def speak(self) -> str: ...
def talk(s: Speaker): return s.speak()
```

`Robot` هیچ‌جا اسم `Speaker` را نمی‌آورد و باز هم آن را برآورده می‌کند، مثل interface در Go که ضمنی برآورده می‌شود. تفاوت: Protocol را type checker بررسی می‌کند، نه زمان اجرا. من اینجا type checker اجرا نکردم. در زمان اجرا `talk(42)` با `AttributeError: 'int' object has no attribute 'speak'` شکست خورد و `isinstance(Robot(), Speaker)` خطای `TypeError: Instance and class checks can only be used with @runtime_checkable protocols` داد. با `@runtime_checkable` نتیجه‌ی `isinstance` برای `Robot` برابر `True` و برای `42` برابر `False` بود (فقط وجود متد را چک می‌کند).

## enum

```python
class Status(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
```

`Status("active")` همان `Status.ACTIVE` است، `.name` برابر `ACTIVE` و `.value` برابر `active` است و `Status("nope")` خطای `ValueError: 'nope' is not a valid Status` می‌دهد.

## چند نکته‌ی مهم

- attributeهای تغییرپذیر کلاس مشترک‌اند. لیست و dict را در `__init__` یا با `default_factory` بسازید.
- `__eq__` را تعریف کنید، `__hash__` از دست می‌رود مگر آن را هم بنویسید.
- `auto()` بعد از مقدار رشته‌ای برای من با `TypeError: unable to increment 'active'` شکست خورد. قاطی نکنید.
- Protocol در زمان اجرا اجبار نمی‌شود. اگر این را می‌خواهید type checker اجرا کنید.
- `frozen=True` فقط انتساب attribute را می‌بندد، نه تغییر لیستِ داخل آن را.

## تمرین

1. یک dataclass فریز‌شده‌ی `Money` با `amount` (سنت، int) و `currency` بنویسید، در `__post_init__` اعتبارسنجی کنید و متد `__add__` اضافه کنید.
2. MRO کلاسی با دو والد را چاپ کنید و اول ترتیب را حدس بزنید.
3. کلاس معمولی و `slots=True` با پنج فیلد را با `tracemalloc` اندازه بگیرید.

## قدم بعدی

مقاله‌ی بعدی «خطا و context manager در Python» است.
