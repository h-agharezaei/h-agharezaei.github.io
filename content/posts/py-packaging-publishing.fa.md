+++
date = '2027-05-07T10:00:00+03:30'
draft = false
title = 'بسته‌بندی و انتشار پروژه‌ی Python'
description = 'بسته‌بندی Python با uv: چیدمان src، pyproject.toml، uv build، محتوای wheel، entry point، نصب editable، twine check و نسخه‌بندی.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "packaging", "uv", "pyproject", "wheel"]
cover = { image = "/images/covers/py-packaging-publishing.fa.png", alt = "بسته‌بندی و انتشار پروژه‌ی Python", hiddenInSingle = true }
+++

یک پوشه کد Python دارید که روی ماشین خودتان کار می‌کند. همکارتان می‌پرسد: «می‌شود فقط `pip install` کنم؟» الان جواب صادقانه نه است. برای اینکه جواب بله شود، کد به یک نام، یک نسخه، فهرست کتابخانه‌هایی که به آن‌ها وابسته است و یک راه استاندارد نیاز دارد که پوشه را به یک فایل تبدیل کند که نصب‌کننده بفهمد. بسته‌بندی همین است، و همان قدمی است که اسکریپت را به چیزی تبدیل می‌کند که دیگران بتوانند استفاده کنند، چه مثل [پست قبل](/fa/posts/py-sqlalchemy-postgres/) با Postgres حرف بزند چه نه.

در این پست یک بسته‌ی کوچک به نام `greeter` می‌سازم، نگاه می‌کنم `uv build` چه چیزی تولید می‌کند و نتیجه را در یک محیط تمیز نصب می‌کنم. این پست روی [محیط Python: venv و uv](/fa/posts/py-environment-uv-venv/) ساخته شده و از ایده‌های [type hint و mypy](/fa/posts/py-type-hints-mypy/) استفاده می‌کند.

> همه‌چیز را دوباره با uv 0.10.9 و Python 3.14.0 و build backend به نام `uv_build`، در یک نسخه‌ی موقت از دمو و با محیط مجازی یک‌بارمصرف اجرا کردم. **هیچ چیزی جایی آپلود نشد**: اعتبارنامه‌ی PyPI ندارم، پس انتشار هرگز اجرا نشد و فقط توصیفش می‌کنم. دمو یک نمونه‌ی محلی است. چند نصب از cache آفلاین uv آمد.

## ایده‌ی اصلی: یک فایل با دستور ساخت

بسته‌بندی مدرن Python به سه چیز برمی‌گردد:

- فایلی به نام `pyproject.toml` که پروژه را توصیف می‌کند: نام، نسخه، وابستگی‌ها و اینکه کدام ابزار آن را می‌سازد.
- یک **build backend**، ابزاری که این فایل را می‌خواند و فایل‌های قابل‌توزیع را تولید می‌کند. جدول `[build-system]` اسمش را می‌گوید. اینجا `uv_build` است؛ بقیه‌ی رایج‌ها hatchling و setuptools هستند. نصب‌کننده (pip یا uv) لازم نیست بداند پروژه‌ی شما چطور ساخته می‌شود؛ فقط backendی را که نام برده‌اید صدا می‌زند.
- دو نوع فایل خروجی: **wheel**، که آماده است تا درون یک محیط باز شود، و **sdist** (source distribution)، یک آرشیو از کد منبع که پیش از نصب باید ساخته شود.

بقیه‌ی پست همین سه چیز در عمل است.

## چیدمان و pyproject.toml

`uv init --package greeter` پوشه را با چیدمان `src` ساخت. بعد `pyproject.toml` را ویرایش کردم تا این شکل شد:

```toml
[project]
name = "greeter"
version = "0.1.0"
description = "A tiny greeting package used to learn packaging"
readme = "README.md"
requires-python = ">=3.12"
dependencies = ["rich>=13"]

[project.optional-dependencies]
yaml = ["pyyaml>=6"]

[project.scripts]
greeter = "greeter:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["uv_build>=0.10.9,<0.11.0"]
build-backend = "uv_build"
```

