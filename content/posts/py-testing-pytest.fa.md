+++
date = '2027-03-24T10:00:00+03:30'
draft = false
title = 'تست در Python با pytest'
description = 'تست در Python با pytest: assertion rewriting، fixture، parametrize، monkeypatch، mock و coverage، همه با pytest 9.1.1 روی Python 3.14 اجرا شده.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "pytest", "testing", "fixtures", "coverage"]
cover = { image = "/images/covers/py-testing-pytest.fa.png", alt = "تست در Python با pytest", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-type-hints-mypy/) type hint و mypy را اضافه کردیم؛ type یک دسته از باگ‌ها را می‌گیرد و بقیه را تست. Python خودش `unittest` دارد ولی تقریباً همه از pytest استفاده می‌کنند. pytest یک {{< term "test-runner" "test runner" >}} است که تابع‌های `test_*` را پیدا می‌کند و اجازه می‌دهد `assert` ساده بنویسید. اگر [table-driven test در Go](/fa/posts/go-testing-basics/) را دیده باشید ایده‌ها آشناست، و نگرش کلی به تست را در [هرم تست و TDD](/fa/posts/eng-testing-pyramid-tdd/) نوشته‌ام.

> همه‌چیز با Python 3.14.0 و pytest 9.1.1 و pytest-cov 7.1.0 (`pytest --version`) در یک venv موقت اجرا شده که حذفش کرده‌ام. دمو یک پکیج کوچک محلی `app/` با پوشه‌ی `tests/` است و مسیر home حذف شده است.

## assert ساده و خروجی شکست

خبری از `self.assertEqual` نیست؛ می‌نویسید `assert a == b`. pytest هنگام import تست، assert را بازنویسی می‌کند و برای همین شکست خودش را توضیح می‌دهد. دو لیست و دو دیکشنری را مقایسه کردم:

```text
E       assert [1, 2, 3, 4] == [1, 2, 9, 4]
E         At index 2 diff: 3 != 9
E       AssertionError: assert {'a': 1, 'b': 2} == {'a': 1, 'b': 3}
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'b': 2} != {'b': 3}
```

ابزار اندیس و کلید متفاوت را نشان داد. با `-v` یا `-vv` جزئیات بیشتر می‌آید.

یک مشکل واقعی که خودم دیدم: تست‌ها `from app import pricing` داشتند و collection با `ModuleNotFoundError: No module named 'app'` شکست خورد. افزودن `pythonpath = .` به `pytest.ini` آن را حل کرد.

## Fixture

یک {{< term "fixture" "fixture" >}} چیزی را که تست لازم دارد آماده می‌کند و تست نامش را در پارامترها می‌نویسد. با `yield`، کد بعد از آن teardown است (مثل {{< term "context-manager" "context manager" >}} در [خطا و context manager در Python](/fa/posts/py-errors-context-managers/)). آن‌ها را در `conftest.py` گذاشتم که pytest خودکار بارگذاری می‌کند و همه‌ی تست‌های آن پوشه می‌توانند استفاده کنند:

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

دو تست هر دو را استفاده کردند و لاگی که آخر session چاپ شد این بود:

```text
setup  test_order_a
teardown test_order_a
setup  test_order_b
teardown test_order_b
```

fixture با scope تابع برای هر تست اجرا شد، اما با `-s` فیکسچر سطح module فقط یک‌بار `[module fixture setup]` را قبل از اولین تستِ نیازمند چاپ کرد و `[module fixture teardown]` را یک‌بار بعد از آخرین تست فایل.

## fixtureهای آماده

- `tmp_path`: یک پوشه‌ی موقت تازه. یک فایل JSON آنجا نوشتم و با کد تحت‌تست خواندم.
- `monkeypatch`: {{< term "monkeypatch" "جایگزینی موقت" >}} که بعد از تست برمی‌گردد. `monkeypatch.setenv("RATE", "2.5")` باعث شد `get_rate()` عدد `2.5` بدهد و تست بعدی بدون آن مقدار پیش‌فرض `1.0` را گرفت.
- `capsys`: stdout را می‌گیرد. `greet("roham")` دقیقاً `"hello roham\n"` تولید کرد.

