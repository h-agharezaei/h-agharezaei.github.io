+++
date = '2027-03-11T10:00:00+03:30'
draft = false
title = 'Type hints and mypy'
description = 'Python type hints and mypy: list[int], X | None, TypedDict, Protocol, PEP 695 generics, real mypy errors, --strict, cast and type: ignore on 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "type-hints", "mypy", "typing"]
cover = { image = "/images/covers/py-type-hints-mypy.png", alt = "Type hints and mypy", hiddenInSingle = true }
+++

In the [previous post](/posts/py-errors-context-managers/) we handled errors. Here is a way to catch a whole class of them before the program runs. Python is dynamically typed, but you can add {{< term "type-hint" "type hints" >}} and let a {{< term "type-checker" "type checker" >}} such as mypy read them. If you come from [Go's static types](/posts/go-types-control-flow/), the difference is that in Python the hints are optional and the interpreter ignores them. We used [dataclasses](/posts/py-classes-dataclasses/) before; they work well with hints.

> Everything ran on Python 3.14.0 with mypy 2.4.0 (`mypy --version`) in a throwaway venv, since deleted. The demo is four small local files.

## A typed module

```python
class User(TypedDict):
    name: str
    age: int

@dataclass
class Order:
    id: int
    total: float

def count_words(words: list[str]) -> dict[str, int]: ...
def find_user(users: dict[str, User], name: str) -> User | None:
    return users.get(name)

def first[T](xs: list[T]) -> T:      # PEP 695 syntax
    return xs[0]

class Closer(Protocol):
    def close(self) -> None: ...
```

`list[int]` and `dict[str, int]` are built-in generics, `User | None` means "a User or None", `TypedDict` types a dict with known keys, and `first[T]` is a {{< term "generics" "generic" >}} function written with the 3.12+ syntax, no `TypeVar` needed. A `Protocol` describes a shape: any class with a matching `close()` qualifies, which is {{< term "structural-typing" "structural typing" >}} and the static cousin of {{< term "duck-typing" "duck typing" >}}. With the full module (it also has a `Conn` class and a `shutdown(c: Closer)` function), `mypy good.py` printed `Success: no issues found in 1 source file`, and running it printed `6 {'a': 2, 'b': 1}`, the user dict, `p`, `Order(id=1, total=9.5)` and `closed`.

## Real errors

A second file `bad.py` has four mistakes: a list of strings passed as `list[int]`, using a result of type `int | None` without a check, a function that forgets a branch, and a class whose `close` has the wrong signature.

```text
bad.py:12: error: Missing return statement  [return]
bad.py:31: error: List item 0 has incompatible type "str"; expected "int"  [list-item]
bad.py:31: error: List item 1 has incompatible type "str"; expected "int"  [list-item]
bad.py:32: error: Item "None" of "int | None" has no attribute "bit_length"  [union-attr]
bad.py:33: error: Argument 1 to "shutdown" has incompatible type "Bad"; expected "Closer"  [arg-type]
bad.py:33: note:     Expected:  def close(self) -> None
bad.py:33: note:     Got:       def close(self, force: bool) -> None
Found 5 errors in 1 file (checked 1 source file)
```

(I shortened the notes onto one line each.) The `None` error is the same family as a nil dereference in Go: the checker forces you to handle the missing case. The fix is `if r is not None:` before the use.

## Types are not checked at run time

The same wrong call, executed without mypy:

```python
def total_of(xs: list[int]) -> int:
    return sum(xs)
print(total_of(['1','2']))
```

```text
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

That error came from `sum`, not from the hint. With another function, `def f(a: int) -> int: return a*2`, the call `f('ab')` printed `abab`, and `f.__annotations__` was `{'a': <class 'int'>, 'return': <class 'int'>}`. The hints are stored and nothing more. So run mypy in CI, since nothing else enforces them.

On 3.14 annotations are evaluated lazily. In `lazy.py` a function used a class defined later in the file as `x: Later`, with no quotes and no `from __future__ import annotations`, and `f.__annotations__` printed the real class `Later`. The future import still works; it makes `__annotations__` hold plain strings (`{'x': 'Later', 'return': 'int'}`).

## --strict

A file `loose.py` had an untyped `load(s: str)` without return type, an untyped `risky(x)`, and some ignores. Plain `mypy loose.py` said `Success`, because by default mypy skips the body of unannotated functions and does not complain about missing annotations. `mypy --strict loose.py` found 4 errors:

```text
loose.py:5: error: Function is missing a return type annotation  [no-untyped-def]
loose.py:9: error: Function is missing a type annotation  [no-untyped-def]
loose.py:23: error: Unused "type: ignore" comment  [unused-ignore]
loose.py:24: error: Call to untyped function "risky" in typed context  [no-untyped-call]
```

On `bad.py` the count stayed 5 because those functions were already annotated; strict mostly bites on missing annotations.

## Escape hatches

- `Any` turns checking off for a value. `json.loads` returns `Any`, so everything after it is unchecked.
- `typing.cast(dict[str, Any], json.loads(s))` only tells the checker what to believe; at run time it does nothing and checks nothing.
- `# type: ignore` silences a line. In `loose.py`, `f("a")  # type: ignore` hid a real wrong-type call, and `y: int = 5  # type: ignore` was pointless: strict reported it as `Unused "type: ignore" comment`.

Hygiene: always write the code (`# type: ignore[assignment]`), keep a reason nearby, and enable `warn_unused_ignores` (part of `--strict`) so stale ignores get found.

## Compared with Go

Go checks types at compile time and you cannot opt out; Python's checking is a separate tool you adopt step by step. Go interfaces are also satisfied structurally, which is exactly what `Protocol` gives Python.

## A few things to watch

- Hints do nothing at run time; wire mypy into CI.
- Prefer `X | None` and handle the `None` branch.
- Annotate function signatures first; bodies get checked after.
- Use `cast` and `Any` rarely, and `type: ignore` with an error code.
- Adopt `--strict` per module on existing code, not all at once.

## Exercise

1. Add hints to a small script of yours and run mypy until it is clean.
2. Write a `Protocol` with one method and two unrelated classes that satisfy it.
3. Add an unused `# type: ignore` and see which flag reports it.

## What's next

The next post is "Testing in Python with pytest".
