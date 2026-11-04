+++
date = '2027-01-08T10:00:00+03:30'
draft = false
title = 'The Python environment: venv and uv'
description = 'Python virtual environments with venv and uv: pip install, requirements.txt, pyproject.toml, uv.lock and uv sync, all shown with real runs.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "venv", "uv", "pip", "beginner"]
cover = { image = "/images/covers/py-environment-uv-venv.png", alt = "The Python environment: venv and uv", hiddenInSingle = true }
+++

Imagine you have two small projects on the same laptop. The first one needs version 1 of some library, and the second one needs version 2. You install the library for the first project, then install it for the second, and now the first one is broken. Nothing is wrong with either project. They are simply sharing one place to keep libraries, and a place can only hold one version of each.

This is the problem that Python's **virtual environments** solve, and it is where coming to Python from Go or Node.js feels different, before any syntax does. Go keeps modules in a shared cache and picks versions per project through `go.mod`. Node puts a separate `node_modules` folder inside every project. Python's default is closer to a single shared folder, so the Python world invented a way to give each project its own: the virtual environment. This post covers it, the older way (`venv` and `pip`) and the newer one (`uv`). If you read [Getting started with Go](/posts/go-getting-started/) and [npm, package.json and lockfiles](/posts/node-npm-package-json/), the ideas will feel familiar, and only the names change.

I should confess how I first learned why this matters. My first attempt to show that a venv isolates packages failed: `requests` imported fine outside it, because my pyenv Python already had it installed. When I re-ran things for this post, the base interpreter here still had `requests` (version 2.32.5), so I use a small package called `cowsay` for the isolation test below.

> Everything below was run with Python 3.14.0 and uv 0.10.9 on macOS (arm64), in throwaway directories that I deleted afterwards. Home paths are shown as `<home>` and the throwaway directory as `<tmp>`. A few millisecond figures come from the original run and vary on every run; I did not time anything, and I am not claiming one tool is faster.

## Which Python am I running

Your machine may have several Pythons: one from the system, one from Homebrew, one from a version manager like pyenv. First find out which one the command `python3` means:

```bash
python3 --version
which python3
```

```
Python 3.14.0
<home>/.pyenv/versions/3.14.0/bin/python3
```

Mine comes from pyenv. Every Python installation has a folder called {{< term "site-packages" "site-packages" >}}, and that is where `pip install` puts libraries. If you install packages straight into this interpreter, every project that uses it sees the same folder. Two projects that want different versions of one library then collide, exactly as in the story above.

The fix is a {{< term "virtual-environment" "virtual environment" >}}: a private folder, usually named `.venv`, that contains a link to an interpreter and its own empty `site-packages`. Install into the environment, and the packages stay inside that project.

## venv and pip

Python ships with the `venv` module, so no installation is needed. This creates an environment in `.venv` and activates it:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -c "import sys; print(sys.prefix); print(sys.base_prefix)"
```

```
<tmp>/pipdemo/.venv
<home>/.pyenv/versions/3.14.0
```

"Activating" has a simple meaning: the shell puts `.venv/bin` at the front of your `PATH`, so `python` and `pip` now mean the copies inside the environment. After activation, `which python` printed `<tmp>/pipdemo/.venv/bin/python`.

The two lines of output show how Python itself knows it is inside a venv. `sys.prefix` points at the venv, while `sys.base_prefix` still points at the interpreter that the venv was made from. If they differ, you are in a venv. The file `.venv/pyvenv.cfg` records the base interpreter and a line `include-system-site-packages = false`, which means "do not look at the base interpreter's packages".

A fresh environment holds almost nothing:

```bash
pip list
```

```
Package Version
------- -------
pip     25.2
```

Now install a package from {{< term "pypi" "PyPI" >}}, the public package index, using {{< term "pip" "pip" >}}, and save what was installed with `pip freeze`:

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

I asked for one package and got five lines. `requests` depends on four other packages, and pip installed those too. `pip freeze` lists everything in the environment with exact versions (`==`), so the file records the full set. (The versions are simply whatever PyPI had when I first ran this. Today my connection to PyPI kept timing out and `pip install requests` never finished, so this list is from the original run. I checked that the same five exact versions come out by installing `requests` from a local cache with `uv pip install`. The `cowsay` install with pip below did work today.)

Now the isolation test. Inside the venv I installed a tiny package called `cowsay` and imported it; that worked. Then I left the venv with `deactivate` and ran the base interpreter:

```bash
python3 -I -c "import cowsay"
```

```
ModuleNotFoundError: No module named 'cowsay'
```

The base Python does not see it. The package lives only inside `.venv`, which is the whole point. (The `-I` flag runs Python in isolated mode, so nothing from my shell settings interferes.)

## uv

`venv`, `pip` and `pip freeze` are three separate steps, and the Python version itself is a fourth thing handled by pyenv or the system. {{< term "uv" "uv" >}} is a single tool that manages the Python version, the environment and the dependencies together. Start a project:

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

`uv init` created a few files: `main.py`, `README.md`, a git repository, and the two files printed above. {{< term "pyproject-toml" "pyproject.toml" >}} holds the project's metadata and its direct dependencies (the list is empty for now), and `.python-version` pins which interpreter the project uses. Now add a dependency:

```bash
uv add cowsay
```

```
Creating virtual environment at: .venv
Resolved 2 packages in 741ms
Installed 1 package in 17ms
 + cowsay==6.1
