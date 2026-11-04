+++
date = '2027-01-28T10:00:00+03:30'
draft = false
title = 'Functions, closures and generators in Python'
description = 'Python functions, closures, decorators and generators for Go and Node.js developers: parameter kinds, late binding, yield, itertools and lru_cache on 3.14.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "functions", "closures", "generators"]
cover = { image = "/images/covers/py-functions-generators.png", alt = "Functions, closures and generators in Python", hiddenInSingle = true }
+++

What does this function print?

```python
def add_item(x, bucket=[]):
    bucket.append(x)
    return bucket

print(add_item(1), add_item(2), add_item(3))
```

You might expect `[1] [2] [3]`, because each call starts with an empty `bucket`. It prints `[1, 2, 3] [1, 2, 3] [1, 2, 3]`. This small bug is a good doorway into how Python treats functions. They are not special declarations that the compiler sets up once. They are ordinary objects, created when the `def` line runs, and everything about them (their default values, the variables they remember, even a pause in the middle of their body) follows from that.

In this post I go through four things that grow out of this idea: how parameters work, closures (functions that remember), decorators (functions that wrap functions), and generators (functions that can pause). It builds on [types, names and control flow](/posts/py-types-control-flow/), and in particular on the idea that a name is a label on an object. I compare with [Go's functions](/posts/go-functions-defer-errors/) only where I am sure, and [the Node.js event loop](/posts/node-event-loop/) is useful background for the closures section.

> Everything ran with Python 3.14.0 on macOS. The demo files are local scripts: `params.py`, `closures.py`, `gens.py`, and a tiny Go program for the last comparison.

## Parameters

Python parameters have more options than Go's. In this signature, `/` ends the positional-only parameters and `*` starts the keyword-only ones:

```python
def f(a, b, /, c, *, d=0):
    return (a, b, c, d)
```

Before `/`, a caller must pass arguments by position. After `*`, a caller must pass them by name. In between (`c`), both ways work. Here are three calls and what they gave:

```text
f(1, 2, 3, d=4)  -> (1, 2, 3, 4)
f(a=1, b=2, c=3) -> TypeError: f() got some positional-only arguments passed as keyword arguments: 'a, b'
f(1, 2, 3, 4)    -> TypeError: f() takes 3 positional arguments but 4 were given
```

The first call is fine. The second tries to pass `a` and `b` by name, which `/` forbids. The third passes `d` by position, which `*` forbids, so Python counts four positional arguments where only three are allowed. Keyword-only parameters are useful for flags: `f(1, 2, 3, d=4)` is readable at the call site, while a bare `4` would not be.

Now back to the puzzle at the top. The answer is that **default values are evaluated once, when `def` runs**, not on every call. The empty list `[]` is created one time and stored inside the function object. Every call that does not pass `bucket` gets that same list. The three calls above all appended to it. (The printing happens after all three calls finish, so you see the final state three times.)

The fix is to use `None` as the default and create the list inside the function:

```python
def add_item_fixed(x, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(x)
    return bucket

print(add_item_fixed(1), add_item_fixed(2))
```

```text
[1] [2]
```

Now each call that gets no list creates its own. The same trap applies to any mutable default, such as `{}` or `set()`.

Two more parameter forms. `*args` collects extra positional arguments into a tuple, and `**kwargs` collects extra named ones into a dict. The `*` and `**` also work on the calling side, to unpack a list or a dict into arguments:

```python
def show(*args, **kwargs):
    print(args, kwargs)

show(1, 2, x=3)
show(*[1, 2], **{"y": 4})
```

```text
(1, 2) {'x': 3}
(1, 2) {'y': 4}
```

## Closures

Since functions are values, you can return one from another function. And an inner function keeps access to the variables of the function it was defined in, even after the outer function has finished. That is a {{< term "closure" "closure" >}}. A counter is the smallest useful example:

```python
def make_counter():
    count = 0
    def inc():
        nonlocal count
        count += 1
        return count
    return inc

c1, c2 = make_counter(), make_counter()
print(c1(), c1(), c2())
```

```text
1 2 1
```

Each call to `make_counter()` creates its own `count`, and the `inc` it returns remembers that one. So `c1` counts 1, 2 and `c2`, which has its own variable, starts again at 1. The two counters are independent.

The `nonlocal` line matters. Inside `inc`, writing `count += 1` would normally make `count` a new local variable of `inc`. `nonlocal` says "I mean the `count` of the enclosing function", which lets you **rebind** it. (Just reading it, or mutating a list it points to, needs no `nonlocal`.) Without it, the same function fails:

```text
UnboundLocalError: cannot access local variable 'n' where it is not associated with a value
```

The demo's second version has `n += 1` in the inner function without `nonlocal`. Python sees an assignment, treats `n` as local, and finds that it has no value yet.

The real gotcha with closures is {{< term "late-binding" "late binding" >}}: a closure looks a variable up when it runs, not when it is created. Watch this loop:

```python
fs = [lambda: i for i in range(3)]
print([f() for f in fs])          # [2, 2, 2]
fs = [lambda i=i: i for i in range(3)]
print([f() for f in fs])          # [0, 1, 2]
```

In the first line we make three small functions that each return `i`. But all three look at the same variable `i`, and by the time we call them the loop has ended and `i` is 2, so every function returns 2. In the second line, `i=i` makes the current value a default argument. Defaults are evaluated when the function is created (the same rule that caused our bug above, now working for us), so each lambda keeps its own value. In the demo, `functools.partial(lambda i: i, i)` also printed `[0, 1, 2]`.

## Decorators

A decorator is a function that takes a function and returns a replacement for it. The `@name` line above a `def` is just a short way of writing `hello = name(hello)`. My `@timed` is a simple one: it counts calls (I called it `timed` but it does not measure time):

```python
def timed(fn):
    def wrapper(*a, **k):
        wrapper.calls += 1
        return fn(*a, **k)
    wrapper.calls = 0
    return wrapper
```

`wrapper` accepts any arguments, bumps a counter stored on the function itself (functions are objects, so they can carry attributes), and calls the original. There is a cost: the decorated function is now really `wrapper`, so it loses its own name and docstring. The fix is `functools.wraps(fn)`. I ran the same function once with `@timed` and once with a version using `@functools.wraps(fn)`:

```text
wrapper None 2
hello2 say hello 3
```

Each line is `__name__`, `__doc__` and `calls`. In the first line the function says its name is `wrapper` and has no docstring. In the second, `wraps` copied the original name and docstring over (`hello2`, `say hello`). The counts are 2 and 3 because I called them two and three times. Debuggers, logs and documentation tools all use `__name__`, so always use `wraps`.

A decorator that takes arguments adds one more level: a function that returns the decorator. This `@retry(times=3)` calls a function again if it raises `ConnectionError`. The test function fails the first two times and succeeds on the third, so the demo is deterministic:

```text
  attempt 1 failed: boom #1
  attempt 2 failed: boom #2
ok after 3 calls
```

Two failures are caught and printed, and the third call returns normally. With `times=2` and a function that always fails, it printed two attempts and then `gave up: down`: on the last attempt the exception is re-raised instead of swallowed, so the caller still learns that it failed.

## Generators

Here is the question behind generators: what if a function could return a value and then continue from where it stopped, the next time you ask? In Python, any function that contains `yield` does that. Calling it does not run its body. It returns a **generator**, an object that runs the body only when you ask for the next value. This demo makes that visible by printing inside the function:

```python
def count_to(n):
    print("start")
    for i in range(1, n + 1):
        print("yield", i)
        yield i
    print("end")

g = count_to(2)
print("created, nothing printed yet")
print(next(g))
print(next(g))
try:
    next(g)
except StopIteration:
    print("StopIteration")
```

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

Follow it line by line:

1. `g = count_to(2)` ran nothing. The first thing printed is our own message.
2. The first `next(g)` runs the body from the top until the first `yield`: it prints `start` and `yield 1`, then stops and hands out `1`. Our `print` shows `1`.
3. The second `next(g)` resumes right after that `yield`. The loop continues, prints `yield 2`, and hands out `2`.
4. The third `next(g)` resumes again. The loop is over, `end` is printed, the body finishes, and Python raises `StopIteration` to say there is nothing more.

This is {{< term "lazy-evaluation" "lazy evaluation" >}}: work happens only when somebody asks for a value, one value at a time. A `for` loop does these `next` calls and catches `StopIteration` for you.

The practical win is memory. These numbers come from `sys.getsizeof`: for `list(range(1_000_000))` it is 8000056 bytes, and for the generator expression `(x for x in range(1_000_000))` it is 200 bytes. The list holds a million entries. The generator is a small object that produces them on demand (so 200 bytes is the size of the generator itself, not of its future values; and the list number is the size of the list's own storage, without counting the integer objects). The price is that a generator is single use. In the demo, the first `sum` of the generator gave `499999500000`, and the second gave `0`, because the generator was already exhausted.

A generator can also delegate to another one with `yield from`, and it can receive values with `send()`. Here they are in one demo:

```python
def inner():
    yield 1
    yield 2
def outer():
    yield 0
    yield from inner()
    yield 3
print(list(outer()))

def acc():
    total = 0
    while True:
        x = yield total
        total += x
a = acc(); next(a)
print(a.send(5), a.send(10))
```

```text
[0, 1, 2, 3]
5 15
```

`outer` yields 0, then hands over to `inner` (which yields 1 and 2), then yields 3. In `acc`, `yield total` both gives out the running total and receives the value passed to `send()`. The first `next(a)` just runs up to the first `yield`; after that `send(5)` makes the total 5 and `send(10)` makes it 15. That is all I will say about `send()`: it is rarely needed.

## The iterator protocol

How does `for` know what to do with a generator, a list or a file? Through a small agreement called the {{< term "iterator" "iterator" >}} protocol. `for` calls `iter()` on the object to get an iterator, then calls `__next__()` repeatedly until `StopIteration` is raised. You can write one by hand:

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

```text
[3, 2, 1]
2 1
exhausted
```

The first line is `list(Countdown(3))`. The next two come from calling `next` by hand on `iter(Countdown(2))`: it gives 2, then 1, and the third call raises `StopIteration` (the demo prints `exhausted`). Generators are just the short way to write this: Python builds the `__iter__` and `__next__` for you.

## itertools and lru_cache

The standard library has ready-made tools for iterators. Two from the demo:

```text
list(islice(naturals(), 5))      [0, 1, 2, 3, 4]
list(chain([1, 2], "ab", (9,)))  [1, 2, 'a', 'b', 9]
```

`naturals()` is an infinite generator (`0, 1, 2, ...`). Because it is lazy, `islice` can take just the first five and stop. `chain` joins several iterables into one stream.

`groupby` has a trap: it groups only **adjacent** items. On `["apple", "avocado", "banana", "blueberry", "apricot"]`, grouped by first letter, the demo printed:

```text
[('a', ['apple', 'avocado']), ('b', ['banana', 'blueberry']), ('a', ['apricot'])]
[('a', ['apple', 'apricot', 'avocado']), ('b', ['banana', 'blueberry'])]
```

The first line is the unsorted list: three groups, with `a` appearing twice, because `apricot` is not next to the other `a` words. The second line is the sorted list: two groups. If you want one group per key, sort first.

{{< term "memoization" "Memoization" >}} means remembering a function's results for inputs it has already seen. In Python it is one line, `@functools.lru_cache`. For a recursive Fibonacci, which would otherwise repeat the same calls over and over, `fib(30)` returned `832040` and `cache_info()` printed:

```text
CacheInfo(hits=28, misses=31, maxsize=None, currsize=31)
```

There are 31 distinct inputs (0 to 30), each computed once (the 31 misses), and the other calls (28 hits) were answered from the cache.

## Compared with Go

Go has closures too, and they capture variables, not values, just like Python's. (Go 1.22 changed `for` loops so each iteration gets a new variable; I did not test Go's loop-variable behavior here.) Go has no `yield` keyword. Since Go 1.23 it has range-over-function iterators, and I ran a tiny program with `iter.Seq[int]` (a function that takes a `yield func(int) bool` callback) with Go 1.27.3; `for v := range Count(3)` printed 1, 2 and 3, one per line. It is push-based: the iterator function calls your loop body. Python's generator is pull-based: you call `next()` and the generator hands out a value.

## Common mistakes with functions and generators

- **A mutable default argument.** `bucket=[]` is created once and shared by every call. Use `None` and build the list inside.
- **Expecting closures to capture values.** They capture variables, and look them up when called. In a loop, use `i=i` (or `functools.partial`) to freeze the current value.
- **A decorator without `functools.wraps`.** The wrapped function loses its name and docstring, which makes logs and tracebacks confusing.
- **`groupby` on unsorted data.** It groups neighbors only, so sort by the same key first.
- **Reusing a generator.** It can be consumed once; a second pass sees nothing (the second `sum` above gave 0).
- **Unhashable arguments to `lru_cache`.** The cache uses the arguments as dict keys, so lists and dicts as arguments raise an error.

## Exercise

1. Write `@count_calls` that exposes `.calls`, then add `@retry` on top of it.
2. Write a generator `chunks(iterable, n)` using `islice`.
3. Reproduce the `groupby` gotcha and fix it two ways.

## What's next

The next post is "Classes and dataclasses in Python", where data and behavior come together: functions that live on objects.
