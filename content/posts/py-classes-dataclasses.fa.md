+++
date = '2027-02-07T10:00:00+03:30'
draft = false
title = 'کلاس و dataclass در Python'
description = 'کلاس و dataclass در Python برای برنامه‌نویس‌های Go و Node.js: property، متدهای dunder، slots، MRO، Protocol و enum، همه روی Python 3.14 اجرا شده.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "classes", "dataclasses"]
cover = { image = "/images/covers/py-classes-dataclasses.fa.png", alt = "کلاس و dataclass در Python", hiddenInSingle = true }
+++

یک کلاس ساده‌ی حساب بانکی، و یک غافلگیری:

```python
class Account:
    history = []
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance
    def deposit(self, n):
        self.balance += n
        self.history.append(n)
```

اگر دو حساب جداگانه بسازم، ۳ را به اولی و ۷ را به دومی واریز کنم و `history` هر حساب را چاپ کنم، هر دو `[3, 7]` چاپ می‌کنند. دو حساب، یک تاریخچه. دلیلش تفاوتی است که در Go ندارید: کلاس در Python داده را می‌تواند در دو جا نگه دارد، روی خود کلاس (مشترک بین همه) و روی هر نمونه (خصوصی). بیشتر چیزهایی که درباره‌ی کلاس‌های Python گیج‌کننده است به این برمی‌گردد که بدانید به کدام‌یک از این دو دست می‌زنید.

این پست از کلاس ساده تا `dataclass` می‌رود، که بیشتر کد تکراری را حذف می‌کند. بعد از [توابع، closure و generator](/fa/posts/py-functions-generators/) می‌آید، چون متد فقط تابعی است که روی کلاس زندگی می‌کند. اگر از Go آمده‌اید، نزدیک‌ترین چیز [struct و متد در Go](/fa/posts/go-structs-methods-interfaces/) است و مقایسه با آن را فقط جایی آورده‌ام که مطمئنم.

> همه‌چیز با Python 3.14.0 روی macOS اجرا شده است (`python3 --version`). دموها سه اسکریپت محلی `a.py`، `b.py` و `c.py` هستند. اندازه‌ی بایت‌ها به این ماشین و این نسخه‌ی Python بستگی دارد.

## کلاس، attribute و متد

کلاس یک نقشه است و هر فراخوانی مثل `Account("ali", 10)` از روی آن یک شیء (یک *نمونه*) می‌سازد. Python روی شیء تازه `__init__` را اجرا می‌کند و `self` همان شیء است. برخلاف receiver در Go یا `this` در JavaScript، `self` صریح است: فقط پارامتر اول هر متد است و خودتان می‌نویسیدش. کلاس کامل دمو این است:

```python
class Account:
    bank = "Demo"            # class attribute
    history = []             # shared mutable class attribute (gotcha)
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
print(a.bank, b.bank, Account.bank, Account.valid(3))
```

```text
[3, 7] [3, 7] True
Mine Demo Demo True
```

اینجا دو نوع attribute در کار است. `bank` و `history` مستقیم در بدنه‌ی کلاس نوشته شده‌اند، پس **attribute کلاس** هستند: یک نسخه، مشترک. `owner` و `balance` داخل `__init__` و از طریق `self` مقدار گرفته‌اند، پس هر نمونه مال خودش را دارد.

- **خط اول خروجی:** `history` یک attribute کلاس است که لیست نگه می‌دارد. `a.deposit(3)` و `b.deposit(7)` هر دو `self.history.append(...)` کردند. Python `history` را روی نمونه می‌گردد، پیدا نمی‌کند و سراغ کلاس می‌رود، پس هر دو به همان یک لیست مشترک اضافه کردند. `a.history is b.history` تأیید می‌کند که یک شیء است. راه‌حل ساختن لیست در `__init__` است: `self.history = []`.
- **خط دوم خروجی:** `a.bank = "Mine"` کلاس را عوض نمی‌کند. روی نمونه‌ی `a` یک attribute تازه می‌سازد که attribute کلاس را می‌پوشاند. `b` و خود کلاس هنوز `Demo` می‌گویند. (انتساب می‌سازد؛ دام اشتراک از *تغییر دادن* یک شیء مشترک می‌آید.)