جدول به جدول:

- `[project]` کارت شناسایی است. `dependencies` چیزهایی است که کاربر موقع اجرا لازم دارد. `requires-python` می‌گوید بسته کدام نسخه‌های Python را پشتیبانی می‌کند.
- `[project.optional-dependencies]` **extra**ها را تعریف می‌کند، یعنی قابلیت‌های اختیاری. کاربری که پشتیبانی از YAML می‌خواهد `greeter[yaml]` را نصب می‌کند و `pyyaml` هم می‌گیرد؛ بقیه نمی‌گیرند.
- `[project.scripts]` یک فرمان می‌سازد. بعد از نصب، نوشتن `greeter` تابع `main` از ماژول `greeter` را اجرا می‌کند. این یک {{< term "entry-point" "entry point" >}} است.
- `[dependency-groups]` فقط برای خود شماست: ابزارهای توسعه مثل pytest. هرگز وارد metadata منتشرشده نمی‌شود، پس کاربران آن را نمی‌گیرند.
- `[build-system]` نام backend و نسخه‌ای را که برای ساخت لازم است می‌گوید.

منبع‌ها `src/greeter/__init__.py`، یک فایل داده `src/greeter/data/greeting.txt` و یک فایل خالی `py.typed` هستند، نشانه‌ای که به type checkerها می‌گوید بسته type hint دارد. کد نسخه‌ی خودش را از metadata نصب‌شده می‌خواند (`importlib.metadata.version("greeter")`)، پس شماره‌ی نسخه فقط یک جا هست: `pyproject.toml`.

## چرا src/؟

چرا کد را در `src/greeter/` می‌گذاریم و نه فقط `greeter/` کنار `pyproject.toml`؟ هر دو را امتحان کردم. با چیدمان flat، اجرای `python3 -c "import flatpkg"` در ریشه‌ی پروژه بدون نصب هیچ چیز موفق شد، چون پوشه‌ی جاری در مسیر import است. با چیدمان src همان import خطای `ModuleNotFoundError: No module named 'greeter'` داد.

نکته همین است. در چیدمان flat ممکن است تست‌هایتان روی پوشه‌ی کاری پاس شوند و هیچ‌وقت به بسته‌ی نصب‌شده دست نزنند، و فایلی که در بسته جا مانده تا وقتی کاربر گزارش بدهد دیده نمی‌شود. با `src/` کد فقط بعد از نصب قابل import است، پس تست‌ها همان چیزی را آزمایش می‌کنند که کاربر می‌گیرد.

## lock و sync و اجرا

بعد پروژه را مثل یک توسعه‌دهنده به کار بردم. `uv lock` ۱۱ بسته را (با خود `greeter`) در `uv.lock` حل کرد، فایلی با ۱۷۲ خط و ۵۷ هش `sha256`. `uv sync` همه را نصب کرد، با گروه dev. `uv run greeter` عبارت `Hello from a data file (greeter 0.1.0)` را چاپ کرد و `uv run pytest -q` با `1 passed` تمام شد.

{{< term "lockfile" "lockfile" >}} نسخه‌ی دقیق هر وابستگی را ثابت می‌کند، پس یک اپلیکیشن و CI آن هر بار همان چیزها را نصب می‌کنند. کتابخانه آن را منتشر نمی‌کند: کاربران کتابخانه حل وابستگی خودشان را دارند و کتابخانه فقط بازه‌هایی مثل `rich>=13` را اعلام می‌کند.

## ساخت: sdist و wheel

`uv build` دو فایل ساخت که فرق دو قالب را نشان می‌دهند:

