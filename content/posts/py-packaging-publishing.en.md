+++
date = '2027-05-07T10:00:00+03:30'
draft = false
title = 'Packaging and publishing a Python project'
description = 'Python packaging with uv: src layout, pyproject.toml, uv build, what is inside a wheel, entry points, editable installs, twine check and versions.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "packaging", "uv", "pyproject", "wheel"]
cover = { image = "/images/covers/py-packaging-publishing.png", alt = "Packaging and publishing a Python project", hiddenInSingle = true }
+++

In the [previous post](/posts/py-sqlalchemy-postgres/) we talked to Postgres from Python. Code only becomes useful to others once it can be installed. This post builds a tiny package, looks inside what `uv build` produces, and installs it into a clean environment. It builds on [the Python environment: venv and uv](/posts/py-environment-uv-venv/) and uses ideas from [type hints and mypy](/posts/py-type-hints-mypy/).

> uv 0.10.9, Python 3.14.0, build backend `uv_build`, in a throwaway directory. **Nothing was uploaded** anywhere: I have no PyPI credentials, so publishing was not run and I only describe it. The demo is a local example.

## The layout and pyproject.toml

`uv init --package greeter` generated a `src` layout. I then edited `pyproject.toml`:

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

The sources are `src/greeter/__init__.py`, `data/greeting.txt` and an empty `py.typed` marker, which tells type checkers the package ships type hints. Extras (`greeter[yaml]`) are optional features users can ask for. A dependency group is for you only: it never goes into the published metadata.

Why `src/`? With a flat layout, `python3 -c "import flatpkg"` in the project root succeeded without installing anything, because the current directory is on the path. With the src layout the same import gave `ModuleNotFoundError`. So tests must run against the installed package, not the working copy.

## Lock, sync, run

`uv lock` resolved 11 packages into `uv.lock` (172 lines, 57 `sha256` hashes). `uv sync` installed them including the dev group, `uv run greeter` printed `Hello from a data file (greeter 0.1.0)` and `uv run pytest -q` gave `1 passed`. The {{< term "lockfile" "lockfile" >}} is for applications and CI. A library publishes only its ranges, not `uv.lock`.

## Building

`uv build` made two files: `greeter-0.1.0.tar.gz` (797 bytes) and `greeter-0.1.0-py3-none-any.whl` (2116 bytes). The {{< term "sdist" "sdist" >}} holds `README.md`, `pyproject.toml`, `PKG-INFO` and the `src/` tree. The {{< term "wheel" "wheel" >}} is a zip; `python3 -m zipfile -l` lists:

```text
greeter/__init__.py
greeter/data/greeting.txt
greeter/py.typed
greeter-0.1.0.dist-info/WHEEL
greeter-0.1.0.dist-info/entry_points.txt
greeter-0.1.0.dist-info/METADATA
greeter-0.1.0.dist-info/RECORD
```

The data file and `py.typed` made it in. `METADATA` contains `Requires-Dist: rich>=13`, `Requires-Dist: pyyaml>=6 ; extra == 'yaml'` and `Provides-Extra: yaml`; pytest is absent. `entry_points.txt` holds the {{< term "entry-point" "entry point" >}}:

```text
[console_scripts]
greeter = greeter:main
```

`RECORD` lists each file with its hash and size, for example `greeter/py.typed,sha256=47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU,0`.

The filename tag `py3-none-any` means: Python 3, no specific ABI, any platform. It is pure Python. According to the packaging docs, a package with compiled extensions gets tags for a specific interpreter, ABI and platform (for example `cp314-...-macosx_...`), so one wheel per platform is needed. I did not build one here.

## Install into a fresh venv

In a new empty venv, `uv pip install` of the wheel pulled in `rich`, `markdown-it-py`, `mdurl` and `pygments`. The `greeter` command printed `Hello from a data file (greeter 0.1.0)`, and `greeter.__file__` pointed into `<venv>/lib/python3.14/site-packages/`. The version comes from `importlib.metadata.version("greeter")`, so it has one source: `pyproject.toml`.

An {{< term "editable-install" "editable install" >}} (`uv pip install -e greeter`) replaced it, and `__file__` now pointed to `<demo>/greeter/src/greeter/__init__.py`: edits apply without reinstalling.

## Versions and checks

PEP 440 verified with `packaging.version`: `1.0.0a1`, `1.0.0rc1` and `1.0.0.dev3` are pre-releases; `1.0.0.post1` is not. Sorted: `dev3 < a1 < rc1 < 1.0.0 < post1`. Comparison is numeric (`Version("1.10") > Version("1.9")` is True; as strings it is False). Follow {{< term "semver" "SemVer" >}} for meaning.

`uvx twine==6.2.0 check dist/*` printed PASSED for both files, with the warning ``long_description` missing`: my README was empty.

## Publishing (not run)

`uv publish` uploads `dist/*` to {{< term "pypi" "PyPI" >}}. As far as I know, PyPI also supports trusted publishing through OIDC from CI, so no long-lived token is stored; check the PyPI docs. I did not run any of it. A `Makefile` wrapped `sync`, `test`, `build` and `check`.

## Versus npm and Go

npm packages use `package.json` ([npm and package.json](/posts/node-npm-package-json/)) and publish source or a tarball. Go modules ([packages and modules](/posts/go-packages-modules/)) are fetched by import path from version control, with no separate build artifact. Python distributes a built wheel, plus an sdist.

## A few things to watch

- Use the src layout so tests hit the installed code.
- Do not publish `uv.lock` for libraries.
- Fill in the README, or `twine` warns.
- Versions are immutable on PyPI once uploaded, as far as I know.

## Exercise

Add a second command and a `[project.optional-dependencies]` extra, rebuild, and diff the two `METADATA` files.

## What's next

The next post is "Command-line tools and scripts with Python".