دو decorator دیده می‌شود. `@classmethod` خود کلاس را می‌گیرد (اینجا با اسم `cls`) و جای طبیعی یک سازنده‌ی جایگزین است: `Account.from_string("sara:5")` از روی یک رشته حساب می‌سازد. `@staticmethod` چیز خاصی نمی‌گیرد؛ تابع معمولی است که اتفاقاً در فضای نام کلاس نشسته.

## Property

فرض کنید `celsius` اول یک attribute ساده بود و بعداً می‌خواهید مقدارهای ناممکن را رد کنید. در بعضی زبان‌ها از روز اول getter و setter می‌نوشتید. در Python می‌توانید صبر کنید، چون `@property` نحو attribute ساده را نگه می‌دارد و پشتش کد اجرا می‌کند:

```python
class Temp:
    def __init__(self, c): self.celsius = c
    @property
    def celsius(self): return self._c
    @celsius.setter
    def celsius(self, v):
        if v < -273.15: raise ValueError("below absolute zero")
        self._c = v
    @property
    def fahrenheit(self): return self._c * 9 / 5 + 32

t = Temp(100); print(t.fahrenheit)
try: t.celsius = -300
except ValueError as e: print("ValueError:", e)
```

```text
212.0
ValueError: below absolute zero
```

`t.fahrenheit` شبیه attribute است ولی در هر دسترسی محاسبه می‌شود. انتساب `t.celsius = -300` شبیه انتساب ساده است ولی setter را اجرا می‌کند که آن را رد می‌کند. مقدار واقعی در `_c` می‌ماند؛ underscore اول فقط قرارداد است و می‌گوید «داخلی». کسی که `t.celsius` را به کار می‌برد شکل نوشتنش عوض نمی‌شود، پس می‌توانید بعداً بدون شکستن چیزی اعتبارسنجی اضافه کنید.

## متدهای dunder

`print(p)` از کجا می‌داند شیء شما را چطور نشان بدهد، و `p == q` چطور کار می‌کند؟ Python متدهای ویژه‌ای را صدا می‌زند که اسمشان دو underscore در دو طرف دارد؛ به آن‌ها {{< term "dunder-method" "متد dunder" >}} می‌گویند (از «double underscore»). خودتان کم صدایشان می‌زنید؛ Python پشت نحو صدایشان می‌زند. یک کلاس نقطه‌ی کوچک که سه‌تایشان را تعریف می‌کند:

```python
class P:
    def __init__(self, x, y): self.x, self.y = x, y
    def __repr__(self): return f"P({self.x}, {self.y})"
    def __str__(self): return f"({self.x}; {self.y})"
    def __eq__(self, o): return (self.x, self.y) == (o.x, o.y)
p, q = P(1, 2), P(1, 2)
print(repr(p), str(p), p == q, [p])
try: {p}
except TypeError as e: print("TypeError:", e)
print(P.__hash__)
```

```text
P(1, 2) (1; 2) True [P(1, 2)]
TypeError: cannot use 'P' as a set element (unhashable type: 'P')
None
```

- `__repr__` برای برنامه‌نویس است: متنی بدون ابهام، ترجیحاً شبیه کد. `__str__` برای نمایش به کاربر است و `print` از آن استفاده می‌کند. وقتی شیءها داخل لیست‌اند، Python هر عضو را با `__repr__` نشان می‌دهد، برای همین `[p]` را `[P(1, 2)]` چاپ کرد، نه `[(1; 2)]`.
- `__eq__` باعث می‌شود `p == q` بر اساس محتوا مقایسه کند (`True`)، نه هویت.
- بعد یک غافلگیری می‌آید. گذاشتن `p` در یک set خطای «unhashable type» داد. وقتی `__eq__` را بدون `__hash__` تعریف کنید، Python مقدار `__hash__` را `None` می‌کند، که خط آخر نشان می‌دهد. منطقش این است که دو شیء برابر باید hash برابر داشته باشند و Python حدس نمی‌زند hash شما چطور حساب شود.

