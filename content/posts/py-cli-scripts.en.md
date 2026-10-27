+++
date = '2027-05-13T10:00:00+03:30'
draft = false
title = 'Command-line tools and scripts with Python'
description = 'Python command-line tools: argparse subcommands, exit codes, pipes and BrokenPipeError, subprocess safety, Ctrl-C, Typer, PEP 723 scripts and tests.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "cli", "argparse", "typer", "scripts"]
cover = { image = "/images/covers/py-cli-scripts.png", alt = "Command-line tools and scripts with Python", hiddenInSingle = true }
+++

In the [previous post](/posts/py-packaging-publishing/) we packaged a project and met the console-script entry point. Here we write the program behind such an entry point. I also built a Go version in [a command-line tool in Go](/posts/go-cli-tool/), and the process side relies on [processes and signals](/posts/linux-processes-signals/).

> Python 3.14.0 and uv 0.10.9, in a throwaway directory. Typer 0.20.0 (with Click 8.5.0) lived in a venv I deleted afterwards. The load on this machine was high, so there are no timings. The demo is a local example.

## argparse: subcommands, types, choices

{{< term "argparse" "argparse" >}} is in the standard library. My `wc.py` has a `count` subcommand with a path or `-`, an `int` option, a `choices` option and a mutually exclusive group (the full source is in the local demo; the key lines):

```python
sub = p.add_subparsers(dest="cmd", required=True)
c = sub.add_parser("count", help="count lines and words")
c.add_argument("file", nargs="?", default="-")
c.add_argument("--limit", type=int, default=0)
g = c.add_mutually_exclusive_group()
g.add_argument("--lines", action="store_true")
g.add_argument("--words", action="store_true")
c.add_argument("--format", choices=["text", "json"], default="text")
```

`python3 wc.py count --help` printed:

```text
usage: wc.py count [-h] [--limit LIMIT] [--lines | --words] [--format {text,json}]
                   [file]
```

Bad usage goes to stderr with {{< term "exit-status" "exit code" >}} 2:

```text
$ python3 wc.py count --lines --words t.txt
wc.py count: error: argument --words: not allowed with argument --lines
rc=2
$ python3 wc.py count --format xml t.txt
wc.py count: error: argument --format: invalid choice: 'xml' (choose from text, json)
rc=2
```

My convention: 0 success, 1 runtime failure (`nope.txt` not found gave rc=1), 2 usage error. `main()` returns an int and `sys.exit(main())` passes it on.

## Config, env vars, logging

Precedence in my script: the `WC_FORMAT` {{< term "environment-variable" "environment variable" >}}, then `--config file.toml` read with the stdlib `tomllib`, then the flag default. With `format = "json"` in the file I got `{"lines": 2, "words": 5}`, and `WC_FORMAT=text` overrode it back to `2 5`. `logging.basicConfig(stream=sys.stderr)` with `-v` for DEBUG keeps diagnostics away from stdout, which must stay clean for pipes. `pathlib.Path` as the argument type gives you `read_text()` directly.

## Pipes and SIGPIPE

`emit.py` prints 100000 numbers. `python3 emit.py | head -2` gave:

```text
0
1
Traceback (most recent call last):
  ...
    print(i)
BrokenPipeError: [Errno 32] Broken pipe
status=120 0
```

`head` closed the pipe, and Python turned the {{< term "sigpipe" "SIGPIPE" >}} into an exception instead of dying quietly (Python ignores that signal at startup, as far as I know). The status 120 comes from the interpreter's failure to flush at exit. The fix, from the Python docs' pattern:

```python
except BrokenPipeError:
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    sys.exit(141)
```

Now there is no traceback and the status is 141, the same number a shell shows for a SIGPIPE death.

## subprocess without a shell

Filename `my file.txt`:

```text
shell=True  : 1 'wc: my: open: No such file or directory\nwc: file.txt: open: No such file or directory'
list args   : 0 1
shlex.quote : 'my file.txt'
check=True  : 1 'ls: missing.txt: No such file or directory'
```

The shell split the name in two. A list needs no quoting, and `check=True` raises `CalledProcessError` on a non-zero status. If you must build a shell string, wrap every piece with `shlex.quote`, but a list is better.

## Ctrl-C

I sent SIGINT from a parent script. With `except KeyboardInterrupt: sys.exit(130)` the child's return code was 130. Without a handler Python printed the traceback and `returncode` was -2: it dies by the signal, which a shell reports as 130 (128 + 2).

## Typer

The same CLI with Typer, about 15 lines of logic, using type hints instead of `add_argument`:

```python
@app.command()
def count(file: Optional[Path] = None, limit: int = 0,
          fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.text): ...
```

`--format xml` printed a boxed error, `Invalid value for '--format': 'xml' is not one of 'text', 'json'.`, with exit code 2. `--limit abc` gave "not a valid integer". Typer also added `--install-completion` to the help. I did not recreate the mutually exclusive group.

| | argparse | Click | Typer |
|---|---|---|---|
| Install | stdlib | dependency | dependency (uses Click) |
| Style | explicit calls | decorators | type hints |
| Good for | scripts, no deps | larger CLIs | quick typed CLIs |

That table is my opinion; I only ran argparse and Typer.

## Single-file scripts and tests

With {{< term "inline-script-metadata" "inline script metadata" >}} a script declares its dependency:

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["humanize==4.13.0"]
# ///
```

After `chmod +x`, `./size.py 1500000` installed `humanize` and printed `1.5 MB`; the second run printed it again without installing. The shebang worked on macOS.

For tests, call `main(argv)` with pytest's `capsys` ([testing with pytest](/posts/py-testing-pytest/)), and use `subprocess.run` for the real exit code. My three tests passed, plus one with Typer's `CliRunner`.

## Versus Go

In Go a CLI compiles to one binary that needs no interpreter. Go's `flag` package ships with the standard library too. A Python tool needs an interpreter and its dependencies on the target machine, unless packaged as in the previous post.

## A few things to watch

- Return ints from `main()`, and send errors to stderr.
- Never `shell=True` with user-controlled text.
- Handle `BrokenPipeError` if your tool prints a lot.
- Pin versions in script metadata.

## Exercise

Make `--limit` read its default from the `--config` file, and test it with `capsys`.

## What's next

The next post is "Small data processing with csv and sqlite3".
