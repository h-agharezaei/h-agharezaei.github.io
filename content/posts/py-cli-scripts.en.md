+++
date = '2027-05-13T10:00:00+03:30'
draft = false
title = 'Command-line tools and scripts with Python'
description = 'Python command-line tools: argparse subcommands, exit codes, pipes and BrokenPipeError, subprocess safety, Ctrl-C, Typer, PEP 723 scripts and tests.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "cli", "argparse", "typer", "scripts"]
cover = { image = "/images/covers/py-cli-scripts.png", alt = "Command-line tools and scripts with Python", hiddenInSingle = true }
+++

I ran `python3 emit.py | head -2`. The script prints 100,000 numbers; `head -2` keeps the first two. I got `0`, `1`, and then a long `BrokenPipeError` traceback. The program did nothing wrong, and yet it looked like it crashed.

Details like this are what separate a script from a tool. A script works when you run it the way you imagined. A tool also behaves well when someone puts it in a {{< term "pipe" "pipe" >}}, gives it bad arguments, presses Ctrl-C, or calls it from another program that looks at its exit code. In this post we write the program behind the console-script entry point from [the previous post](/posts/py-packaging-publishing/). I also built a Go version in [A command-line tool in Go](/posts/go-cli-tool/), and the process side relies on [Processes and signals](/posts/linux-processes-signals/).

> I re-ran everything with Python 3.14.0 and uv 0.10.9 in a scratch copy of the demo. Typer 0.20.0 (with Click 8.5.0) lived in a throwaway venv, installed from uv's offline cache and deleted afterwards. The machine was busy, so there are no timings. The demo is a local example. The usage text wraps at the terminal width, so yours may break lines differently from mine.

## argparse: the standard library parser

A command-line tool has to turn text such as `wc.py count --limit 5 notes.txt` into values the program can use, and to reject nonsense with a clear message. {{< term "argparse" "argparse" >}} does this and ships with Python.

My demo, `wc.py`, is a small word counter. It has a `count` subcommand (like `git commit`: the first word chooses what to do), a file argument that is optional (`-` or nothing means read standard input), an `int` option, an option restricted to a few `choices`, and a mutually exclusive group (`--lines` or `--words`, never both). These are the key lines; the full source is in the local demo:

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

`type=int` makes argparse convert and check the value for you, and `choices` limits the options. You get `--help` for free, generated from this description:

```text
usage: wc.py count [-h] [--limit LIMIT] [--lines | --words]
                   [--format {text,json}]
                   [file]
```

(That is the first lines of `python3 wc.py count --help`; the rest lists each option with its help text.) In `[--lines | --words]` the bar means "one of these". Now the useful part: what happens with bad usage. I ran two wrong commands. Each prints the usage lines, then an error on **stderr** (the error stream, separate from the normal output), and ends with {{< term "exit-status" "exit code" >}} 2. I cut the repeated usage lines here:

```text
$ python3 wc.py count --lines --words t.txt
wc.py count: error: argument --words: not allowed with argument --lines
rc=2
$ python3 wc.py count --format xml t.txt
wc.py count: error: argument --format: invalid choice: 'xml' (choose from text, json)
rc=2
```

The exit code is what a calling program checks. My convention is:

- `0` means success.
- `1` means a runtime failure. Counting a file that does not exist (`nope.txt`) printed `wc.py: nope.txt: not found` and gave rc=1.
- `2` means a usage error. argparse does that itself.

`main()` returns an integer and the last line, `sys.exit(main())`, passes it on to the shell. Returning a number rather than calling `sys.exit` deep inside the code also makes `main` easy to test, as we will see.

## Config, environment variables and logging

A tool usually has several places a setting can come from. In my script the `format` value is chosen like this: the `WC_FORMAT` {{< term "environment-variable" "environment variable" >}} first, then a `--config file.toml` read with the standard `tomllib`, then the value from the command line (or its default). The file had one line, `format = "json"`:

```text
$ python3 wc.py count t.txt                           ->  2 5
$ python3 wc.py --config c.toml count t.txt           ->  {"lines": 2, "words": 5}
$ WC_FORMAT=text python3 wc.py --config c.toml ...    ->  2 5
```

Without a config it printed `2 5` (two lines, five words). With the config the output became JSON, and the environment variable overrode the file and put it back to text. I also ran `--config c.toml count --format text t.txt` and still got JSON. That is a quirk of my demo: the command-line flag has the lowest priority, which is the opposite of what users usually expect. In a real tool, the explicit flag should normally win, then the environment, then the file, then the default.

Two smaller habits. `logging.basicConfig(stream=sys.stderr)`, with `-v` switching to DEBUG, keeps diagnostics on stderr, so stdout stays clean for whatever reads it next in a pipe (with `-v`, the demo printed `DEBUG format=text cfg={}` on stderr before the result). And `pathlib.Path` as the argument type gives you a path object that has `read_text()`.

## Pipes and SIGPIPE

Back to the traceback from the beginning. A pipe connects one program's output to another's input. In `emit.py | head -2`, `head` takes two lines and then exits, closing its end of the pipe. When `emit.py` writes again, the operating system tells it the reader is gone, with the {{< term "sigpipe" "SIGPIPE" >}} {{< term "signal" "signal" >}}. Most command-line tools just die quietly at that point. Python ignores SIGPIPE at startup, as far as I know, so the write fails with an exception instead. This is the real output:

```text
0
1
Traceback (most recent call last):
  File "<tmp>/emit.py", line 3, in <module>
    print(i)
    ~~~~~^^^
BrokenPipeError: [Errno 32] Broken pipe
Exception ignored while flushing sys.stdout:
BrokenPipeError: [Errno 32] Broken pipe
status=120 0
```

