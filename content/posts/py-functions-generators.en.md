+++
date = '2027-01-28T10:00:00+03:30'
draft = false
title = 'Functions, closures and generators in Python'
description = 'Python functions, closures, decorators and generators for Go and Node.js developers: parameter kinds, late binding, yield, itertools and lru_cache on 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "functions", "closures", "generators"]
cover = { image = "/images/covers/py-functions-generators.png", alt = "Functions, closures and generators in Python", hiddenInSingle = true }
+++

In the [previous post](/posts/py-types-control-flow/) we covered types and control flow. Functions are where Python starts to feel different from Go. They are ordinary objects, they can be wrapped by {{< term "decorator" "decorators" >}}, and a function can pause in the middle and resume later. I compare with [Go's functions](/posts/go-functions-defer-errors/) only where I am sure, and [the Node.js event loop](/posts/node-event-loop/) is useful background for the closures section.

> Everything ran with Python 3.14.0 on macOS. The demo files are local scripts: `params.py`, `closures.py`, `gens.py`.

## Parameters

`/` ends the positional-only parameters, `*` starts the keyword-only ones:

```python
def f(a, b, /, c, *, d=0):
    return (a, b, c, d)
```

```text
f(1, 2, 3, d=4)  -> (1, 2, 3, 4)
f(a=1, b=2, c=3) -> TypeError: f() got some positional-only arguments passed as keyword arguments: 'a, b'
f(1, 2, 3, 4)    -> TypeError: f() takes 3 positional arguments but 4 were given
```

Defaults are evaluated once, when `def` runs, and that causes the classic bug:

```python
def add_item(x, bucket=[]):
    bucket.append(x)
    return bucket
```

```text
[1, 2, 3] [1, 2, 3] [1, 2, 3]
```

All three calls returned the same list (printing happens after all calls, so you see the final state three times). The fix is `bucket=None` and `if bucket is None: bucket = []`; two calls then print `[1] [2]`.

`*args` collects extra positionals into a tuple and `**kwargs` collects keywords into a dict. `show(1, 2, x=3)` printed `(1, 2) {'x': 3}`, and `show(*[1, 2], **{"y": 4})` unpacks on the call side.

## Closures

Functions are values, and an inner function keeps the variables it uses. That is a {{< term "closure" "closure" >}}. To rebind (not just mutate) an outer variable you need `nonlocal`:

```python
def make_counter():
    count = 0
    def inc():
        nonlocal count
        count += 1
        return count
    return inc
```

Two counters are independent: `c1(), c1(), c2()` printed `1 2 1`. Without `nonlocal`, `n += 1` raised `UnboundLocalError: cannot access local variable 'n' where it is not associated with a value`.

The real gotcha is {{< term "late-binding" "late binding" >}}: a closure looks the variable up when it runs.

```python
fs = [lambda: i for i in range(3)]
print([f() for f in fs])          # [2, 2, 2]
fs = [lambda i=i: i for i in range(3)]
print([f() for f in fs])          # [0, 1, 2]
```

Every lambda saw the final `i`. A default argument (`i=i`) freezes the value; `functools.partial` printed `[0, 1, 2]` too.

## Decorators

A decorator is a function that takes a function and returns a replacement. My `@timed` counts calls instead of measuring time:

```python
def timed(fn):
    def wrapper(*a, **k):
        wrapper.calls += 1
        return fn(*a, **k)
    wrapper.calls = 0
    return wrapper
```

Without `functools.wraps`, the decorated function lost its identity. I ran the same function with and without `@functools.wraps(fn)`:

```text
wrapper None 2
hello2 say hello 3
```

The first line is `__name__`, `__doc__` and `calls` without `wraps`. A decorator with arguments is one more level. This `@retry(times=3)` wraps a function that fails twice, deterministically:

```text
  attempt 1 failed: boom #1
  attempt 2 failed: boom #2
ok after 3 calls
```

With `times=2` and a function that always fails, it printed two attempts and then `gave up: down`: the last attempt re-raises.

## Generators

A function with `yield` returns a generator and runs nothing until you ask. The prints prove it:

```text
created, nothing printed yet
start
yield 1
1
yield 2
2
end
StopIteration
```

This is {{< term "lazy-evaluation" "lazy evaluation" >}}. The memory difference is deterministic: `sys.getsizeof` of `list(range(1_000_000))` is 8000056 bytes, of the generator expression `(x for x in range(1_000_000))` it is 200 bytes (the size of the generator object, not of its future values). Also, a generator is single use: the first `sum` gave `499999500000`, the second gave `0`.

`yield from` delegates to another generator: `list(outer())` gave `[0, 1, 2, 3]`. Generators can also receive values with `send()`; that is all I will say about it.

## The iterator protocol

`for` calls `iter()` and then `__next__()` until `StopIteration`. A hand-written {{< term "iterator" "iterator" >}}:

```python
class Countdown:
    def __init__(self, n): self.n = n
    def __iter__(self): return self
    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1
```

`list(Countdown(3))` gave `[3, 2, 1]`. Generators are just the short way to write this.

## itertools and lru_cache

```text
list(islice(naturals(), 5))      [0, 1, 2, 3, 4]
list(chain([1, 2], "ab", (9,)))  [1, 2, 'a', 'b', 9]
```

`islice` cuts an infinite generator. `groupby` only groups *adjacent* items. On `["apple", "avocado", "banana", "blueberry", "apricot"]` by first letter it printed three groups, with `a` twice; on the sorted list it printed two groups.

{{< term "memoization" "Memoization" >}} comes with `@functools.lru_cache`. For a recursive `fib(30)`, `cache_info()` printed `CacheInfo(hits=28, misses=31, maxsize=None, currsize=31)`: 31 distinct inputs computed once each.

## Compared with Go

Go has closures too, and they capture variables by reference. I did not test Go's loop-variable semantics here. Go has no `yield` generators; I ran a tiny program with `iter.Seq[int]` in Go 1.26, a function that takes a `yield func(int) bool` callback, and `for v := range Count(3)` printed `1 2 3`. It is push-based, unlike Python's pull-based `next()`.

## A few things to watch

- Never use a mutable default argument; use `None`.
- Closures capture variables, not values: fix loops with `i=i`.
- Always use `functools.wraps` in decorators.
- `groupby` needs sorted input, and a generator can be consumed only once.
- `lru_cache` arguments must be hashable.

## Exercise

1. Write `@count_calls` that exposes `.calls`, then add `@retry` on top of it.
2. Write a generator `chunks(iterable, n)` using `islice`.
3. Reproduce the `groupby` gotcha and fix it two ways.

## What's next

The next post is "Classes and dataclasses in Python".
