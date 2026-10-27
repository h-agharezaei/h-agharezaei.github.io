+++
date = '2027-02-23T10:00:00+03:30'
draft = false
title = 'Errors and context managers in Python'
description = 'Python exceptions and context managers: try/except/finally, chaining, ExceptionGroup, with, contextlib and ExitStack, all run on Python 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "exceptions", "context-managers"]
cover = { image = "/images/covers/py-errors-context-managers.png", alt = "Errors and context managers in Python", hiddenInSingle = true }
+++

In the [previous post](/posts/py-classes-dataclasses/) we built classes and dataclasses. Now we look at what happens when things go wrong, and how to guarantee cleanup. Python reports errors with exceptions, unlike [Go's errors as values](/posts/go-functions-defer-errors/): there is no `if err != nil`, an exception travels up the call stack until somebody catches it. Node has the same model for synchronous code, and I covered the async side in [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/).

> Everything ran with Python 3.14.0 on macOS (`python3 --version`). The demos are three local scripts; home paths are redacted.

## try, except, else, finally

```python
def f(x):
    try:
        print("try"); r = 10 / x
    except ZeroDivisionError as e:
        print("except:", e); return "from except"
    else:
        print("else"); return "from else"
    finally:
        print("finally")
```

```text
f(2): try, else, finally  -> from else
f(0): try, except: division by zero, finally  -> from except
```

`else` runs only when nothing was raised, and `finally` runs always, even after a `return`. A `return` inside `finally` overrides the earlier one, which is why 3.14 prints `SyntaxWarning: 'return' in a 'finally' block` for it. Do not do that.

## The hierarchy and catching specifically

`FileNotFoundError.__mro__` printed `FileNotFoundError, OSError, Exception, BaseException, object`. Catch the narrowest class you can handle; `except Exception` is a last resort at a boundary, and a bare `except` would even catch `KeyboardInterrupt`. `open("/no/such/file")` gave an error whose `errno` was `2` and `filename` the path.

Two types can share a handler. `except (ValueError, TypeError):` always worked, and on 3.14 `except ValueError, TypeError:` without parentheses also ran fine. I did not test older versions; as far as I know that form is a syntax error before 3.14.

## Chaining

If you raise while handling another error, Python keeps the first one. {{< term "exception-chaining" "Chaining" >}} has two flavors:

```python
raise RuntimeError("config broken") from e   # explicit: __cause__
raise ValueError("oops")                     # inside except: implicit __context__
```

```text
KeyError('k') True True       # __cause__, context is cause, suppress_context
None ZeroDivisionError('division by zero') False
```

Printed by `traceback.print_exc()`, the implicit case showed both tracebacks joined by `During handling of the above exception, another exception occurred:`. With `from e` the joining line is different (I did not print it; the docs describe it as the direct cause). Use `from` when you translate a low-level error into your own.

## Custom exceptions and notes

```python
class AppError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg); self.code = code
```

I raised `AppError("bad", 42)`, added `e.add_note("while loading user 7")`, re-raised with a bare `raise`, and the outer handler saw `42 ['while loading user 7']`. Notes appear under the message in a traceback too.

## ExceptionGroup and except*

An {{< term "exception-group" "ExceptionGroup" >}} carries several errors at once, for example from a batch. I collected four job results (two `ValueError`, one `TypeError`) and raised them together:

```python
try:
    raise ExceptionGroup("batch", errs)
except* ValueError as eg: print("values:", [str(x) for x in eg.exceptions])
except* TypeError as eg:  print("types:", [str(x) for x in eg.exceptions])
```

```text
values: ['v1', 'v3']
types: ['t2']
```

Unlike a plain `except`, every matching `except*` clause runs on its own slice of the group.

## Logging and traceback

`logging.exception("lookup failed")` inside an `except` logged `ERROR lookup failed` followed by the full traceback. Use it instead of `print(e)`, which loses the stack.

## The with statement

A {{< term "context-manager" "context manager" >}} guarantees setup and cleanup. `with m as x: body` calls `m.__enter__()` then the body, and `m.__exit__(type, value, tb)` in a `finally`-like way. A hand-written one:

```python
class Res:
    def __enter__(self): print("enter", self.name); return self
    def __exit__(self, et, ev, tb):
        self.closed = True; print("exit", self.name, et.__name__ if et else None)
        return self.swallow
```

```text
normal body:   enter a, body, exit a None        (closed True)
ValueError:    enter b, exit b ValueError        -> exception propagated
swallow=True:  enter c, exit c ValueError        -> "after swallow" printed
```

If `__exit__` returns a true value the exception is swallowed. Almost always return `None`.

## contextlib

The easy way is a {{< term "generator" "generator" >}} with `@contextlib.contextmanager`; put the cleanup in `try/finally` around the `yield`:

```python
@contextlib.contextmanager
def opened(name):
    print("setup", name)
    try: yield name
    finally: print("cleanup", name)
```

Raising inside the `with` printed `setup x`, `cleanup x`, then my handler ran. Others I ran: `contextlib.suppress(FileNotFoundError)` around `os.remove` of a missing file (silently continued), and `contextlib.closing(Conn())` which called `close()` (printed `conn closed`).

For a variable number of resources use `ExitStack`. I entered `r1`, `r2`, `r3` in a list comprehension and the exits printed in reverse: `exit r3`, `exit r2`, `exit r1`. A real file confirmed it: `f.closed` was `True` after the block, also when the body raised `OSError`.

## assert is not validation

`assert n > 0, "n must be positive"` raised `AssertionError` normally. Under `python3 -O`, `__debug__` was `False` and the same `pay(-1)` returned `-1` silently. So use `assert` for internal invariants only; validate input with `raise ValueError`.

## A few things to watch

- Catch narrow exceptions; never silence with a bare `except: pass`.
- Use `raise X from e` to keep the cause, and a bare `raise` to re-raise unchanged.
- Never `return` in `finally`.
- Returning True from `__exit__` hides errors.
- `assert` disappears with `-O`.

## Exercise

1. Write a `@contextmanager` called `timer` that prints elapsed time even when the body raises.
2. Open two files with one `ExitStack` and prove both closed after an error.
3. Raise an `ExceptionGroup` of three errors and handle two types with `except*`.

## What's next

The next post is "Type hints and mypy".