```

One command did several jobs. It created `.venv` (you never ran `venv` yourself), added `cowsay` to `pyproject.toml` (`dependencies = ["cowsay>=6.1"]`), installed it, and wrote a file named `uv.lock`, a {{< term "lockfile" "lockfile" >}}. "Resolved 2 packages" counts the project itself plus `cowsay`. These timings are from the original run and change every time. A trimmed look at the lock file:

```toml
[[package]]
name = "cowsay"
version = "6.1"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.pythonhosted.org/.../cowsay-6.1-py3-none-any.whl", hash = "sha256:274b1e6f...", size = 25560, ... },
]
```

It records the exact version, where to download it and a hash of the file. Commit it, and every machine that installs from it gets the same bytes. `uv run` runs a command inside the project's environment, so you do not need to activate anything:

```bash
uv run python -c "import cowsay; print(cowsay.char_names[:3])"
```

```
['beavis', 'cheese', 'cow']
```

To show that the lock file is enough to rebuild the environment, I deleted `.venv` and ran `uv sync`, which makes the environment match the lock file:

```
Creating virtual environment at: .venv
Resolved 2 packages in 0.88ms
Installed 1 package in 2ms
 + cowsay==6.1
```

The environment came back, with the same `cowsay==6.1`. Two more commands are worth knowing: `uv tree` prints the dependency tree (here `uvdemo v0.1.0` with `cowsay v6.1` under it), and `uv python list` shows the interpreters uv found on the machine (in my case 3.14.0 from pyenv, 3.14.7 from Homebrew, and some entries marked "download available"). If you prefer the pip-style workflow, `uv venv` plus `uv pip install cowsay` also worked here; it is the same idea as the previous section with a different front end.

## requirements.txt vs the lock file

The `requirements.txt` I made above is a flat list of exact versions written by `pip freeze`. It does not record file hashes unless you ask for that, and it mixes the packages you chose with the ones they pulled in, so later you cannot tell which is which. `uv.lock` is generated by the tool, records URLs and hashes, and `pyproject.toml` stays short and human-edited with only the dependencies you actually asked for. A rule of thumb: you edit `pyproject.toml`, and the tool edits the lock.

Here is how it maps to what you may know:

| | Go | Node.js | Python (uv) |
|---|---|---|---|
| Declared dependencies | `go.mod` | `package.json` | `pyproject.toml` |
| Exact versions | `go.mod` + `go.sum` | `package-lock.json` | `uv.lock` |
| Where code lands | shared module cache | `node_modules` in the project | `.venv` in the project |

See [Packages and modules in Go](/posts/go-packages-modules/) for the Go side.

## Environment traps

- **What to commit.** Do not commit `.venv`; it can be rebuilt. Do commit `pyproject.toml`, `uv.lock` and `.python-version`, because those describe the project.
- **Moving the folder.** A venv has absolute paths inside it, so moving or renaming the project folder breaks it. Recreate it instead of fixing it.
- **Forgetting to activate.** Without activation, `python` is still the system one, and your packages "disappear". `uv run` avoids the question by always using the project's environment.
- **Externally managed Pythons.** According to the docs, many system-managed Pythons are marked "externally managed" (PEP 668) and refuse a global `pip install`, so a venv is the expected way there. I did not hit that here.
- **Strange imports.** If an import behaves strangely, run `which python` after activating, to check which interpreter you are really using.

## Exercise

1. Create a project with `uv init`, add `requests`, and write a script that prints a response status for a local server.
2. Delete `.venv` and rebuild it with `uv sync`.
3. Do the same with `python3 -m venv` and `pip freeze`, and compare the two files.

## What's next

The next post is "Types and control flow in Python". Unlike Go, types are not checked at compile time, and we will see what that means in practice. For a different model of running code, see [The Node.js event loop](/posts/node-event-loop/).
