+++
date = '2027-03-24T10:00:00+03:30'
draft = false
title = 'تست در Python با pytest'
description = 'تست در Python با pytest: assertion rewriting، fixture، parametrize، monkeypatch، mock و coverage، همه با pytest 9.1.1 روی Python 3.14 اجرا شده.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "pytest", "testing", "fixtures", "coverage"]
cover = { image = "/images/covers/py-testing-pytest.fa.png", alt = "تست در Python با pytest", hiddenInSingle = true }
+++

این یک تست است که سبز می‌شود و هیچ چیزی را ثابت نمی‌کند. تابعی را که باید تست شود با یک نسخه‌ی ساختگی عوض می‌کند که `999` برمی‌گرداند، و بعد ادعا می‌کند که تابع `999` برمی‌گرداند. هر بار سبز است. بعداً به آن برمی‌گردم، چون مهم‌ترین تله‌ی تست‌نویسی است: تست سبز فقط وقتی معنی دارد که می‌توانست قرمز شود.

پست قبلی، [type hint و mypy](/fa/posts/py-type-hints-mypy/)، یک دسته از باگ‌ها را می‌گیرد: مقدار با نوع غلط. تست‌ها بقیه را می‌گیرند، یعنی جاهایی که نوع‌ها درست‌اند ولی رفتار غلط است. Python ماژولی به نام `unittest` همراه خودش دارد، اما تقریباً همه از **pytest** استفاده می‌کنند. pytest یک {{< term "test-runner" "test runner" >}} است: برنامه‌ای که تست‌های شما را پیدا می‌کند، اجرا می‌کند و می‌گوید کدام‌ها شکست خوردند و چرا.

ایده‌ی اصلی کوچک است. تست یک تابع ساده است که اسمش با `test_` شروع می‌شود. pytest آن را پیدا می‌کند و صدا می‌زند، و اگر بدون پرتاب exception تمام شود، تست موفق است. خود بررسی هم یک دستور `assert` معمولی است. برای شروع همین کافی است. اگر [تست‌های جدولی در Go](/fa/posts/go-testing-basics/) را می‌شناسید، ایده‌ها آشنا به نظر می‌رسند، و درباره‌ی طرز فکر پشت تست‌ها در [هرم تست و TDD](/fa/posts/eng-testing-pyramid-tdd/) نوشته‌ام.

> همه‌چیز را دوباره با Python 3.14.0، pytest 9.1.1 و pytest-cov 7.1.0 (`pytest --version`) اجرا کردم، روی یک نسخه‌ی scratch از دمو و در یک virtual environment موقت. دمو یک پکیج کوچک محلی `app/` با پوشه‌ی `tests/` است. مسیرهای خانگی حذف شده‌اند. تست‌های scratch برای assertهای شکست‌خورده، تست `999` و غلط املایی mock داخل پوشه‌ی دمو نیستند؛ آن‌ها را در نسخه‌ی scratch اجرا کردم.

## کدی که تست می‌شود

دمو یک ماژول کوچک `app/pricing.py` دارد با تابعی که درصدی تخفیف اعمال می‌کند:

```python
def apply_discount(price, percent):
    if not 0 <= percent <= 100:
        raise ValueError(f"percent out of range: {percent}")
    return round(price * (100 - percent) / 100, 2)
```

و `app/service.py` که از تابعی استفاده می‌کند که به شبکه وصل می‌شد:

```python
def fetch_user(uid):
    raise RuntimeError("would hit the network")

def welcome(uid):
    user = fetch_user(uid)
    return f"welcome {user['name']}"
```

اولین تست یک تابع و یک assert است:

```python
def test_plain_assert():
    assert pricing.apply_discount(200, 10) == 180.0
```

## assert ساده و خروجی شکستش

در `unittest` داخل یک کلاس می‌نویسید `self.assertEqual(a, b)`. در pytest می‌نویسید `assert a == b`. به نظر می‌رسد وقتی شکست بخورد چیزی به شما نمی‌گوید، ولی pytest هنگام import کردن فایل‌های تست، دستورهای assert را بازنویسی می‌کند و برای همین پیام شکست خودش را توضیح می‌دهد. دو تست را عمداً شکست دادم، یکی با مقایسه‌ی دو فهرست و یکی با مقایسه‌ی دو دیکشنری:

