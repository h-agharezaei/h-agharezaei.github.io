+++
date = '2027-03-11T10:00:00+03:30'
draft = false
title = 'Type hints and mypy'
description = 'Python type hints and mypy: list[int], X | None, TypedDict, Protocol, PEP 695 generics, real mypy errors, --strict, cast and type: ignore on 3.14.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "type-hints", "mypy", "typing"]
cover = { image = "/images/covers/py-type-hints-mypy.png", alt = "Type hints and mypy", hiddenInSingle = true }
+++

Picture a function that adds up the prices in an order. In every test you wrote, the prices are numbers, so it works. Then one day a price arrives from a JSON file as the string `"12.5"`, and the function fails with a `TypeError`, but only on the one code path that nobody exercised. Python does not look at types until the line actually runs, so this kind of mistake waits quietly for the worst moment.

Type hints are Python's answer. A {{< term "type-hint" "type hint" >}} is a note you write next to a parameter or a return value that says what type it should be: `def total(prices: list[float]) -> float`. The simplest way to think about it is this: **a type hint is documentation written in a form that a tool can check**. The tool is a {{< term "type-checker" "type checker" >}}, and the most common one is mypy. It reads your code without running it and tells you where the hints and the code disagree. The Python interpreter itself ignores the hints completely.

If you come from [Go's static types](/posts/go-types-control-flow/), this is the big difference to keep in mind: in Go the compiler refuses to build a program with a type error. In Python the checking is a separate step that you choose to add. The previous post, [Errors and context managers in Python](/posts/py-errors-context-managers/), was about errors that show up while the program runs. Hints and mypy catch a whole group of them earlier, before the program runs. We also used [dataclasses](/posts/py-classes-dataclasses/) before, and they fit naturally with hints.

> I ran the Python parts of this post on Python 3.14.0 (`python3 --version`). The mypy outputs below (the error lists and the `--strict` run) are from the original run of this post, with mypy 2.4.0 in a throwaway virtual environment that I deleted afterwards; I could not install mypy again while rewriting the post, so I did not re-run those. The demo is four small local files.

## The interpreter does not check hints

Let me start with the surprising part. This function says it takes an `int`:

```python
def f(a: int) -> int:
    return a * 2
```

Calling `f('ab')` does not fail. It prints `abab`, because `'ab' * 2` is a perfectly valid thing to do in Python. The hints are stored on the function and nothing more: `f.__annotations__` is `{'a': <class 'int'>, 'return': <class 'int'>}`.

Sometimes a wrong call does fail, but the error comes from the code, not from the hint. Take this function and the same kind of wrong call:

```python
def total_of(xs: list[int]) -> int:
    return sum(xs)
print(total_of(['1', '2']))
```

```text
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

This error came from `sum`, when it tried to add `'1'` to its starting value `0`. The hint `list[int]` played no part. So the first rule is: **hints do nothing at run time**. If you want them to protect you, something has to read them, and that something is a checker you run yourself or in CI.

## A typed module

Here are the kinds of hints you will use most. This is the demo file `good.py`:

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

Going through them one by one:

- `list[str]` and `dict[str, int]` say what is inside a container: a list of strings, a dictionary from strings to integers. You write them with the plain built-in names.
- `User | None` means "either a `User` or `None`". `dict.get` can return `None` when the key is missing, so honest code says so in the return type.
- `TypedDict` describes a dictionary whose keys are known, here `name` and `age`. At run time it is still an ordinary `dict`.
- `first[T]` is a {{< term "generics" "generic" >}} function: it works for a list of anything, and the result has the same type as the list's items. `first(["p", "q"])` is a `str`, `first([1, 2])` is an `int`. This `[T]` syntax needs Python 3.12 or newer (it comes from PEP 695), and replaces the older `TypeVar`.
- `Protocol` describes a shape instead of a name. Any class that has a `close()` method taking no arguments counts as a `Closer`, even if it never mentions `Closer`. This is {{< term "structural-typing" "structural typing" >}}. It is the static version of {{< term "duck-typing" "duck typing" >}}: "if it has `close()`, it can be closed".

The full file also has a `Conn` class and a `shutdown(c: Closer)` function. Running `python3 -I good.py` printed:

```text
6 {'a': 2, 'b': 1}
{'name': 'x', 'age': 3} p Order(id=1, total=9.5)
closed
```

and in the original run, `mypy good.py` printed `Success: no issues found in 1 source file`.

## What mypy catches

A second file, `bad.py`, makes four mistakes on purpose. Here are the lines that matter, with their line numbers:

```python
12  def sign(n: int) -> str:
13      if n > 0:
14          return "pos"
15      elif n < 0:
16          return "neg"        # no else: n == 0 returns nothing
...
23  class Bad:
24      def close(self, force: bool) -> None: ...
...
31  print(total_of(["1", "2"]))          # list of str, expected list of int
32  print(find({"a": 1}, "a").bit_length())   # find() may return None
33  shutdown(Bad())                      # Bad.close needs an argument
```

This is what mypy said (original run):

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

(I put each note on one line.) Reading it from the top:

- Line 12: `sign` promises a `str`, but when `n` is `0` no branch returns anything. Python would quietly return `None`.
- Line 31, twice: the list holds two strings, and the function wants integers. mypy reports each item.
- Line 32: `find` returns `int | None`, and `None` has no `bit_length`. This is the same family of mistakes as a nil pointer dereference in Go: the checker forces you to deal with the "missing" case. The fix is `r = find(...)` followed by `if r is not None:` before using `r`.
- Line 33: `Bad` has a `close`, but with an extra required argument, so it does not match the `Closer` shape. The two `note` lines show the difference.

Every one of these would have failed only when that line ran. Here mypy found all four without running anything.

## Python 3.14 evaluates annotations lazily

One practical detail. Annotations used to be evaluated when the function was defined, so a hint that named a class defined later in the file was an error, and people wrote it in quotes (`"Later"`) or used `from __future__ import annotations`. In Python 3.14 annotations are evaluated lazily, on demand. The demo file `lazy.py` uses a class before it is defined, with no quotes and no future import:

```python
def f(x: Later) -> Later:
    return x

class Later: ...

print(f.__annotations__)
```

```text
{'x': <class '__main__.Later'>, 'return': <class '__main__.Later'>}
```

It works, and the annotations hold the real class. The future import still works and then keeps plain strings: in a separate scratch file with `from __future__ import annotations` the annotations printed as `{'x': 'Later', 'return': 'int'}`.

## --strict

By default mypy is gentle with old, unannotated code: it skips the body of a function that has no annotations and does not complain that annotations are missing. The demo file `loose.py` has a `load(s: str)` without a return type, a completely untyped `risky(x)`, and a few `type: ignore` comments. In the original run plain `mypy loose.py` said `Success`. With `--strict`, mypy found 4 errors:

```text
loose.py:5: error: Function is missing a return type annotation  [no-untyped-def]
loose.py:9: error: Function is missing a type annotation  [no-untyped-def]
loose.py:23: error: Unused "type: ignore" comment  [unused-ignore]
loose.py:24: error: Call to untyped function "risky" in typed context  [no-untyped-call]
```

The first two are the missing annotations on `load` and `risky`. The third is an ignore comment that is not needed, and the fourth is a typed call into a function that has no types. On `bad.py` the count stayed at 5 in the original run, because those functions were already annotated. `--strict` mostly matters for code that is only partly annotated.

## Escape hatches, and how to use them safely

Sometimes the checker cannot know something, or you need to move on. Python has three ways to say "trust me", and each one turns checking off a little:

- `Any` means "any type at all"; checking stops for that value. `json.loads` returns `Any`, so everything you read from the result is unchecked.
- `typing.cast(dict[str, Any], json.loads(s))` tells the checker what to believe. At run time it does nothing and checks nothing, so a wrong cast is a lie that no tool will catch.
- `# type: ignore` silences all errors on a line. In `loose.py` the line `f("a")  # type: ignore` hides a real wrong-type call. The line `y: int = 5  # type: ignore` was pointless, and strict mode reported it as `Unused "type: ignore" comment`.

To keep these under control, write the error code (`# type: ignore[assignment]`) so you only silence the error you meant, keep a reason next to it, and turn on `warn_unused_ignores` (it is part of `--strict`) so that ignores that are no longer needed get found.

## How I would adopt hints

- Remember that hints do nothing at run time. Run mypy in CI, otherwise they are only comments.
- Prefer `X | None` and handle the `None` case, instead of hoping a value is there.
- Annotate function signatures first. Mypy checks the body of a function only once it has annotations, so signatures give the most for the least work.
- Use `cast` and `Any` rarely, and `type: ignore` always with an error code.
- On an existing project, turn on `--strict` one module at a time, not for the whole code base at once.

Go interfaces are also satisfied structurally, which is exactly what `Protocol` gives Python. The difference is that in Go the compiler enforces it, while in Python you adopt the checker step by step.

## Exercise

1. Add hints to a small script of yours and run mypy until it is clean.
2. Write a `Protocol` with one method and two unrelated classes that satisfy it.
3. Add an unused `# type: ignore` and see which flag reports it.

## What's next

Types catch only one kind of bug, so the next post is "Testing in Python with pytest", about checking the behavior that types cannot describe.