- `greeter-0.1.0.tar.gz` (۷۹۷ بایت) همان {{< term "sdist" "sdist" >}} است. `PKG-INFO`، `README.md`، `pyproject.toml` و کل درخت `src/` را دارد. نصب‌کننده باید پیش از نصبش backend را روی آن اجرا کند.
- `greeter-0.1.0-py3-none-any.whl` (۲۱۱۶ بایت) همان {{< term "wheel" "wheel" >}} است. wheel یک فایل ZIP است؛ نصبش یعنی باز کردن فایل‌ها در جای درست، بدون هیچ مرحله‌ی ساخت. برای همین نصب‌کننده‌ها آن را ترجیح می‌دهند.

چون wheel یک ZIP است، `python3 -m zipfile -l` می‌تواند فهرستش کند:

```text
File Name                                             Modified             Size
greeter/                                       1980-01-01 00:00:00            0
greeter/__init__.py                            1980-01-01 00:00:00          287
greeter/data/                                  1980-01-01 00:00:00            0
greeter/data/greeting.txt                      1980-01-01 00:00:00           23
greeter/py.typed                               1980-01-01 00:00:00            0
greeter-0.1.0.dist-info/                       1980-01-01 00:00:00            0
greeter-0.1.0.dist-info/WHEEL                  1980-01-01 00:00:00           80
greeter-0.1.0.dist-info/entry_points.txt       1980-01-01 00:00:00           42
greeter-0.1.0.dist-info/METADATA               1980-01-01 00:00:00          261
greeter-0.1.0.dist-info/RECORD                 1980-01-01 00:00:00          525
```

(تاریخ ۱۹۸۰ یک تاریخ ثابت جایگزین است؛ گمانم این است که برای این آنجاست که دو بار ساخت یک کد فایل‌های یکسان بدهد.) بخش اول کد ماست: ماژول، فایل داده و `py.typed` همگی داخل آمدند. پوشه‌ی `dist-info` metadata بسته است. `METADATA` شامل `Requires-Dist: rich>=13`، `Requires-Dist: pyyaml>=6 ; extra == 'yaml'` و `Provides-Extra: yaml` است، که راهی است که نصب‌کننده از وابستگی‌ها و extraها خبردار می‌شود؛ pytest نیست، همان‌طور که گفتیم. `entry_points.txt` فرمانی را که تعریف کردیم دارد:

```text
[console_scripts]
greeter = greeter:main
```

وقتی wheel نصب شود، نصب‌کننده این را می‌خواند و یک فایل اجرایی به نام `greeter` می‌سازد. `RECORD` هر فایل را با هش و اندازه فهرست می‌کند، مثلاً `greeter/py.typed,sha256=47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU,0`؛ طبق مستندات بسته‌بندی، برای تأیید فایل‌های نصب‌شده و حذف آن‌ها به کار می‌رود.

نام فایل `py3-none-any` از برچسب‌ها ساخته شده: Python 3، بدون ABI خاص، هر سیستم‌عاملی. یعنی این wheel کاملاً Python است و همه‌جا کار می‌کند. طبق مستندات بسته‌بندی، بسته‌ای با extension کامپایل‌شده برچسب‌های مخصوص یک مفسر، ABI و سیستم‌عامل می‌گیرد (مثلاً `cp314-...-macosx_...`)، پس برای هر سیستم‌عامل یک wheel لازم است. اینجا چنین چیزی نساختم؛ [صدا زدن Rust از Python با ctypes و PyO3](/fa/posts/py-ffi-pyo3-ctypes/) جایی است که این مهم می‌شود.

## نصب در یک محیط تازه

آزمون واقعی بسته‌بندی نصب در یک محیط خالی است، پس venv تازه ساختم و wheel را با `uv pip install` نصب کردم. زنجیره‌ی وابستگی یعنی `rich`، `markdown-it-py`، `mdurl` و `pygments` هم آمد و فرمان `greeter` عبارت `Hello from a data file (greeter 0.1.0)` را چاپ کرد. `greeter.__file__` به `<venv>/lib/python3.14/site-packages/` اشاره می‌کرد: یک نسخه‌ی نصب‌شده‌ی واقعی، با فایل داده در داخلش.

