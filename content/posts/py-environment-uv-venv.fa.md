+++
date = '2027-01-08T10:00:00+03:30'
draft = false
title = 'محیط Python: venv و uv'
description = 'محیط مجازی Python با venv و uv: نصب با pip، requirements.txt، pyproject.toml، uv.lock و uv sync، همه با اجرای واقعی.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "venv", "uv", "pip", "beginner"]
cover = { image = "/images/covers/py-environment-uv-venv.fa.png", alt = "محیط Python: venv و uv", hiddenInSingle = true }
+++

دو پروژه‌ی کوچک روی یک لپ‌تاپ دارید. اولی نسخه‌ی ۱ از یک کتاب‌خانه را می‌خواهد و دومی نسخه‌ی ۲ را. کتاب‌خانه را برای پروژه‌ی اول نصب می‌کنید، بعد برای دومی، و حالا اولی خراب شده. هیچ‌کدام از دو پروژه اشتباهی ندارند. فقط یک جا را برای نگه‌داشتن کتاب‌خانه‌ها با هم شریک‌اند، و یک جا از هر کتاب‌خانه فقط یک نسخه را نگه می‌دارد.

مشکلی که **محیط مجازی** (virtual environment) در Python حل می‌کند همین است، و همین‌جاست که آمدن به Python از Go یا Node.js قبل از هر سینتکسی حس متفاوتی دارد. Go ماژول‌ها را در یک cache مشترک نگه می‌دارد و نسخه‌ها را با `go.mod` برای هر پروژه انتخاب می‌کند. Node برای هر پروژه یک پوشه‌ی `node_modules` جدا می‌گذارد. پیش‌فرض Python بیشتر شبیه یک پوشه‌ی مشترک است، برای همین دنیای Python راهی ساخته که به هر پروژه یک جای خودش بدهد: همان محیط مجازی. این پست آن را توضیح می‌دهد، هم راه قدیمی‌تر (`venv` و `pip`) و هم راه تازه‌تر (`uv`). اگر [شروع کار با Go](/fa/posts/go-getting-started/) و [npm، package.json و قفل وابستگی](/fa/posts/node-npm-package-json/) را خوانده باشید، ایده‌ها آشنا است و فقط اسم‌ها فرق می‌کند.

باید اعتراف کنم من خودم چطور فهمیدم این موضوع مهم است. اولین تلاشم برای نشان دادن جداسازی venv شکست خورد: `requests` بیرون از آن هم import شد، چون Python پایه‌ی pyenv من از قبل داشتش. وقتی برای این پست دوباره اجرا کردم، interpreter پایه‌ی این ماشین هنوز `requests` داشت (نسخه‌ی 2.32.5)، برای همین در آزمایش جداسازی پایین از یک پکیج کوچک به اسم `cowsay` استفاده می‌کنم.

> همه‌چیز با Python 3.14.0 و uv 0.10.9 روی macOS (معماری arm64) و در پوشه‌های موقتی اجرا شده که بعدش پاک کردم. مسیر خانه را به شکل `<home>` و پوشه‌ی موقت را `<tmp>` نوشته‌ام. چند عدد میلی‌ثانیه از اجرای اول است و در هر اجرا فرق می‌کند؛ هیچ زمانی اندازه نگرفتم و ادعا نمی‌کنم یک ابزار سریع‌تر است.

## کدام Python را اجرا می‌کنم

ممکن است روی ماشین شما چند Python باشد: یکی از سیستم، یکی از Homebrew، یکی از یک مدیر نسخه مثل pyenv. اول ببینید دستور `python3` کدام را می‌گوید:

```bash
python3 --version
which python3
```

```
Python 3.14.0
<home>/.pyenv/versions/3.14.0/bin/python3
```

Python من از pyenv می‌آید. هر نصب Python پوشه‌ای دارد به اسم {{< term "site-packages" "site-packages" >}} و `pip install` کتاب‌خانه‌ها را همان‌جا می‌گذارد. اگر پکیج‌ها را مستقیم داخل همین interpreter نصب کنید، همه‌ی پروژه‌هایی که از آن استفاده می‌کنند همان پوشه را می‌بینند. دو پروژه که نسخه‌ی متفاوتی از یک کتاب‌خانه می‌خواهند آن‌وقت با هم برخورد می‌کنند، دقیقاً مثل داستان بالا.

راه‌حل {{< term "virtual-environment" "محیط مجازی" >}} است: پوشه‌ای خصوصی، معمولاً با اسم `.venv`، که یک لینک به interpreter و `site-packages` خالی مخصوص خودش دارد. داخل محیط نصب کنید و پکیج‌ها داخل همان پروژه می‌مانند.

## venv و pip

