+++
date = '2027-01-08T10:00:00+03:30'
draft = false
title = 'The Python environment: venv and uv'
description = 'Python virtual environments with venv and uv: pip install, requirements.txt, pyproject.toml, uv.lock and uv sync, all shown with real runs.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "venv", "uv", "pip", "beginner"]
cover = { image = "/images/covers/py-environment-uv-venv.png", alt = "The Python environment: venv and uv", hiddenInSingle = true }
+++

This is the first post of a **Python** series for backend engineers who already write Go and Node.js. Before any syntax, we need the part that bites newcomers first: where Python lives on your machine, and where your dependencies go. If you read [Getting started with Go](/posts/go-getting-started/) and [npm, package.json and lockfiles](/posts/node-npm-package-json/), the ideas will feel familiar, only the names change.

Everything below was run with Python 3.14.0 and uv 0.10.9 on macOS (arm64), in throwaway directories that I deleted afterwards. Home paths are shown as `<home>`.

## Which Python am I running

```bash
python3 --version
which python3
```

```
Python 3.14.0
<home>/.pyenv/versions/3.14.0/bin/python3
```

Mine comes from pyenv. If you install packages straight into this interpreter, every project on the machine shares them, and two projects needing different versions of one library collide. The fix is a {{< term "virtual-environment" "virtual environment" >}}: a private folder with its own interpreter link and its own `site-packages`.

## venv and pip

```bash
python3 -m venv .venv
source .venv/bin/activate
python -c "import sys; print(sys.prefix); print(sys.base_prefix)"
```

```
<tmp>/pipdemo/.venv
<home>/.pyenv/versions/3.14.0
```

Inside a venv `sys.prefix` points at the venv, while `sys.base_prefix` still points at the interpreter it was made from. That difference is how Python knows it is in a venv. The `.venv/pyvenv.cfg` file records the base interpreter and `include-system-site-packages = false`.

A fresh environment holds almost nothing:

```bash
pip list
```

```
Package Version
------- -------
pip     25.2
```

Install a package from {{< term "pypi" "PyPI" >}} with {{< term "pip" "pip" >}} and freeze the result:

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

One package brought four others, and `pip freeze` lists all of them pinned. Isolation check: I also installed a tiny package called `cowsay` inside the venv. Outside the venv:

```
ModuleNotFoundError: No module named 'cowsay'
```

(I first tried `requests` for this check, but it turned out my pyenv Python already had it. That is exactly the kind of leak a venv prevents.)

## uv

{{< term "uv" "uv" >}} is a single tool that manages the Python version, the venv and dependencies.

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

`uv init` also created `main.py`, `README.md` and a git repository. {{< term "pyproject-toml" "pyproject.toml" >}} holds project metadata and direct dependencies; `.python-version` pins the interpreter. Now add a dependency:

```bash
uv add cowsay
```

```
Creating virtual environment at: .venv
Resolved 2 packages in 741ms
Installed 1 package in 17ms
 + cowsay==6.1
```

`uv add` created `.venv`, edited `pyproject.toml` (`dependencies = ["cowsay>=6.1"]`) and wrote `uv.lock`, a {{< term "lockfile" "lockfile" >}}. A trimmed look:

```toml
[[package]]
name = "cowsay"
version = "6.1"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.pythonhosted.org/.../cowsay-6.1-py3-none-any.whl", hash = "sha256:274b1e6f...", size = 25560, ... },
]
```

Exact version, download URL and hash. Commit it, and every machine gets the same bytes. `uv run` uses the project environment without activating anything:

```bash
uv run python -c "import cowsay; print(cowsay.char_names[:3])"
```

```
['beavis', 'cheese', 'cow']
```

To prove the lock is enough, I deleted `.venv` and ran `uv sync`:

```
Creating virtual environment at: .venv
Resolved 2 packages in 0.88ms
Installed 1 package in 2ms
 + cowsay==6.1
```

`uv tree` prints the dependency tree, and `uv python list` shows interpreters it found (my output listed 3.14.0 from pyenv, 3.14.7 from Homebrew and some "download available" entries). If you prefer the pip workflow, `uv venv` plus `uv pip install cowsay` also worked here; it is the same idea as the first section.

I am not claiming uv is faster: the machine was heavily loaded during my runs, so I did not time anything.

## requirements.txt vs the lock file

My `requirements.txt` above is a flat list of pins produced by `pip freeze`; it does not record hashes unless you ask for that. `uv.lock` is generated and records URLs and hashes, while `pyproject.toml` stays short and human-edited. Rule of thumb: you edit `pyproject.toml`, the tool edits the lock.

| | Go | Node.js | Python (uv) |
|---|---|---|---|
| Declared dependencies | `go.mod` | `package.json` | `pyproject.toml` |
| Exact versions | `go.mod` + `go.sum` | `package-lock.json` | `uv.lock` |
| Where code lands | shared module cache | `node_modules` in the project | `.venv` in the project |

See [Packages and modules in Go](/posts/go-packages-modules/) for the Go side.

## A few things to watch

- Do not commit `.venv`; do commit `pyproject.toml`, `uv.lock` and `.python-version`.
- A venv has absolute paths inside, so moving or renaming the folder breaks it. Recreate it instead.
- Without activation, `python` is still the system one. `uv run` avoids the question.
- According to the docs, many system-managed Pythons are marked "externally managed" (PEP 668) and refuse global `pip install`. I did not hit that here.
- Check `which python` after activating if an import behaves strangely.

## Exercise

1. Create a project with `uv init`, add `requests`, and write a script that prints a response status for a local server.
2. Delete `.venv` and rebuild it with `uv sync`.
3. Do the same with `python3 -m venv` and `pip freeze`, and compare the two files.

## What's next

Next: "Types and control flow in Python". Unlike Go, types are not checked at compile time, and we will see what that means in practice. For a different model of running code, see [The Node.js event loop](/posts/node-event-loop/).