افزودن `__hash__` از روی همان فیلدها درستش می‌کند: در دمو یک زیرکلاس با `def __hash__(self): return hash((self.x, self.y))` باعث شد set دو نقطه‌ی برابر طول ۱ داشته باشد.

برای ترتیب، لازم نیست هر شش متد مقایسه را بنویسید. `__eq__` و `__lt__` را بنویسید و `functools.total_ordering` بقیه یعنی `<=`، `>` و `>=` را پر می‌کند. با یک کلاس کوچک `V`، هم `V(1) <= V(2)` و هم `V(3) > V(2)` برابر `True` بود و `sorted([V(3), V(1)])` برابر `[V(1), V(3)]` شد.

## dataclass

ببینید `P` چه چیزهایی لازم داشت: `__init__`، `__repr__`، `__eq__` و باز هم `__hash__`. برای کلاسی که فقط داده نگه می‌دارد این کد تکراری زیادی است. {{< term "dataclass" "dataclass" >}} این‌ها را از روی فهرست فیلدها می‌سازد. فیلدها را با annotation نوع می‌نویسید و decorator `@dataclass` متدها را تولید می‌کند:

```python
@dataclass
class Item:
    name: str
    price: float = 0.0
    tags: list[str] = field(default_factory=list)
    def __post_init__(self):
        if self.price < 0: raise ValueError("price must be >= 0")

i = Item("pen", 1.5)
print(i, i == Item("pen", 1.5), i == Item("pen", 2))
try: Item("x", -1)
except ValueError as e: print("ValueError:", e)
```

```text
Item(name='pen', price=1.5, tags=[]) True False
ValueError: price must be >= 0
```

خط اول `__repr__` تولیدشده را نشان می‌دهد، بعد `==` روی یک آیتم برابر (`True`) و یک آیتم متفاوت (`False`). برابری همه‌ی فیلدها را مقایسه می‌کند. `__post_init__` درست بعد از `__init__` تولیدشده اجرا می‌شود، پس جای اعتبارسنجی است: خط دوم `ValueError` برای قیمت منفی است. annotationها (`str`، `float`) موقع اجرا اجبار نمی‌شوند؛ Python اینجا چک‌شان نمی‌کند.

یک نکته‌ی دیگر که به دام لیست مشترک بالا وصل است. فیلد `tags` از `field(default_factory=list)` استفاده می‌کند، یعنی «برای هر نمونه‌ی تازه `list()` را صدا بزن». دمو یک پیش‌فرض `[]` ساده را هم امتحان کرد:

```text
ValueError: mutable default <class 'list'> for field xs is not allowed: use default_factory
```

dataclass آن را رد می‌کند و می‌گوید به‌جایش چه بنویسید، پس شما را از باگ پیش‌فرض مشترکی که در پست قبل دیدیم نجات می‌دهد.

دو گزینه‌ی رایج `frozen` و `order` است. با `@dataclass(frozen=True, order=True)` کلاس `Ver(major, minor)` این‌طور رفتار می‌کند:

```python
v = Ver(1, 2)
try: v.major = 3
except FrozenInstanceError as e: print("FrozenInstanceError:", e)
print(Ver(1, 2) < Ver(1, 10), hash(v) == hash(Ver(1, 2)), len({v, Ver(1, 2)}))
```

```text
FrozenInstanceError: cannot assign to field 'major'
True True 1
```

