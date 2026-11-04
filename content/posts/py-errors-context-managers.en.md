+++
date = '2027-02-23T10:00:00+03:30'
draft = false
title = 'Errors and context managers in Python'
description = 'Python exceptions and context managers: try/except/finally, chaining, ExceptionGroup, with, contextlib and ExitStack, all run on Python 3.14.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "exceptions", "context-managers"]
cover = { image = "/images/covers/py-errors-context-managers.png", alt = "Errors and context managers in Python", hiddenInSingle = true }
+++

Imagine a function that opens a file, starts reading, and fails halfway because a line has bad data. Is the file closed? In Go you would write `defer f.Close()` right after opening it, and the close happens whatever happens next. Python has the same need and answers it in two steps. First, errors are **exceptions**: they do not come back as return values, they fly up the call stack until somebody catches them. Second, a `with` block guarantees that cleanup code runs, however the block ends, including when an exception flies through it.

This post covers both halves: how exceptions behave on their way up (and what Python gives you to read and reshape them), and how `with` and `contextlib` make cleanup reliable. It follows [classes and dataclasses](/posts/py-classes-dataclasses/), because exceptions are classes and `with` is built on two methods.

Python reports errors with exceptions, unlike [Go's errors as values](/posts/go-functions-defer-errors/): there is no `if err != nil` after every call. Node has the same model for synchronous code, and I covered the async side in [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/).

> Everything ran with Python 3.14.0 on macOS (`python3 --version`). The demos are three local scripts: `flow.py`, `chain.py` and `cm.py`. The tracebacks below show `<demo>` instead of the real directory, and a few extra checks I ran in a scratch file are marked as such.

## try, except, else, finally

A `try` block runs code that may fail. `except` catches a particular error. Two more clauses are less known: `else` runs only if nothing was raised, and `finally` runs always. This function has all four, and prints which part ran:

```python
def f(x):
    try:
        print("try")
        r = 10 / x
    except ZeroDivisionError as e:
        print("except:", e)
        return "from except"
    else:
        print("else")
        return "from else"
    finally:
        print("finally")
print(f(2)); print(f(0))
```

```text
try
else
finally
from else
try
except: division by zero
finally
from except
```

Read the output in two halves, one per call. `f(2)` works: `try` runs, nothing is raised, so `else` runs, and then `finally`. Only after that does the returned value, `from else`, get printed. `f(0)` divides by zero: `try` starts, the error jumps straight to `except`, and `finally` still runs before the function returns `from except`.

The important part is that `finally` runs **even though both branches had already executed `return`**. That is what makes it the right place for cleanup. It also has a sharp edge: a `return` inside `finally` replaces the earlier one and silently throws away any exception. The demo has such a function, and Python 3.14 warns about it when the file is compiled:

```text
flow.py:19: SyntaxWarning: 'return' in a 'finally' block
```

## The hierarchy and catching specifically

Exceptions form a class hierarchy. The demo prints it for `FileNotFoundError`:

```text
['FileNotFoundError', 'OSError', 'Exception', 'BaseException', 'object']
```

A `FileNotFoundError` is an `OSError`, which is an `Exception`. An `except` clause for a class also catches all its subclasses, so catch the **narrowest** class that you can really handle. `except Exception` is a last resort for the outer boundary of a program, and a bare `except:` is worse, because it would even catch `KeyboardInterrupt` (Ctrl+C). Exceptions also carry data: for `open("/no/such/file")` the demo got an error whose `errno` was `2` and whose `filename` was the path.

Two types can share a handler by putting them in a tuple: `except (ValueError, TypeError):` works everywhere, and the demo's `int("x")` was caught by it as a `ValueError`. On 3.14 the demo also ran `except ValueError, TypeError:` without parentheses. As far as I know (PEP 758), that form is new in 3.14 and is a syntax error before it, but I did not test older versions.

## Chaining

If you raise a new exception while handling another one, you do not want to lose the first, because it is often the real cause. Python keeps it, and calls this {{< term "exception-chaining" "exception chaining" >}}. There are two flavors:

```python
raise RuntimeError("config broken") from e   # explicit: __cause__
raise ValueError("oops")                     # inside except: implicit __context__
```

The demo caught both and printed their attributes:

```text
KeyError('k') True True
None ZeroDivisionError('division by zero') False
```

The first line is the explicit `from e`: `__cause__` is the original `KeyError`, `__context__` is the same object, and `__suppress_context__` is `True`. The second line is the implicit case (a `ValueError` raised inside an `except ZeroDivisionError` block): there is no `__cause__`, but `__context__` still records the `ZeroDivisionError`. The two forms look different in a traceback. This is the implicit one, printed by `traceback.print_exc()`:

```text
Traceback (most recent call last):
  File "<demo>/chain.py", line 3, in <module>
    1/0
    ~^~
ZeroDivisionError: division by zero

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<demo>/chain.py", line 5, in <module>
    raise ValueError("oops")
ValueError: oops
```

`During handling of the above exception, another exception occurred` tells you the second error happened while the first was being handled, perhaps by accident. In a separate scratch file I also checked the explicit form, and its joining line is different: `The above exception was the direct cause of the following exception:`. So use `raise ... from e` when you deliberately translate a low-level error into one of your own, so that the reader of the traceback knows it was on purpose.

## Custom exceptions and notes

Your own exception is just a subclass of `Exception`, and it can carry extra data:

```python
class AppError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code
try:
    try:
        raise AppError("bad", 42)
    except AppError as e:
        e.add_note("while loading user 7")
        raise
except AppError as e:
    print(e.code, e.__notes__)
```

```text
42 ['while loading user 7']
```

The inner handler adds a note with `add_note()` and re-raises the same exception with a bare `raise` (which keeps the original traceback). The outer handler then sees both the `code` attribute and the list of notes. Notes appear under the error message in a printed traceback too, so each layer can add context ("while loading user 7") without wrapping the exception in a new one.

## ExceptionGroup and except*

Sometimes several things fail at once, for example in a batch of jobs. An {{< term "exception-group" "ExceptionGroup" >}} carries many errors together. The demo runs four jobs, collects the failures (two `ValueError` and one `TypeError`) and raises them as one group:

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

A plain `except ValueError` would not even match here, because the group itself is not a `ValueError`. With `except*`, Python looks inside the group, and every matching clause runs on its own slice of it: the `ValueError` clause saw `v1` and `v3`, and the `TypeError` clause saw `t2`.

## Logging and traceback

When you catch an error you usually want a record of it. `logging.exception("lookup failed")`, called inside an `except` block, logs the message and the full traceback:

```text
ERROR lookup failed
Traceback (most recent call last):
  File "<demo>/chain.py", line 11, in <module>
    {}["k"]
    ~~^^^^^
KeyError: 'k'
```

Use it instead of `print(e)`, which prints only the message (here just `'k'`) and loses the stack.

## The with statement

Back to the opening problem. A {{< term "context-manager" "context manager" >}} is an object that knows how to set something up and how to clean it up. The `with` statement uses it. Writing `with m as x: body` means roughly: call `m.__enter__()` and bind its result to `x`, run the body, and then call `m.__exit__(type, value, traceback)` whether the body finished normally or raised. When the body succeeds, those three arguments are all `None`; when it raised, they describe the exception.

I wrote a small manager that prints when it enters and exits, so the order is visible:

```python
class Res:
    def __init__(self, name, swallow=False):
        self.name, self.swallow, self.closed = name, swallow, False
    def __enter__(self):
        print("enter", self.name); return self
    def __exit__(self, et, ev, tb):
        self.closed = True
        print("exit", self.name, et.__name__ if et else None)
        return self.swallow
```

Three runs of it, one with a normal body, one where the body raises `ValueError`, and one where it raises but `swallow=True`:

```text
enter a
body
exit a None
closed: True
enter b
exit b ValueError
propagated boom True
enter c
exit c ValueError
after swallow
```

- **`a`:** `enter`, the body, then `exit a None` (no exception, so the type is `None`). Afterwards `closed` is `True`.
- **`b`:** the body raised, but `__exit__` still ran (`exit b ValueError`) before the exception moved on. The outer `except` caught it and `closed` was `True`: cleanup happened, and the error was not hidden.
- **`c`:** the same, but `__exit__` returned a true value, so the exception was **swallowed**, and the program went on to print `after swallow`. Almost always you want to return `None` (or nothing) and let errors propagate.

The demo also wrote out the equivalent by hand, a call to `__enter__`, then `try: ... finally: m.__exit__(None, None, None)` (it printed `enter d` and `exit d None`). That is the idea: `with` is a `try/finally` that you cannot forget to write.

## contextlib

Writing a class with two methods is heavy for small cases. The easy way is a {{< term "generator" "generator" >}} decorated with `@contextlib.contextmanager`: the code before `yield` is the setup, the code after it is the cleanup, and the `try/finally` around the `yield` makes sure cleanup runs when the body raises:

```python
@contextlib.contextmanager
def opened(name):
    print("setup", name)
    try: yield name
    finally: print("cleanup", name)
try:
    with opened("x") as n: raise RuntimeError("fail")
except RuntimeError: print("caught after cleanup")
```

```text
setup x
cleanup x
caught after cleanup
```

The error was raised inside the `with`, cleanup still printed, and only then did our own handler run. Other helpers from the demo: `contextlib.suppress(FileNotFoundError)` around `os.remove` of a missing file (it silently continued and the demo printed `suppressed`), and `contextlib.closing(Conn())`, which calls `close()` for an object that has no `__exit__` (it printed `using conn` and then `conn closed`).

For a variable number of resources, use `ExitStack`. In the demo I entered `r1`, `r2` and `r3` in a list comprehension, and the exits ran in reverse order:

```text
enter r1
enter r2
enter r3
body 3
exit r3 None
exit r2 None
exit r1 None
```

Last in, first out, which is what you want when a later resource may depend on an earlier one. Finally, a real file: `f.closed` was `True` after the `with` block, and also `True` when the body raised `OSError`.

## assert is not validation

`assert n > 0, "n must be positive"` raises `AssertionError` when the condition is false, and the demo printed `assert: n must be positive` with a normal run (`__debug__` was `True`). But Python can be started with `-O`, which removes `assert` statements. I checked in a scratch file: under `python3 -O`, `__debug__` was `False` and `pay(-1)` returned `-1` without any error. So use `assert` only for internal checks that should never fail, and validate real input with `raise ValueError(...)`.

## Bad habits in error handling

- **A bare `except: pass`.** It hides every error, including bugs and Ctrl+C. Catch narrow exceptions and do something useful with them.
- **Losing the cause.** Use `raise X from e` to keep the cause when you translate an error, and a bare `raise` to re-raise unchanged.
- **`return` in `finally`.** It overrides earlier returns and swallows exceptions. Python 3.14 even warns about it.
- **Returning true from `__exit__`.** It hides errors from the caller, and it does so silently.
- **Relying on `assert` for validation.** It disappears with `-O`.

## Exercise

1. Write a `@contextmanager` called `timer` that prints elapsed time even when the body raises.
2. Open two files with one `ExitStack` and prove both closed after an error.
3. Raise an `ExceptionGroup` of three errors and handle two types with `except*`.

## What's next

The next post is "Type hints and mypy". It catches part of these errors before the program runs, which is the other half of the story when exceptions only appear at run time.