وقتی در حال توسعه‌اید نمی‌خواهید بعد از هر ویرایش دوباره نصب کنید. {{< term "editable-install" "editable install" >}} (`uv pip install -e greeter`) همین مشکل را حل می‌کند. بعد از آن `greeter.__file__` به `<demo>/greeter/src/greeter/__init__.py` اشاره می‌کرد، یعنی خود پوشه‌ی منبع، پس ویرایش‌ها فوراً اعمال می‌شوند.

## نسخه‌ها و بررسی‌ها

شماره‌ی نسخه از PEP 440 پیروی می‌کند و قاعده‌هایش را با کتابخانه‌ی `packaging` امتحان کردم. `1.0.0a1`، `1.0.0rc1` و `1.0.0.dev3` پیش‌انتشارند؛ `1.0.0.post1` نیست. از قدیمی به جدید مرتب می‌شوند: `dev3 < a1 < rc1 < 1.0.0 < post1`. مقایسه عددی است: `Version("1.10") > Version("1.9")` برابر `True` است، ولی به‌صورت رشته‌ی ساده `False`. برای اینکه خود عددها چه معنایی داشته باشند از {{< term "semver" "SemVer" >}} پیروی کنید.

پیش از آپلود، `twine check` بررسی می‌کند فایل‌ها سالم‌اند. `uvx twine==6.2.0 check dist/*` برای هر دو فایل `PASSED with warnings` چاپ کرد و هشدار این بود: ``long_description` missing``، چون `README.md` من خالی است. پس ابزار README خالی را می‌بیند، که دقیقاً همان چیزی است که می‌خواهید پیش از اینکه PyPI صفحه‌ی خالی نشان بدهد بشنوید.

## انتشار (اجرا نشد)

`uv publish` فایل‌های `dist/*` را به {{< term "pypi" "PyPI" >}} آپلود می‌کند. تا آنجا که می‌دانم PyPI از trusted publishing با OIDC از CI هم پشتیبانی می‌کند، پس لازم نیست توکن بلندمدت نگه داشت؛ جزئیاتش را در مستندات PyPI ببینید. هیچ‌کدام را اجرا نکردم. دمو یک `Makefile` کوچک با هدف‌های `sync`، `test`، `build` و `check` دارد، فقط برای اینکه فرمان‌ها یک‌جا باشند.

## در مقایسه با npm و Go

بسته‌های npm از `package.json` استفاده می‌کنند ([npm و package.json](/fa/posts/node-npm-package-json/)) و کد منبع یا یک tarball منتشر می‌کنند. ماژول‌های Go ([بسته و ماژول](/fa/posts/go-packages-modules/)) با مسیر import از سیستم کنترل نسخه گرفته می‌شوند و فایل ساخته‌شده‌ی جدایی ندارند. Python یک wheel ساخته‌شده را توزیع می‌کند، و یک sdist برای حالت پشتیبان.

## پیش از انتشار

- از چیدمان src استفاده کنید تا تست‌هایتان روی کد نصب‌شده اجرا شود، نه پوشه‌ی کاری.
- `uv.lock` را برای کتابخانه منتشر نکنید. بازه‌ها را اعلام کنید و بگذارید کاربران حل کنند.
- README را پر کنید، وگرنه `twine` هشدار می‌دهد و صفحه‌ی PyPI شما خالی خواهد بود.
- شماره‌ی نسخه را با دقت انتخاب کنید: تا آنجا که می‌دانم PyPI هرگز اجازه نمی‌دهد یک نام فایل را دوباره آپلود کنید، حتی بعد از حذف انتشار. مستندات PyPI را ببینید.

## تمرین

یک فرمان دوم و یک extra در `[project.optional-dependencies]` اضافه کنید، دوباره بسازید و دو فایل `METADATA` را diff بگیرید.

## قدم بعدی

قدم بعد: «ابزار خط فرمان و اسکریپت‌نویسی با Python»، که برنامه‌ی پشت یک entry point مثل این را می‌نویسد.