```text
E       assert [1, 2, 3, 4] == [1, 2, 9, 4]
E
E         At index 2 diff: 3 != 9
E         Use -v to get more diff
E       AssertionError: assert {'a': 1, 'b': 2} == {'a': 1, 'b': 3}
E
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'b': 2} != {'b': 3}
E         Use -v to get more diff
```

(مسیر فایل‌ها و خط‌های کد را حذف کرده‌ام.) لازم نیست فهرست‌ها را با چشم مقایسه کنید: pytest اندیسی را نشان می‌دهد که فرق دارد، و برای دیکشنری کلید را نشان می‌دهد و عضوهای یکسان را کنار می‌گذارد. `-v` یا `-vv` جزئیات بیشتری می‌دهد.

یک مشکل اینجا سراغم آمد. تست‌هایم `from app import pricing` داشتند و وقتی دستور `pytest` را اجرا کردم، جمع‌آوری تست‌ها با `ModuleNotFoundError: No module named 'app'` شکست خورد. پوشه‌ی `tests/` به مسیر import اضافه می‌شود، ولی ریشه‌ی پروژه نه. اضافه کردن `pythonpath = .` به `pytest.ini` درستش کرد. (اگر با `python -m pytest` اجرا کنید، پوشه‌ی فعلی به مسیر اضافه می‌شود و مشکل پنهان می‌ماند. هر دو راه را امتحان کردم.)

## Fixture

خیلی از تست‌ها اول به مقداری آماده‌سازی نیاز دارند: یک فایل موقت، یک شیء تنظیم‌شده، یک اتصال. اگر این آماده‌سازی را در همه‌ی تست‌ها کپی کنید، تست‌ها بلند و شکننده می‌شوند. pytest جواب بهتری دارد: {{< term "fixture" "fixture" >}}.

fixture تابعی است که چیزی را که تست لازم دارد آماده می‌کند. تست فقط با نوشتن اسمش به‌عنوان پارامتر آن را می‌خواهد و pytest fixture را اجرا می‌کند و نتیجه را به تست می‌دهد. اگر fixture از `yield` استفاده کند، کد قبل از آن آماده‌سازی است و کد بعد از آن پاک‌سازی، که وقتی تست تمام شد اجرا می‌شود، چه موفق چه ناموفق. این همان ایده‌ی {{< term "context-manager" "context manager" >}} در [خطا و context manager در Python](/fa/posts/py-errors-context-managers/) است. fixtureها را در فایلی به نام `conftest.py` گذاشتم. pytest این فایل را خودکار بارگذاری می‌کند، پس همه‌ی تست‌های آن پوشه می‌توانند از آن‌ها استفاده کنند:

```python
@pytest.fixture
def order(request):
    LOG.append(f"setup  {request.node.name}")
    yield LOG
    LOG.append(f"teardown {request.node.name}")

@pytest.fixture(scope="module")
def shared():
    print("\n[module fixture setup]")
    yield {"n": 1}
    print("\n[module fixture teardown]")
```

fixture اول اسم هر تست را وقت آماده‌سازی و وقت پاک‌سازی ثبت می‌کند. دومی `scope="module"` دارد، یعنی یک بار برای کل فایل تست ساخته می‌شود و نه برای هر تست. دو تست، `test_order_a` و `test_order_b`، هر دو را خواستند. در پایان جلسه `conftest.py` ثبت‌ها را چاپ می‌کند، و اجرا با `-s` (که اجازه می‌دهد `print` دیده شود) این را داد:

```text
tests/test_pricing.py::test_order_a
[module fixture setup]
PASSED
tests/test_pricing.py::test_order_b PASSED
tests/test_pricing.py::test_slow_one PASSED
[module fixture teardown]
...
ORDER:
  setup  test_order_a
  teardown test_order_a
  setup  test_order_b
  teardown test_order_b
```

رفتار دو fixture را ببینید. آن‌که scope تابع داشت دور هر تست آماده و پاک شد: آماده‌سازی، پاک‌سازی، آماده‌سازی، پاک‌سازی. آن‌که scope ماژول داشت `[module fixture setup]` را فقط یک بار چاپ کرد، درست پیش از اولین تستی که لازم داشت، و `[module fixture teardown]` را فقط یک بار، بعد از آخرین تست فایل، حتی با اینکه `test_slow_one` از آن استفاده نمی‌کرد. scope را با هزینه انتخاب کنید: شیء ارزان برای هر تست، شیء گران برای هر ماژول.