Python ماژول `venv` را همراه خودش دارد، پس نصب چیزی لازم نیست. این دستورها یک محیط در `.venv` می‌سازد و آن را فعال می‌کند:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -c "import sys; print(sys.prefix); print(sys.base_prefix)"
```

```
<tmp>/pipdemo/.venv
<home>/.pyenv/versions/3.14.0
```

«فعال‌کردن» معنی ساده‌ای دارد: shell پوشه‌ی `.venv/bin` را جلوی `PATH` می‌گذارد، پس `python` و `pip` حالا یعنی نسخه‌های داخل محیط. بعد از فعال‌کردن، `which python` مقدار `<tmp>/pipdemo/.venv/bin/python` را چاپ کرد.

دو خط خروجی نشان می‌دهند خود Python از کجا می‌فهمد داخل venv است. `sys.prefix` به خود venv اشاره می‌کند ولی `sys.base_prefix` هنوز به interpreterی که venv از آن ساخته شده. اگر فرق داشته باشند، داخل venv هستید. فایل `.venv/pyvenv.cfg` interpreter پایه و خطی به شکل `include-system-site-packages = false` را نگه می‌دارد، یعنی «پکیج‌های interpreter پایه را نبین».

محیط تازه تقریباً خالی است:

```bash
pip list
```

```
Package Version
------- -------
pip     25.2
```

حالا با {{< term "pip" "pip" >}} یک پکیج از {{< term "pypi" "PyPI" >}}، فهرست عمومی پکیج‌ها، نصب می‌کنیم و آنچه نصب شد را با `pip freeze` ذخیره می‌کنیم:

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

یک پکیج خواستم و پنج خط گرفتم. `requests` به چهار پکیج دیگر وابسته است و pip آن‌ها را هم نصب کرد. `pip freeze` همه‌چیز داخل محیط را با نسخه‌ی دقیق (`==`) فهرست می‌کند، پس فایل مجموعه‌ی کامل را ثبت می‌کند. (نسخه‌ها همان چیزی است که اولین بار که این را اجرا کردم در PyPI بود. امروز اتصال من به PyPI مدام timeout می‌داد و `pip install requests` هیچ‌وقت تمام نشد، برای همین این فهرست از اجرای اول است. بررسی کردم که با نصب `requests` از یک cache محلی با `uv pip install` همین پنج نسخه‌ی دقیق به دست می‌آید. نصب `cowsay` با pip در ادامه امروز جواب داد.)

حالا آزمایش جداسازی. داخل venv یک پکیج کوچک به اسم `cowsay` نصب کردم و import کردم؛ کار کرد. بعد با `deactivate` از venv بیرون آمدم و Python پایه را اجرا کردم:

```bash
python3 -I -c "import cowsay"
```

```
ModuleNotFoundError: No module named 'cowsay'
```

Python پایه آن را نمی‌بیند. پکیج فقط داخل `.venv` است و کل مقصود همین است. (گزینه‌ی `-I` Python را در حالت ایزوله اجرا می‌کند تا تنظیمات shell من چیزی را عوض نکند.)

## uv

`venv`، `pip` و `pip freeze` سه قدم جدا هستند و خود نسخه‌ی Python هم چیز چهارمی است که pyenv یا سیستم مدیریت می‌کند. {{< term "uv" "uv" >}} یک ابزار واحد است که نسخه‌ی Python، محیط و وابستگی‌ها را با هم مدیریت می‌کند. یک پروژه شروع کنیم:

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

`uv init` چند فایل ساخت: `main.py`، `README.md`، یک مخزن git، و دو فایلی که بالا چاپ شد. {{< term "pyproject-toml" "pyproject.toml" >}} متادیتای پروژه و وابستگی‌های مستقیمش را نگه می‌دارد (فعلاً فهرست خالی است) و `.python-version` ثابت می‌کند پروژه از کدام interpreter استفاده کند. حالا یک وابستگی اضافه کنیم:

```bash
uv add cowsay
```

```
Creating virtual environment at: .venv
Resolved 2 packages in 741ms
Installed 1 package in 17ms
 + cowsay==6.1
```

یک دستور چند کار کرد. `.venv` را ساخت (هیچ‌وقت خودتان `venv` را اجرا نکردید)، `cowsay` را به `pyproject.toml` اضافه کرد (`dependencies = ["cowsay>=6.1"]`)، نصبش کرد و فایلی به اسم `uv.lock` نوشت، یعنی یک {{< term "lockfile" "lockfile" >}}. عبارت «Resolved 2 packages» خود پروژه را به‌علاوه‌ی `cowsay` می‌شمارد. این زمان‌ها از اجرای اول است و هر بار فرق می‌کند. نگاهی کوتاه به فایل lock:

```toml
[[package]]
name = "cowsay"
version = "6.1"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.pythonhosted.org/.../cowsay-6.1-py3-none-any.whl", hash = "sha256:274b1e6f...", size = 25560, ... },
]
```

نسخه‌ی دقیق، محل دانلود و hash فایل را ثبت می‌کند. آن را commit کنید تا هر ماشینی که از روی آن نصب می‌کند همان بایت‌ها را بگیرد. `uv run` یک دستور را داخل محیط پروژه اجرا می‌کند، پس لازم نیست چیزی را فعال کنید:

```bash
uv run python -c "import cowsay; print(cowsay.char_names[:3])"
```

```
['beavis', 'cheese', 'cow']
```

برای نشان دادن اینکه فایل lock برای ساختن دوباره‌ی محیط کافی است، `.venv` را پاک کردم و `uv sync` زدم، که محیط را با فایل lock هماهنگ می‌کند:

```
Creating virtual environment at: .venv
Resolved 2 packages in 0.88ms
Installed 1 package in 2ms
 + cowsay==6.1
