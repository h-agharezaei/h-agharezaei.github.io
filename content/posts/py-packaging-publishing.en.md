+++
date = '2027-05-07T10:00:00+03:30'
draft = false
title = 'Packaging and publishing a Python project'
description = 'Python packaging with uv: src layout, pyproject.toml, uv build, what is inside a wheel, entry points, editable installs, twine check and versions.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "packaging", "uv", "pyproject", "wheel"]
cover = { image = "/images/covers/py-packaging-publishing.png", alt = "Packaging and publishing a Python project", hiddenInSingle = true }
+++

You have a folder of Python code that works on your machine. A colleague asks, "Can I just `pip install` it?" Right now the honest answer is no. To make that answer yes, the code needs a name, a version, a list of the libraries it depends on, and a standard way to turn the folder into one file that an installer understands. That is what packaging is, and it is the step that turns a script into something other people can use, whether it talks to Postgres like [the previous post](/posts/py-sqlalchemy-postgres/) or not.

This post builds a tiny package called `greeter`, looks inside what `uv build` produces, and installs the result into a clean environment. It builds on [The Python environment: venv and uv](/posts/py-environment-uv-venv/) and uses ideas from [Type hints and mypy](/posts/py-type-hints-mypy/).

> I re-ran everything with uv 0.10.9 and Python 3.14.0, build backend `uv_build`, in a scratch copy of the demo with a throwaway environment. **Nothing was uploaded anywhere**: I have no PyPI credentials, so publishing was never run and I only describe it. The demo is a local example. A few of the installs here came from uv's offline cache.

## The core idea: one file with a recipe

Modern Python packaging comes down to three things:

- A file called `pyproject.toml` that describes the project: name, version, dependencies, and which tool builds it.
- A **build backend**, the tool that reads that file and produces the distributable files. The `[build-system]` table names it. Here it is `uv_build`; others you will meet are hatchling and setuptools. The installer (pip or uv) does not need to know how your project is built; it just calls the backend that you named.
- Two kinds of output files: a **wheel**, which is ready to unpack into an environment, and an **sdist** (source distribution), which is a source archive that must be built before it can be installed.

The rest of the post is these three things in practice.

## The layout and pyproject.toml

`uv init --package greeter` generated the folder, using the `src` layout. I then edited `pyproject.toml` until it looked like this:

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

Taking it table by table:

- `[project]` is the identity card. `dependencies` are what users need at run time. `requires-python` says which Python versions the package supports.
- `[project.optional-dependencies]` defines **extras**: optional features. A user who wants YAML support installs `greeter[yaml]` and also gets `pyyaml`; everyone else does not.
- `[project.scripts]` creates a command. After installation, typing `greeter` runs the function `main` from the module `greeter`. This is an {{< term "entry-point" "entry point" >}}.
- `[dependency-groups]` is for you only: tools for development such as pytest. It never goes into the published metadata, so users do not get it.
- `[build-system]` names the backend and the version of it needed to build.

The sources are `src/greeter/__init__.py`, a data file `src/greeter/data/greeting.txt` and an empty file `py.typed`, a marker that tells type checkers the package ships type hints. The code reads its own version from the installed metadata (`importlib.metadata.version("greeter")`), so the version number lives in one place only, `pyproject.toml`.

## Why src/?

Why put the code in `src/greeter/` and not simply `greeter/` next to `pyproject.toml`? I tried both. With a flat layout, running `python3 -c "import flatpkg"` in the project root succeeded without installing anything, because the current directory is on the import path. With the src layout, the same import gave `ModuleNotFoundError: No module named 'greeter'`.

That is the point. With a flat layout your tests may pass against the working folder and never touch the installed package, so a file missing from the package goes unnoticed until a user reports it. With `src/`, the code can only be imported after it is installed, so the tests test what users will get.

## Lock, sync, run

Next I used the project like a developer. `uv lock` resolved 11 packages (including `greeter` itself) into `uv.lock`, a file of 172 lines with 57 `sha256` hashes. `uv sync` installed them, dev group included. `uv run greeter` printed `Hello from a data file (greeter 0.1.0)` and `uv run pytest -q` ended with `1 passed`.

The {{< term "lockfile" "lockfile" >}} pins the exact version of every dependency, so an application and its CI install the same things every time. A library does not publish it: users of a library get their own resolution, and the library only declares ranges such as `rich>=13`.

## Building: sdist and wheel

`uv build` made two files, and they show the difference between the two formats:

