+++
date = '2027-05-07T10:00:00+03:30'
draft = false
title = 'بسته‌بندی و انتشار پروژه‌ی Python'
description = 'بسته‌بندی Python با uv: چیدمان src، pyproject.toml، uv build، محتوای wheel، entry point، نصب editable، twine check و نسخه‌بندی.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "packaging", "uv", "pyproject", "wheel"]
cover = { image = "/images/covers/py-packaging-publishing.fa.png", alt = "بسته‌بندی و انتشار پروژه‌ی Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-sqlalchemy-postgres/) از Python با Postgres حرف زدیم. کد وقتی برای دیگران مفید می‌شود که نصب‌شدنی باشد. در این مقاله یک بسته‌ی کوچک می‌سازیم، داخل خروجی `uv build` را نگاه می‌کنیم و آن را در یک محیط تمیز نصب می‌کنیم. این مقاله ادامه‌ی [محیط Python: venv و uv](/fa/posts/py-environment-uv-venv/) است و از [type hint و mypy](/fa/posts/py-type-hints-mypy/) هم استفاده می‌کند.

> uv 0.10.9، Python 3.14.0، build backend به نام `uv_build`، در یک پوشه‌ی موقت. **هیچ چیزی جایی آپلود نشد**: اعتبارنامه‌ی PyPI ندارم، پس انتشار اجرا نشد و فقط توصیفش می‌کنم. دمو یک نمونه‌ی محلی است.

## چیدمان و pyproject.toml

`uv init --package greeter` چیدمان `src` ساخت و من `pyproject.toml` را ویرایش کردم:

```toml
[project]
name = "greeter"
version = "0.1.0"
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

سورس‌ها `src/greeter/__init__.py`، `data/greeting.txt` و یک فایل خالی `py.typed` هستند که به type checker می‌گوید بسته type hint دارد. extra (مثل `greeter[yaml]`) قابلیت اختیاری است که کاربر می‌تواند بخواهد. dependency group فقط برای خود شماست و هرگز وارد metadata منتشرشده نمی‌شود.

چرا `src/`؟ در چیدمان flat، دستور `python3 -c "import flatpkg"` در ریشه‌ی پروژه بدون نصب موفق شد، چون پوشه‌ی جاری در path است. با چیدمان src همان import خطای `ModuleNotFoundError` داد. پس تست‌ها باید روی بسته‌ی نصب‌شده اجرا شوند، نه روی نسخه‌ی کاری.

## lock، sync، run

`uv lock` یازده بسته را در `uv.lock` حل کرد (۱۷۲ خط، ۵۷ hash از نوع `sha256`). `uv sync` همه را با گروه dev نصب کرد، `uv run greeter` عبارت `Hello from a data file (greeter 0.1.0)` را چاپ کرد و `uv run pytest -q` نتیجه‌ی `1 passed` داد. {{< term "lockfile" "lockfile" >}} برای اپلیکیشن و CI است. کتابخانه فقط بازه‌ی نسخه‌ها را منتشر می‌کند، نه `uv.lock`.

## ساخت

`uv build` دو فایل ساخت: `greeter-0.1.0.tar.gz` (۷۹۷ بایت) و `greeter-0.1.0-py3-none-any.whl` (۲۱۱۶ بایت). {{< term "sdist" "sdist" >}} شامل `README.md`، `pyproject.toml`، `PKG-INFO` و درخت `src/` است. {{< term "wheel" "wheel" >}} یک zip است؛ `python3 -m zipfile -l` این را فهرست کرد:

```text
greeter/__init__.py
greeter/data/greeting.txt
greeter/py.typed
greeter-0.1.0.dist-info/WHEEL
greeter-0.1.0.dist-info/entry_points.txt
greeter-0.1.0.dist-info/METADATA
greeter-0.1.0.dist-info/RECORD
```

فایل داده و `py.typed` داخل آن آمدند. `METADATA` شامل `Requires-Dist: rich>=13`، `Requires-Dist: pyyaml>=6 ; extra == 'yaml'` و `Provides-Extra: yaml` است؛ pytest در آن نیست. `entry_points.txt` همان {{< term "entry-point" "entry point" >}} را دارد:

```text
[console_scripts]
greeter = greeter:main
```

`RECORD` هر فایل را با hash و اندازه فهرست می‌کند، مثلاً `greeter/py.typed,sha256=47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU,0`.

برچسب `py3-none-any` یعنی: Python 3، بدون ABI خاص، هر پلتفرم؛ یعنی Python خالص. طبق مستندات packaging، بسته‌ای با extension کامپایل‌شده برچسب مخصوص یک مفسر، ABI و پلتفرم می‌گیرد (مثل `cp314-...-macosx_...`) و برای هر پلتفرم یک wheel لازم است. اینجا چنین wheel ‌ای نساختم.

## نصب در venv تازه

در یک venv خالی، `uv pip install` روی wheel بسته‌های `rich`، `markdown-it-py`، `mdurl` و `pygments` را هم آورد. دستور `greeter` عبارت `Hello from a data file (greeter 0.1.0)` را چاپ کرد و `greeter.__file__` به `<venv>/lib/python3.14/site-packages/` اشاره می‌کرد. نسخه از `importlib.metadata.version("greeter")` می‌آید، پس فقط یک منبع دارد: `pyproject.toml`.

{{< term "editable-install" "نصب editable" >}} (`uv pip install -e greeter`) جایگزین آن شد و `__file__` حالا `<demo>/greeter/src/greeter/__init__.py` بود: تغییرها بدون نصب دوباره اعمال می‌شوند.

## نسخه و بررسی

PEP 440 با `packaging.version` بررسی شد: `1.0.0a1`، `1.0.0rc1` و `1.0.0.dev3` پیش‌انتشارند؛ `1.0.0.post1` نیست. ترتیب: `dev3 < a1 < rc1 < 1.0.0 < post1`. مقایسه عددی است (`Version("1.10") > Version("1.9")` درست است؛ به‌صورت رشته نادرست). برای معنا از {{< term "semver" "SemVer" >}} پیروی کنید.

`uvx twine==6.2.0 check dist/*` برای هر دو فایل PASSED چاپ کرد، با هشدار ``long_description` missing`: README من خالی بود.

## انتشار (اجرا نشد)

`uv publish` فایل‌های `dist/*` را روی {{< term "pypi" "PyPI" >}} آپلود می‌کند. تا جایی که می‌دانم PyPI از trusted publishing با OIDC از CI هم پشتیبانی می‌کند تا توکن بلندمدت ذخیره نشود؛ مستندات PyPI را ببینید. هیچ‌کدام را اجرا نکردم. یک `Makefile` دستورهای `sync`، `test`، `build` و `check` را جمع کرد.

## در مقایسه با npm و Go

بسته‌های npm از `package.json` استفاده می‌کنند ([npm و package.json](/fa/posts/node-npm-package-json/)). ماژول‌های Go ([package و module](/fa/posts/go-packages-modules/)) با import path از سیستم کنترل نسخه گرفته می‌شوند و artifact ساخت جدا ندارند. Python یک wheel ساخته‌شده توزیع می‌کند، به‌علاوه‌ی sdist.

## چند نکته‌ی مهم

- از چیدمان src استفاده کنید تا تست‌ها کد نصب‌شده را بزنند.
- `uv.lock` را برای کتابخانه منتشر نکنید.
- README را پر کنید وگرنه `twine` هشدار می‌دهد.
- تا جایی که می‌دانم نسخه‌ی آپلودشده در PyPI تغییرناپذیر است.

## تمرین

یک دستور دوم و یک extra در `[project.optional-dependencies]` اضافه کنید، دوباره build کنید و دو `METADATA` را diff بگیرید.

## قدم بعدی

مقاله‌ی بعد «ابزار خط فرمان و اسکریپت‌نویسی با Python» است.