```

محیط با همان `cowsay==6.1` برگشت. دو دستور دیگر هم به دانستنش می‌ارزد: `uv tree` درخت وابستگی را چاپ می‌کند (اینجا `uvdemo v0.1.0` با `cowsay v6.1` زیرش) و `uv python list` interpreterهایی را نشان می‌دهد که uv روی ماشین پیدا کرده (در مورد من 3.14.0 از pyenv، 3.14.7 از Homebrew و چند مورد با برچسب «download available»). اگر جریان کاری به سبک pip را ترجیح می‌دهید، `uv venv` به‌علاوه‌ی `uv pip install cowsay` هم اینجا جواب داد؛ همان ایده‌ی بخش قبل با یک رابط دیگر است.

## requirements.txt در برابر فایل lock

`requirements.txt`ی که بالا ساختم فهرستی تخت از نسخه‌های دقیق است که `pip freeze` نوشت. تا وقتی نخواهید hash فایل‌ها را ثبت نمی‌کند، و پکیج‌هایی که خودتان انتخاب کردید را با پکیج‌هایی که آن‌ها آورده‌اند قاطی می‌کند، پس بعداً نمی‌توانید بگویید کدام کدام است. `uv.lock` را خود ابزار تولید می‌کند، آدرس و hash را ثبت می‌کند، و `pyproject.toml` کوتاه و دست‌نویس می‌ماند و فقط وابستگی‌هایی را دارد که واقعاً خواسته‌اید. قاعده‌ی سرانگشتی: شما `pyproject.toml` را ویرایش می‌کنید و ابزار lock را.

این‌طور با چیزهایی که می‌شناسید تطبیق می‌کند:

| | Go | Node.js | Python (uv) |
|---|---|---|---|
| وابستگی‌های اعلام‌شده | `go.mod` | `package.json` | `pyproject.toml` |
| نسخه‌های دقیق | `go.mod` و `go.sum` | `package-lock.json` | `uv.lock` |
| محل کد وابستگی | cache مشترک ماژول | `node_modules` داخل پروژه | `.venv` داخل پروژه |

برای سمت Go به [پکیج‌ها و ماژول‌ها در Go](/fa/posts/go-packages-modules/) نگاه کنید.

## دام‌های محیط و venv

- **چه چیزی commit شود.** `.venv` را commit نکنید؛ دوباره ساخته می‌شود. `pyproject.toml`، `uv.lock` و `.python-version` را commit کنید، چون پروژه را توصیف می‌کنند.
- **جابه‌جایی پوشه.** داخل venv مسیرهای مطلق هست، پس جابه‌جا کردن یا تغییر نام پوشه‌ی پروژه آن را خراب می‌کند. به‌جای تعمیر، دوباره بسازیدش.
- **فراموش‌کردن activate.** بدون فعال‌کردن، `python` هنوز همان Python سیستم است و پکیج‌هایتان «گم می‌شوند». `uv run` این سؤال را حذف می‌کند، چون همیشه از محیط پروژه استفاده می‌کند.
- **Pythonهای externally managed.** طبق مستندات، خیلی از Pythonهای سیستمی «externally managed» (PEP 668) علامت می‌خورند و `pip install` سراسری را رد می‌کنند، پس آنجا venv راه مورد انتظار است. من اینجا به آن برنخوردم.
- **importهای عجیب.** اگر import رفتار عجیبی دارد، بعد از activate کردن `which python` را اجرا کنید تا ببینید واقعاً از کدام interpreter استفاده می‌کنید.

## تمرین

1. با `uv init` پروژه بسازید، `requests` را اضافه کنید و اسکریپتی بنویسید که status یک پاسخ از سرور محلی را چاپ کند.
2. `.venv` را پاک کنید و با `uv sync` دوباره بسازید.
3. همین کار را با `python3 -m venv` و `pip freeze` انجام دهید و دو فایل را مقایسه کنید.

## قدم بعدی

پست بعدی «نوع‌ها و کنترل جریان در Python» است. برخلاف Go، نوع‌ها در زمان کامپایل بررسی نمی‌شوند و می‌بینیم در عمل یعنی چه. برای مدلی دیگر از اجرای کد، [event loop در Node.js](/fa/posts/node-event-loop/) را ببینید.