مقدار دادن به فیلد `FrozenInstanceError` می‌اندازد. `order=True` مقایسه می‌دهد، پس `Ver(1, 2) < Ver(1, 10)` برابر `True` است. و dataclass منجمد hash‌پذیر است، پس دو مقدار برابر در set یک عضو می‌شوند (طول ۱).

اگر فقط یک بسته‌ی تغییرناپذیر از مقدارها می‌خواهید، `typing.NamedTuple` جایگزین سبک‌تری است: `NT(x=1, y=2)` مثل dataclass چاپ می‌شود ولی مثل tuple هم باز می‌شود و اندیس می‌خورد (دمو برای نمونه، عضو اولش و `a + b` بعد از باز کردن، `NT(x=1, y=2) 1 3` چاپ کرد). من وقتی متد، پیش‌فرض یا تغییرپذیری می‌خواهم dataclass به کار می‌برم.

## حافظه و slots

نمونه‌ی معمولی attributeهایش را در یک دیکشنری به اسم `__dict__` نگه می‌دارد، که اجازه می‌دهد هر وقت خواستید attribute اضافه کنید. با `@dataclass(slots=True)` نام attributeها از قبل ثابت می‌شود ({{< term "slots" "slots" >}}) و نمونه‌ها `__dict__` ندارند. ۱۰۰٬۰۰۰ نمونه از کلاسی با سه فیلد int را در دو نسخه ساختم و با `tracemalloc` اندازه گرفتم:

```text
Plain    10403616 bytes  (104 per object)
Slotted   6400928 bytes  (64 per object)
AttributeError: 'Slotted' object has no attribute 'd' and no __dict__ for setting new attributes
```

در همین دمو `hasattr(..., "__dict__")` برای کلاس معمولی `True` و برای کلاس slotted برابر `False` بود. این مجموع‌ها لیستی را که شیءها را نگه می‌دارد هم شامل می‌شوند (۸ بایت برای هر ورودی)، برای همین رقم slotted برابر ۶۴ است، نه ۵۶ که `sys.getsizeof` برای یک نمونه گزارش می‌کند. صرفه‌جویی اینجا حدود ۴۰ بایت برای هر شیء است و هزینه‌اش همان خط آخر است: attributeی که اعلام نشده نمی‌توانید اضافه کنید. برای میلیون‌ها شیء کوچک می‌ارزد، در غیر این صورت نه.

## ارث‌بری، MRO و ترکیب

ارث‌بری همان‌طور که انتظار دارید کار می‌کند. زیرکلاس می‌تواند نسخه‌ی والد را با `super()` صدا بزند:

```python
class Dog(Animal):
    def __init__(self, name, trick):
        super().__init__(name); self.trick = trick
    def speak(self): return super().speak() + " (woof)"
```

`Dog("rex", "sit").speak()` برابر `rex makes a sound (woof)` چاپ شد و `isinstance(d, Animal)` برابر `True` بود. Python چند والد را هم اجازه می‌دهد. در شکل «الماس»، یعنی `D(B, C)` که هر دو `B` و `C` از `A` ارث می‌برند، کدام `who()` اول اجرا می‌شود؟ {{< term "mro" "MRO" >}} (ترتیب جست‌وجوی متد) تصمیم می‌گیرد و `super()` آن را دنبال می‌کند:

```text
['D', 'B', 'C', 'A', 'object']
D>B>C>A
```

خط اول `D.__mro__` است: اول `D`، بعد `B`، بعد `C`، بعد `A` را بگرد. هر `who()` یک بار `super().who()` را صدا زد، پس خط دوم نشان می‌دهد هر کلاس دقیقاً یک بار و به همین ترتیب اجرا شد و `A` دو بار اجرا نشد. قاعده‌ی من این است که ترکیب (composition) را ترجیح بدهم و فقط برای رابطه‌ی واقعی «است یک» ارث ببرم. مثلاً `Car` یک `Engine` نگه می‌دارد و `self.engine.start()` را صدا می‌زند، که `vroom` چاپ کرد.

## Protocol: duck typing به شکل صریح