## fixtureهای داخلی

pytest خودش هم fixtureهای مفیدی دارد و دمو از سه‌تایشان استفاده می‌کند:

- `tmp_path` به هر تست یک پوشه‌ی موقت تازه می‌دهد. یک فایل JSON آنجا نوشتم و با کدی که تست می‌شد خواندمش، پس هیچ تستی فایلی جا نمی‌گذارد.
- `monkeypatch` چیزی را موقتاً عوض می‌کند، مثلاً یک متغیر محیطی یا یک attribute، و بعد از تست برش می‌گرداند ({{< term "monkeypatch" "monkeypatching" >}}). `monkeypatch.setenv("RATE", "2.5")` باعث شد `get_rate()` عدد `2.5` را برگرداند، و تست بعدی که از آن استفاده نمی‌کرد مقدار پیش‌فرض `1.0` را گرفت.
- `capsys` آنچه کد چاپ می‌کند را می‌گیرد. `greet("roham")` دقیقاً `"hello roham\n"` چاپ کرد و تست روی همین رشته assert کرد.

## parametrize

اغلب می‌خواهید همان تست را با چند ورودی اجرا کنید. می‌شود تست را سه بار کپی کرد یا حلقه نوشت، ولی حلقه در اولین شکست می‌ایستد. {{< term "parametrized-test" "تست پارامتری" >}} یک بدنه را روی ردیف‌های زیادی اجرا می‌کند و هر ردیف جداگانه گزارش می‌شود. Go همین ایده را با یک جدول و `t.Run` دارد:

```python
@pytest.mark.parametrize("price,percent,expected",
    [(100, 0, 100.0), (100, 50, 50.0), (19.99, 10, 17.99)],
    ids=["none", "half", "cents"])
def test_discount(price, percent, expected): ...
```

```text
tests/test_pricing.py::test_discount[none] PASSED
tests/test_pricing.py::test_discount[half] PASSED
tests/test_pricing.py::test_discount[cents] PASSED
```

آرگومان اول اسم پارامترها را می‌دهد، فهرست برای هر حالت یک tuple دارد، و `ids` به هر حالت یک اسم خوانا می‌دهد که در خروجی می‌آید. اگر ردیف `cents` شکست بخورد، گزارش دقیقاً می‌گوید کدام بود.

## خطاهای مورد انتظار

گاهی رفتار درست همان شکست خوردن است. `pytest.raises` این را بررسی می‌کند:

```python
with pytest.raises(ValueError, match=r"out of range: 120"):
    pricing.apply_discount(10, 120)
```

تست فقط وقتی موفق است که بلوک یک `ValueError` پرتاب کند. `match` یک عبارت باقاعده است که در پیام جست‌وجو می‌شود، پس اگر `ValueError` دیگری به دلیل دیگری بیاید هم تست شکست می‌خورد.

## marker و انتخاب تست

می‌شود روی تست‌ها برچسب زد و انتخاب کرد کدام‌ها اجرا شوند. یک تست را با `@pytest.mark.slow` علامت زدم. marker باید در `pytest.ini` ثبت شود (فایل دمو `slow` را دارد)، وگرنه pytest درباره‌ی marker ناشناخته هشدار می‌دهد. بعد با فیلترهای مختلف اجرا کردم:

- `-m "not slow"` نتیجه‌ی `12 passed, 1 deselected` را داد.
- `-m slow` نتیجه‌ی `1 passed, 12 deselected` را داد.
- `-k "discount and not bad"` تست‌ها را با بخشی از اسمشان انتخاب می‌کند و سه ردیف پارامتری را برداشت (`3 passed, 10 deselected`).

## mock و تله‌اش

گاهی تست نباید چیز واقعی را صدا بزند، مثلاً شبکه را. `unittest.mock` یک وابستگی را با یک جانشین عوض می‌کند. `welcome(7)` تابع `fetch_user` را صدا می‌زند که در دمو شکست می‌خورد، پس تست آن را عوض می‌کند:

```python
with mock.patch("app.service.fetch_user", return_value={"name": "Ana"}) as m:
    assert service.welcome(7) == "welcome Ana"
m.assert_called_once_with(7)
```