## Parametrize

یک {{< term "parametrized-test" "تست پارامتری" >}} یک بدنه را روی چند ردیف اجرا می‌کند. در Go همین ایده جدول به‌همراه `t.Run` است؛ اینجا هر ردیف یک تست جداست:

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

## خطای مورد انتظار

```python
with pytest.raises(ValueError, match=r"out of range: 120"):
    pricing.apply_discount(10, 120)
```

`match` یک regex است که در پیام جست‌وجو می‌شود؛ پس اگر `ValueError` دیگری بیاید تست شکست می‌خورد.

## Marker و انتخاب تست

یک تست را `@pytest.mark.slow` زدم (در `pytest.ini` ثبت شده، وگرنه pytest هشدار می‌دهد). بعد: `-m "not slow"` نتیجه‌ی `12 passed, 1 deselected` داد، `-m slow` نتیجه‌ی `1 passed, 12 deselected`، و `-k "discount and not bad"` سه ردیف پارامتری را انتخاب کرد (`3 passed, 10 deselected`).

## Mock و تله‌ی آن

`unittest.mock` یک وابستگی را عوض می‌کند. `welcome(7)` تابع `fetch_user` را صدا می‌زند که به شبکه می‌رفت:

```python
with mock.patch("app.service.fetch_user", return_value={"name": "Ana"}) as m:
    assert service.welcome(7) == "welcome Ana"
m.assert_called_once_with(7)
```

تست پاس شد. باید همان‌جایی patch کنید که نام *جست‌وجو می‌شود* (`app.service.fetch_user`) نه جایی که تعریف شده. mock یک {{< term "test-double" "test double" >}} است و تله‌اش over-mocking است: خود `apply_discount` را patch کردم که ۹۹۹ برگرداند و ۹۹۹ را assert کردم. پاس شد و چیزی را تست نکرد. همچنین غلط املایی مثل `m.assert_called_once_wiht(1)` بی‌صدا رد نمی‌شود: `AttributeError ... Did you mean: 'assert_called_once_with'?` داد. فقط لبه‌ها (شبکه، ساعت) را mock کنید، نه منطقی را که می‌خواهید تست کنید.

## تست مبتنی بر ویژگی

به‌جای مثال، {{< term "property-based-testing" "property-based testing" >}} یک قاعده می‌گوید و ورودی تولید می‌کند؛ [Property-based testing](/fa/posts/eng-property-based-testing/) را ببینید. ابزار معمول آن Hypothesis است. برای این مقاله آن را نصب و اجرا نکردم، پس خروجی‌ای نشان نمی‌دهم.

## Coverage

```text
Name              Stmts   Miss  Cover   Missing
app/pricing.py       17      3    82%   20-22
app/service.py        6      1    83%   5
TOTAL                23      4    83%
```

از `pytest --cov=app --cov-report=term-missing`. خط‌های ۲۰ تا ۲۲ در `pricing.py` همان `unused_branch` است که هیچ تستی صدایش نمی‌زند، و خط ۵ در `service.py` همان `fetch_user` واقعی است که همیشه patch کردم. {{< term "code-coverage" "Coverage" >}} می‌گوید چه چیزی اجرا شد، نه این‌که assertها خوب‌اند.

## چند نکته‌ی مهم

- تست‌ها به `pythonpath` یا پکیج نصب‌شده نیاز دارند، وگرنه import شکست می‌خورد.
- نام را همان‌جا patch کنید که استفاده می‌شود.
- fixture را به کدِ setup کپی‌شده بین تست‌ها ترجیح دهید.
- markerهای سفارشی را ثبت کنید.
- دنبال coverage صددرصد رفتن تست‌های ضعیف را تشویق می‌کند.

## تمرین

1. یک fixture بنویسید که فایل موقت SQLite بدهد و بعد پاکش کند، و ترتیب را با `-s` ثابت کنید.
2. تابع `slugify` را با `ids` پارامتری کنید، از جمله رشته‌ی خالی.
3. `unused_branch` را پوشش بدهید و ستون `Missing` را ببینید که کوچک می‌شود.

## قدم بعدی

مقاله‌ی بعدی «GIL و threading» است.