- `greeter-0.1.0.tar.gz` (797 bytes) is the {{< term "sdist" "sdist" >}}. It holds `PKG-INFO`, `README.md`, `pyproject.toml` and the whole `src/` tree. An installer must run the build backend on it before it can install it.
- `greeter-0.1.0-py3-none-any.whl` (2116 bytes) is the {{< term "wheel" "wheel" >}}. A wheel is a ZIP file; installing it means unpacking the files into the right places, with no build step. That is why installers prefer it.

Since a wheel is a ZIP, `python3 -m zipfile -l` can list it:

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

(The modification date 1980 is a fixed placeholder date; I believe it is there so that two builds of the same code give identical files.) The first part is our code: the module, the data file and `py.typed` all made it in. The `dist-info` folder is the package's metadata. `METADATA` contains `Requires-Dist: rich>=13`, `Requires-Dist: pyyaml>=6 ; extra == 'yaml'` and `Provides-Extra: yaml`, which is how the installer learns about dependencies and extras; pytest is absent, as promised. `entry_points.txt` holds the command we declared:

```text
[console_scripts]
greeter = greeter:main
```

When the wheel is installed, the installer reads this and creates an executable named `greeter`. `RECORD` lists every file with its hash and size, for example `greeter/py.typed,sha256=47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU,0`; according to the packaging docs, it is used to verify the installed files and to uninstall them.

The file name `py3-none-any` is made of tags: Python 3, no specific ABI, any platform. It means this wheel is pure Python and works everywhere. According to the packaging docs, a package with compiled extensions gets tags for a specific interpreter, ABI and platform (for example `cp314-...-macosx_...`), so you need one wheel per platform. I did not build one here; [Calling Rust from Python with ctypes and PyO3](/posts/py-ffi-pyo3-ctypes/) is the case where it matters.

## Install into a fresh environment

The real test of packaging is installing into an empty environment, so I made a new venv and installed the wheel with `uv pip install`. It pulled in the dependency chain, `rich`, `markdown-it-py`, `mdurl` and `pygments`, and the `greeter` command printed `Hello from a data file (greeter 0.1.0)`. `greeter.__file__` pointed into `<venv>/lib/python3.14/site-packages/`: a real installed copy, with the data file inside.

While developing, you do not want to reinstall after every edit. An {{< term "editable-install" "editable install" >}} (`uv pip install -e greeter`) solves that. After it, `greeter.__file__` pointed to `<demo>/greeter/src/greeter/__init__.py`, the source folder itself, so edits apply immediately.

## Versions and checks

Version numbers follow PEP 440, and I checked its rules with the `packaging` library. `1.0.0a1`, `1.0.0rc1` and `1.0.0.dev3` are pre-releases; `1.0.0.post1` is not. Sorted from oldest to newest they go `dev3 < a1 < rc1 < 1.0.0 < post1`. Comparison is numeric: `Version("1.10") > Version("1.9")` is `True`, while as plain strings it is `False`. For what the numbers should mean, follow {{< term "semver" "SemVer" >}}.

Before uploading, `twine check` verifies that the files are well formed. `uvx twine==6.2.0 check dist/*` printed `PASSED with warnings` for both files, and the warning was ``long_description` missing``: my `README.md` is empty. So the tool does notice an empty README, which is exactly what you want to hear before PyPI shows an empty page.

## Publishing (not run)

`uv publish` uploads `dist/*` to {{< term "pypi" "PyPI" >}}. As far as I know, PyPI also supports trusted publishing through OIDC from CI, so no long-lived token has to be stored; check the PyPI docs for the details. I did not run any of it. The demo has a small `Makefile` with targets `sync`, `test`, `build` and `check`, just to keep the commands in one place.

## Versus npm and Go

npm packages use `package.json` ([npm and package.json](/posts/node-npm-package-json/)) and publish source or a tarball. Go modules ([Packages and modules](/posts/go-packages-modules/)) are fetched by import path from version control, with no separate build artifact. Python distributes a built wheel, plus an sdist as the fallback.

## Before you publish

- Use the src layout so your tests run against the installed code, not the working folder.
- Do not publish `uv.lock` for libraries. Declare ranges and let users resolve them.
- Fill in the README, or `twine` warns you and your PyPI page will be empty.
- Choose version numbers carefully: as far as I know, PyPI never lets you upload the same file name again, even after deleting a release. Check the PyPI docs.

## Exercise

Add a second command and a `[project.optional-dependencies]` extra, rebuild, and diff the two `METADATA` files.

## What's next

Next is "Command-line tools and scripts with Python", which writes the program behind an entry point like the one built here.