تست موفق شد. دو نکته را یادتان نگه دارید. اول، جایی را patch کنید که اسم در آن *جست‌وجو می‌شود*، اینجا `app.service.fetch_user`، نه جایی که تعریف شده. دوم، mock یک {{< term "test-double" "test double" >}} است و خطرش زیاد mock کردن است. همان تست اول را یادتان بیاورید: خود `apply_discount` را patch می‌کرد تا `999` بدهد و روی `999` assert می‌کرد. آن تست را در نسخه‌ی scratch اجرا کردم و موفق شد، و فقط خود mock را تست می‌کند. قاعده‌ای که خودم دارم: لبه‌های سیستم را mock کن (شبکه، ساعت، دیسک)، نه منطقی را که می‌خواهی تست کنی.

یک نکته‌ی مرتبط: غلط املایی در assertion مربوط به mock بی‌صدا نادیده گرفته نمی‌شود. `m.assert_called_once_wiht(1)` یک `AttributeError` پرتاب کرد که پیامش با `Did you mean: 'assert_called_once_with'?` تمام می‌شد. این شما را از تستی که به‌خاطر یک غلط املایی هیچ چیز را بررسی نمی‌کند حفظ می‌کند.

## تست خاصیت‌محور

به‌جای فهرست کردن مثال‌ها، {{< term "property-based-testing" "تست خاصیت‌محور" >}} قاعده‌ای را می‌نویسد که همیشه باید برقرار باشد و می‌گذارد یک ابزار ورودی‌های زیادی تولید کند؛ [تست خاصیت‌محور](/fa/posts/eng-property-based-testing/) را ببینید. ابزار معمول کنار pytest کتابخانه‌ی Hypothesis است. آن را نصب و اجرا نکردم، پس اینجا خروجی‌ای برایش نیست.

## coverage

از کجا بفهمیم کدام خط‌ها را تست‌ها هرگز نمی‌رسند؟ coverage این را می‌سنجد. با `pytest --cov=app --cov-report=term-missing` اجرا چاپ کرد:

```text
Name              Stmts   Miss  Cover   Missing
-----------------------------------------------
app/__init__.py       0      0   100%
app/pricing.py       17      3    82%   20-22
app/service.py        6      1    83%   5
-----------------------------------------------
TOTAL                23      4    83%
```

ستون `Missing` را بخوانید. خط‌های ۲۰ تا ۲۲ در `pricing.py` تابع `unused_branch` هستند که هیچ تستی صدایش نمی‌زند. خط ۵ در `service.py` بدنه‌ی `fetch_user` واقعی است که من همیشه آن را با mock عوض کردم. {{< term "code-coverage" "coverage" >}} می‌گوید کدام خط‌ها اجرا شدند، نه اینکه assertها خوب بودند یا نه. تستی بدون هیچ `assert` هم می‌تواند ۱۰۰٪ بدهد.

## تله‌های رایج تست

- تست‌ها به `pythonpath` یا یک پکیج نصب‌شده نیاز دارند، وگرنه importها شکست می‌خورند، همان‌طور که با `ModuleNotFoundError` دیدیم.
- اسم را همان‌جا patch کنید که استفاده می‌شود، نه جایی که تعریف شده، وگرنه patch اثری ندارد.
- fixture را به کدِ آماده‌سازی کپی‌شده بین تست‌ها ترجیح بدهید؛ حتی وقتی تست شکست می‌خورد هم پاک‌سازی می‌کند.
- markerهای سفارشی را ثبت کنید تا pytest درباره‌ی اسم غلط marker هشدار بدهد.
- دنبال ۱۰۰٪ coverage رفتن به تست‌های ضعیفی پاداش می‌دهد که فقط خط‌ها را اجرا می‌کنند. از گزارش برای پیدا کردن کد تست‌نشده استفاده کنید، نه به‌عنوان نمره.

## تمرین

1. یک fixture بنویسید که فایل موقت SQLite بدهد و بعد پاکش کند، و ترتیب را با `-s` ثابت کنید.
2. تابع `slugify` را با `ids` پارامتری کنید، از جمله رشته‌ی خالی.
3. `unused_branch` را پوشش بدهید و ستون `Missing` را ببینید که کوچک می‌شود.

## قدم بعدی

کدِ تست‌شده روی یک thread درست است، پس پست بعد «GIL و threading» است، درباره‌ی اینکه وقتی همین کد هم‌زمان اجرا شود چه چیزی عوض می‌شود.
