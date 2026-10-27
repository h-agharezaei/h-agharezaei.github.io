+++
date = '2027-01-08T10:00:00+03:30'
draft = false
title = 'محیط Python: venv و uv'
description = 'محیط مجازی Python با venv و uv: نصب با pip، requirements.txt، pyproject.toml، uv.lock و uv sync، همه با اجرای واقعی.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "venv", "uv", "pip", "beginner"]
cover = { image = "/images/covers/py-environment-uv-venv.fa.png", alt = "محیط Python: venv و uv", hiddenInSingle = true }
+++

این اولین پست از سری **Python** است، برای مهندس‌های بک‌اندی که قبلاً Go و Node.js نوشته‌اند. قبل از سینتکس، باید سراغ چیزی برویم که اول از همه تازه‌کارها را زمین می‌زند: Python کجای ماشین شما نشسته و وابستگی‌ها کجا نصب می‌شوند. اگر [شروع کار با Go](/fa/posts/go-getting-started/) و [npm، package.json و قفل وابستگی](/fa/posts/node-npm-package-json/) را خوانده باشید، ایده‌ها آشنا است و فقط اسم‌ها فرق می‌کند.

همه‌چیز با Python 3.14.0 و uv 0.10.9 روی macOS (معماری arm64) و در پوشه‌های موقتی اجرا شده که بعدش پاک کردم. مسیر خانه را به شکل `<home>` نوشته‌ام.

## کدام Python را اجرا می‌کنم

```bash
python3 --version
which python3
```

```
Python 3.14.0
<home>/.pyenv/versions/3.14.0/bin/python3
```

Python من از pyenv می‌آید. اگر پکیج‌ها را مستقیم داخل همین interpreter نصب کنید، همه‌ی پروژه‌های ماشین آن‌ها را مشترکاً می‌بینند و دو پروژه که نسخه‌ی متفاوتی از یک کتاب‌خانه می‌خواهند با هم برخورد می‌کنند. راه‌حل **{{< term "virtual-environment" "محیط مجازی" >}}** (virtual environment) است: پوشه‌ای خصوصی با لینک interpreter و `site-packages` مخصوص خودش.

## venv و pip

```bash
python3 -m venv .venv
source .venv/bin/activate
python -c "import sys; print(sys.prefix); print(sys.base_prefix)"
```

```
<tmp>/pipdemo/.venv
<home>/.pyenv/versions/3.14.0
```

داخل venv مقدار `sys.prefix` به خود venv اشاره می‌کند ولی `sys.base_prefix` هنوز به interpreterی که venv از آن ساخته شده. همین تفاوت نشان می‌دهد Python الان داخل venv است. فایل `.venv/pyvenv.cfg` هم interpreter پایه و `include-system-site-packages = false` را نگه می‌دارد.

محیط تازه تقریباً خالی است:

```bash
pip list
```

```
Package Version
------- -------
pip     25.2
```

با **{{< term "pip" "pip" >}}** یک پکیج از **{{< term "pypi" "PyPI" >}}** نصب می‌کنیم و نتیجه را freeze می‌کنیم:

```bash
pip install requests
pip freeze > requirements.txt
cat requirements.txt
```

```
certifi==2026.10.23
charset-normalizer==3.5.2
idna==3.20
requests==2.34.2
urllib3==2.8.0
```

یک پکیج چهار پکیج دیگر هم آورد و `pip freeze` همه را با نسخه‌ی دقیق فهرست کرد. آزمایش isolation: داخل venv پکیج کوچکی به اسم `cowsay` هم نصب کردم. بیرون از venv:

```
ModuleNotFoundError: No module named 'cowsay'
```

(اول برای همین آزمایش `requests` را امتحان کردم، ولی معلوم شد Python پایه‌ی pyenv من از قبل آن را دارد. دقیقاً همان نشتی‌ای که venv جلویش را می‌گیرد.)

## uv

**{{< term "uv" "uv" >}}** یک ابزار واحد است که نسخه‌ی Python، venv و وابستگی‌ها را مدیریت می‌کند.

```bash
uv --version
uv init
cat .python-version pyproject.toml
```

```
uv 0.10.9 (f675560f3 2026-03-06)
3.14
[project]
name = "uvdemo"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.14"
dependencies = []
```

`uv init` فایل‌های `main.py` و `README.md` و یک مخزن git هم ساخت. **{{< term "pyproject-toml" "pyproject.toml" >}}** متادیتای پروژه و وابستگی‌های مستقیم را نگه می‌دارد و `.python-version` نسخه‌ی interpreter را ثابت می‌کند. حالا یک وابستگی اضافه کنیم:

```bash
uv add cowsay
```

```
Creating virtual environment at: .venv
Resolved 2 packages in 741ms
Installed 1 package in 17ms
 + cowsay==6.1
```

`uv add` پوشه‌ی `.venv` را ساخت، `pyproject.toml` را ویرایش کرد (`dependencies = ["cowsay>=6.1"]`) و `uv.lock` را نوشت، یعنی یک **{{< term "lockfile" "lockfile" >}}**. نگاهی کوتاه به آن:

```toml
[[package]]
name = "cowsay"
version = "6.1"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.pythonhosted.org/.../cowsay-6.1-py3-none-any.whl", hash = "sha256:274b1e6f...", size = 25560, ... },
]
```

نسخه‌ی دقیق، آدرس دانلود و hash. آن را commit کنید تا همه‌ی ماشین‌ها همان بایت‌ها را بگیرند. `uv run` بدون activate کردن چیزی، از محیط پروژه استفاده می‌کند:

```bash
uv run python -c "import cowsay; print(cowsay.char_names[:3])"
```

```
['beavis', 'cheese', 'cow']
```

برای اینکه ثابت شود lock کافی است، `.venv` را پاک کردم و `uv sync` زدم:

```
Creating virtual environment at: .venv
Resolved 2 packages in 0.88ms
Installed 1 package in 2ms
 + cowsay==6.1
```

`uv tree` درخت وابستگی را چاپ می‌کند و `uv python list` interpreterهای پیدا‌شده را نشان می‌دهد (خروجی من 3.14.0 از pyenv، 3.14.7 از Homebrew و چند مورد «download available» داشت). اگر جریان کاری pip را ترجیح می‌دهید، `uv venv` به‌علاوه‌ی `uv pip install cowsay` هم اینجا جواب داد؛ همان ایده‌ی بخش اول است.

ادعا نمی‌کنم uv سریع‌تر است: ماشین هنگام اجرا زیر بار سنگین بود و زمانی اندازه نگرفتم.

## requirements.txt در برابر lock

فایل `requirements.txt` بالا فهرستی تخت از نسخه‌های دقیق است که `pip freeze` ساخت؛ تا وقتی نخواهید، hash ثبت نمی‌کند. `uv.lock` خودکار تولید می‌شود و آدرس و hash را ثبت می‌کند، و `pyproject.toml` کوتاه و دست‌نویس می‌ماند. قاعده‌ی سرانگشتی: شما `pyproject.toml` را ویرایش می‌کنید، ابزار lock را.

| | Go | Node.js | Python (uv) |
|---|---|---|---|
| وابستگی‌های اعلام‌شده | `go.mod` | `package.json` | `pyproject.toml` |
| نسخه‌های دقیق | `go.mod` و `go.sum` | `package-lock.json` | `uv.lock` |
| محل کد وابستگی | cache مشترک ماژول | `node_modules` داخل پروژه | `.venv` داخل پروژه |

برای سمت Go به [پکیج‌ها و ماژول‌ها در Go](/fa/posts/go-packages-modules/) نگاه کنید.

## چند نکته‌ی مهم

- `.venv` را commit نکنید؛ `pyproject.toml`، `uv.lock` و `.python-version` را commit کنید.
- داخل venv مسیرهای مطلق هست، پس جابه‌جا یا تغییر نام پوشه آن را خراب می‌کند. به‌جایش دوباره بسازیدش.
- بدون activate، `python` همان Python سیستم است. `uv run` این سؤال را حذف می‌کند.
- طبق مستندات، خیلی از Pythonهای سیستمی «externally managed» (PEP 668) علامت می‌خورند و `pip install` سراسری را رد می‌کنند. من اینجا به آن برنخوردم.
- اگر import رفتار عجیبی دارد، بعد از activate کردن `which python` را بررسی کنید.

## تمرین

1. با `uv init` پروژه بسازید، `requests` را اضافه کنید و اسکریپتی بنویسید که status یک پاسخ از سرور محلی را چاپ کند.
2. `.venv` را پاک کنید و با `uv sync` دوباره بسازید.
3. همین کار را با `python3 -m venv` و `pip freeze` انجام دهید و دو فایل را مقایسه کنید.

## قدم بعدی

پست بعدی: «نوع‌ها و کنترل جریان در Python». برخلاف Go، نوع‌ها در زمان کامپایل بررسی نمی‌شوند و می‌بینیم در عمل یعنی چه. برای مدلی دیگر از اجرای کد، [event loop در Node.js](/fa/posts/node-event-loop/) را ببینید.