The last line shows the exit statuses of the two programs in the pipeline: `emit.py` ended with 120 and `head` with 0. The status 120 comes from the interpreter failing to flush its output while exiting, which is the "Exception ignored" lines. The fix is a pattern from the Python documentation:

```python
except BrokenPipeError:
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    sys.exit(141)
```

When the pipe breaks, the code points standard output at `/dev/null`, so the final flush at exit has nowhere to fail, and then exits quietly. With this in `emit2.py` the output was just `0` and `1` with the status `141 0`. No traceback. And 141 is the number a shell shows for a process killed by SIGPIPE (128 + 13), so it behaves like a native tool.

## subprocess without a shell

A tool often runs other programs. The risky way is to build a command as a string and hand it to the shell. To show why, I used a file called `my file.txt`, with a space in the name:

```text
shell=True  : 1 'wc: my: open: No such file or directory\nwc: file.txt: open: No such file or directory'
list args   : 0 1
shlex.quote : 'my file.txt'
check=True  : 1 'ls: missing.txt: No such file or directory'
```

Line by line:

- With `shell=True` the shell split the name at the space and ran `wc -l my file.txt`, which asks for two files that do not exist. Exit code 1. If that text had come from a user, it could have contained far worse than a space.
- With a list of arguments (`["wc", "-l", name]`), no shell is involved and the name is passed as one argument. It worked: exit code 0 and the count `1`.
- `shlex.quote` shows what correct quoting for a shell looks like: the name wrapped in quotes.
- `check=True` makes `subprocess.run` raise `CalledProcessError` when the command exits with a non-zero status, instead of letting you ignore it. Here `ls` failed and the exception carried code 1 and the error text.

If you must build a shell string, wrap every piece with `shlex.quote`. A list is better, and it is the default choice.

## Ctrl-C

Pressing Ctrl-C sends the SIGINT signal, which Python raises as `KeyboardInterrupt`. I tested two tiny scripts that sleep for 30 seconds. A parent script started each, waited a second, and sent SIGINT:

```text
sig.py returncode 130 | stderr tail: interrupted
sig2.py returncode -2 | stderr tail: KeyboardInterrupt
```

`sig.py` has `except KeyboardInterrupt: sys.exit(130)`, so it printed a short message and returned 130. `sig2.py` has no handler, so Python printed the traceback (the last line of it is `KeyboardInterrupt`) and then the process ended by the signal itself. `subprocess` reports that as -2, a negative signal number, which a shell shows as 130 (128 + 2). Both end up with the same shell status, but the handler version has no traceback.

## Typer

argparse is explicit: you call `add_argument` for everything. Typer builds the same interface from type hints, with Click underneath. The same CLI came out at about 15 lines of logic:

```python
@app.command()
def count(file: Optional[Path] = None, limit: int = 0,
          fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.text): ...
```

`Fmt` is an `Enum` with `text` and `json`, which is how Typer knows the allowed choices. With `--format xml`, Typer printed a boxed error, `Invalid value for '--format': 'xml' is not one of 'text', 'json'.`, with exit code 2. `--limit abc` gave `'abc' is not a valid integer.`, also code 2. Typer also added `--install-completion` and `--show-completion` to the help. I did not recreate the mutually exclusive group.

| | argparse | Click | Typer |
|---|---|---|---|
| Install | stdlib | dependency | dependency (uses Click) |
| Style | explicit calls | decorators | type hints |
| Good for | scripts, no deps | larger CLIs | quick typed CLIs |

That table is my opinion; I only ran argparse and Typer.

## Single-file scripts and tests

Sometimes a script is all you need, but it has a dependency. {{< term "inline-script-metadata" "Inline script metadata" >}} lets a script declare its own requirements in a comment block, and `uv run --script` reads it:

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["humanize==4.13.0"]
# ///
```

(The real `size.py` also has a `requires-python` line.) After `chmod +x`, `./size.py 1500000` installed `humanize` into an environment managed by uv and printed `1.5 MB`. The second run printed it again without installing anything. The shebang line worked on macOS.

For tests, the design pays off. Because `main(argv)` takes the arguments as a list and returns the exit code, a test can call it directly with pytest's `capsys` ([Testing in Python with pytest](/posts/py-testing-pytest/)) and check the output and the code. For the real process exit code, run the script with `subprocess.run`. My three tests for `wc.py` passed (counting through `capsys`, the bad choice exiting with 2, and the subprocess returning 1 for a missing file), and so did one for the Typer version with Typer's `CliRunner`: 4 passed in total.

## Versus Go

In Go a CLI compiles to one binary that needs no interpreter, and `flag` ships with the standard library too. A Python tool needs an interpreter and its dependencies on the target machine, unless it is packaged as in the previous post.

## CLI traps

- Return ints from `main()` and send errors to stderr, so callers can tell success from failure and pipes stay clean.
- Never use `shell=True` with text a user controls. A list of arguments avoids both quoting bugs and injection.
- Handle `BrokenPipeError` if your tool prints a lot; otherwise `| head` turns a working tool into one that looks broken.
- Decide the priority of flag, environment variable and config file on purpose, and write it down. My demo got it backwards.
- Pin versions in script metadata, so the script behaves the same next year.

## Exercise

Make `--limit` read its default from the `--config` file, and test it with `capsys`.

## What's next

Next is "Small data processing with csv and sqlite3", because many real scripts end up reading a CSV someone sent.