Python از {{< term "duck-typing" "duck typing" >}} استفاده می‌کند: اگر شیء متد `speak()` دارد، می‌توانید `speak()` را صدا بزنید و کلاسش مهم نیست. `typing.Protocol` همین انتظار را مکتوب می‌کند. این {{< term "structural-typing" "نوع‌دهی ساختاری" >}} است: نوع وقتی می‌خواند که متدهای درست را داشته باشد.

```python
class Speaker(Protocol):
    def speak(self) -> str: ...
def talk(s: Speaker): return s.speak()
```

`Robot` متد `speak()` دارد و هیچ‌وقت اسمی از `Speaker` نمی‌برد، و باز هم آن را برآورده می‌کند، مثل اینکه interface در Go ضمنی برآورده می‌شود. فرق در این است که چه کسی چک می‌کند. Protocol برای **type checker** است، نه برای زمان اجرا، و من اینجا type checker اجرا نکردم. موقع اجرا `talk(42)` با `AttributeError: 'int' object has no attribute 'speak'` شکست خورد، و یک `isinstance(Robot(), Speaker)` ساده این را انداخت:

```text
TypeError: Instance and class checks can only be used with @runtime_checkable protocols
```

با `@runtime_checkable`، `isinstance` برای `Robot` برابر `True` و برای `42` برابر `False` شد. فقط وجود متد را چک می‌کند، نه امضایش را.

## enum

وقتی یک مقدار فقط می‌تواند یکی از چند گزینه‌ی نام‌دار باشد، از `Enum` استفاده کنید:

```python
class Status(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
```

`Status("active")` برابر `Status.ACTIVE` است که `.name` آن `ACTIVE` و `.value` آن `active` است. `Status.BLOCKED is Status("blocked")` برابر `True` است، پس عضوهای enum را با `is` مقایسه می‌کنید. `Status("nope")` خطای `ValueError: 'nope' is not a valid Status` می‌دهد.

## جاهایی که کلاس‌ها غافلگیر می‌کنند

- **attributeهای تغییرپذیر کلاس مشترک‌اند.** لیست یا dictی که در بدنه‌ی کلاس نوشته شود یک شیء برای همه‌ی نمونه‌هاست. آن را در `__init__` بسازید، یا در dataclass با `default_factory`.
- **تعریف `__eq__` باعث حذف `__hash__` می‌شود.** شیءهای شما در set و به‌عنوان کلید dict کار نمی‌کنند تا `__hash__` را هم تعریف کنید (یا از dataclass منجمد استفاده کنید).
- **ترکیب `auto()` با مقدارهای رشته‌ای.** در دمو یک `Enum` با `A = "active"` و بعد `B = auto()` خطای `TypeError: unable to increment 'active'` داد، چون `auto()` می‌خواهد به مقدار قبلی یکی اضافه کند. این دو را قاطی نکنید.
- **Protocol موقع اجرا اجبار نمی‌شود.** اگر چک‌شدنش را می‌خواهید type checker اجرا کنید.
- **`frozen=True` فقط انتساب را می‌بندد.** dataclass منجمد با فیلد لیست هنوز اجازه می‌دهد به آن لیست `append` کنید: اجرایش کردم و `F(xs=[1])` گرفتم.

## تمرین

1. dataclass منجمد `Money` را با `amount` (سنت به‌صورت int) و `currency` بنویسید، در `__post_init__` اعتبارسنجی کنید و متد `__add__` اضافه کنید.
2. MRO کلاسی با دو والد را چاپ کنید و قبلش ترتیب را حدس بزنید.
3. کلاس معمولی و `slots=True` را برای پنج فیلد با `tracemalloc` اندازه بگیرید.

## قدم بعدی

پست بعدی «خطا و context manager در Python» است. exceptionهای سفارشی هم کلاس‌اند، پس هرچه اینجا گفتیم درباره‌ی آن‌ها هم صدق می‌کند.
