+++
date = '2027-01-18T10:00:00+03:30'
draft = false
title = 'Types and control flow in Python'
description = 'Python types and control flow for Go and Node.js developers: strong dynamic typing, int, float, str, references, for-else and match, all run on 3.14.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/py-types-control-flow.png", alt = "Types and control flow in Python", hiddenInSingle = true }
+++

Here are three lines of Python:

```python
a = [1, 2, 3]
b = a
b.append(4)
```

Now print `a`. It is `[1, 2, 3, 4]`. I only touched `b`, but `a` changed too. In many languages assignment feels like "put this value in that box", and this result looks like a bug. In Python it is the normal rule, and for someone coming from Go like me it is the biggest change in the basics.

The idea is this: in Python the **type belongs to the value, not to the variable**. A variable is only a name, a label that you stick on an object. `b = a` does not copy anything; it sticks a second label on the same object. Several things in this post follow from that one sentence: why there are no type declarations, why copying a list needs care, and why `is` and `==` are different questions.

[The previous post](/posts/py-environment-uv-venv/) gave us a working environment, so now we can write code. I will go through types, names and control flow in that order. I compare with [Go's types and control flow](/posts/go-types-control-flow/) only where I am sure of the facts.

> Everything below ran with Python 3.14.0 on macOS (`python3 --version` prints `Python 3.14.0`). The demo files are local scripts: `basics.py`, `flow.py`, `ident.py` and three tiny files with deliberate syntax errors. For syntax errors I show only the last line of the output.

## Dynamic, but strong

In Go you write `var x int`, and `x` can never hold a string. In Python you do not declare anything. A name can point to an `int` now and to a `str` a moment later:

```python
x = 5
print(type(x).__name__, x)
x = 'five'
print(type(x).__name__, x)
```

```text
int 5
str five
```

This is what people call **dynamic typing**: types are checked while the program runs, not before. It does not mean Python is careless about types. The value `5` is always an `int`, and Python will not quietly turn it into a string for you (this is sometimes called *strong* typing, and it is where Python differs from JavaScript):

```python
try:
    1 + '1'
except TypeError as e:
    print("TypeError:", e)
```

```text
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

The error appears only when this line actually runs. In Go the same mistake is a compile error, and the program never starts. That is the real price of dynamic typing: a mistake on a rarely executed line stays hidden until somebody executes it. Later in the series we will see how type hints and a checker bring part of that safety back.

## Numbers

Python has three kinds of numbers you will meet daily: `int`, `float` and, when you need exactness, `decimal.Decimal` and `fractions.Fraction`. The demo prints a few values:

```python
from decimal import Decimal
from fractions import Fraction

print(2**200)
print(0.1 + 0.2, 0.1 + 0.2 == 0.3)
print(Decimal('0.1') + Decimal('0.2'), Fraction(1, 10) + Fraction(2, 10))
```

```text
1606938044258990275541962092341162602522202993782792835301376
0.30000000000000004 False
0.3 3/10
```

Let us read it line by line:

- **The first line:** `int` has {{< term "arbitrary-precision" "arbitrary precision" >}}. It grows as large as it needs to, so `2**200` just works and never overflows. A Go `int`, by contrast, has a fixed width.
- **The second line:** `float` is ordinary binary floating point, the same as `float64` in Go or `number` in JavaScript. The computer cannot store `0.1` exactly in binary, so the sum is slightly off, and the comparison with `0.3` is `False`.
- **The third line:** `Decimal` does decimal arithmetic, so `0.1 + 0.2` is exactly `0.3`. `Fraction` keeps an exact ratio and prints `3/10`. (`print` shows the readable form; the `repr` form would be `Decimal('0.3')`.)

For money, use `Decimal`, and build it from a **string** like `'0.1'`. If you write `Decimal(0.1)` you hand it a float that is already inexact.

## Strings and bytes

A `str` is an immutable sequence of Unicode characters. `bytes` is a different type: raw numbers from 0 to 255. They never compare equal, even when they "look" the same:

```python
s = 'سلام'
print(len(s), len(s.encode()), s.encode())
print(s[1:3], s[::-1])
try:
    s[0] = 'x'
except TypeError as e:
    print("TypeError:", e)
print(b'abc'[0], 'abc'.encode() == b'abc', 'abc' == b'abc')
```

```text
4 8 b'\xd8\xb3\xd9\x84\xd8\xa7\xd9\x85'
لا مالس
TypeError: 'str' object does not support item assignment
97 True False
```

- **Line 1:** the word has 4 characters, but `s.encode()` turns it into UTF-8 bytes, and there are 8 of them (each of these Persian letters takes two bytes). `len` on a `str` counts characters; `len` on the encoded `bytes` counts bytes.
- **Line 2:** slicing and reversing work on characters. `s[1:3]` is the second and third letters, and `s[::-1]` is all four in reverse order (a terminal that shows right-to-left text can make this look odd). Unlike a Go `string`, which you index by byte, indexing a Python `str` gives you whole characters.
- **Line 3:** strings are immutable. You cannot assign to `s[0]`; you build a new string instead.
- **Line 4:** indexing `bytes` gives a number (`97` is `a`). The encoded string equals the bytes literal, but the `str` itself does not, because they are different types.

F-strings let you format values inside a string. After a colon you can give a format spec:

```python
name, price = 'Roham', 1234.5678
print(f'{name:>8}|{price:,.2f}|{42:05d}|{255:#x}|{0.256:.1%}')
```

```text
   Roham|1,234.57|00042|0xff|25.6%
```

In order: right-align in 8 characters, thousands separator with 2 decimals, zero-pad to 5 digits, hex with a `0x` prefix, and percent with one decimal.

## Truthiness and None

In an `if` or a `while`, Python does not need a real `bool`. Every object has a {{< term "truthiness" "truthiness" >}}: it counts as true or false when used as a condition. The demo runs `bool()` on a few values:

```text
     0 -> False
    '' -> False
    [] -> False
    {} -> False
  None -> False
   0.0 -> False
   'a' -> True
   [0] -> True
   0.1 -> True
```

The rule of thumb is "empty or zero is false". Zero numbers, empty strings, empty containers and `None` are false. Everything else is true: `[0]` is true because the list has one element, even though that element is zero. (According to the docs, your own classes are true unless they define `__bool__` or `__len__`.) This is why Python code writes `if items:` instead of `if len(items) > 0:`.

`None` is Python's "no value", similar to `nil` in Go or `null` in JavaScript. To check for it, use `is`, not `==`:

```python
x = None
print(x is None, x == None)
```

```text
True True
```

Both are `True` here, but `x is None` asks "is this the very same object?", and a class that defines its own `__eq__` cannot fool it. That leads us to the main topic of this post.

## Names are references

Back to the opening example. A name is a label on an object, not a box that holds a value. Two labels can point to one object:

```python
a = [1, 2, 3]
b = a
b.append(4)
print(a, a is b, id(a) == id(b))
```

```text
[1, 2, 3, 4] True True
```

`append` changed the one list that both names point to. `a is b` asks "are these the same object?" and `id()` returns the object's identity; both say yes. (The actual number `id` returns differs on every run, so I only compared it.)

If you want an independent list you must copy it. But a copy has levels. Take a list that contains lists:

```python
import copy
nested = [[1], [2]]
sh = nested.copy()          # shallow
dp = copy.deepcopy(nested)  # deep
nested[0].append(99)
print(sh, dp)
```

```text
[[1, 99], [2]] [[1], [2]]
```

A {{< term "shallow-copy" "shallow copy" >}} makes a new outer list, but its inner lists are the same objects as before. So when we changed an inner list through `nested`, `sh` saw the change. `copy.deepcopy` copies everything all the way down, so `dp` is unaffected.

There is one more identity surprise, from `ident.py`:

```python
a = int('1000'); b = int('1000')
print(a is b, a == b)
c = int('100'); d = int('100')
print(c is d, c == d)
```

```text
False True
True True
```

Both pairs are equal, but only the small numbers are the same object. This is an implementation detail of CPython (according to the docs, it keeps ready-made objects for small integers, from -5 to 256). It can even change inside one file: in `basics.py`, `n = 1000; m = 1000; n is m` printed `True`, because the compiler reuses one constant object for the two identical numbers in the same file. The lesson is not to memorise these cases but to never use `is` on numbers: `==` compares values, `is` compares identity, and you want `is` almost only for `None`.

## Control flow

Python marks blocks by indentation, not braces, and every block header ends with a colon. These are the three mistakes beginners meet first. Each one stops at parse time, before any line runs:

```text
IndentationError: expected an indented block after 'if' statement on line 1
SyntaxError: expected ':'
IndentationError: unindent does not match any outer indentation level
```

They come from three small files: a block with no indentation, an `if x > 2` without a colon, and a line that is dedented to a level that matches no enclosing block.

The conditional and loops look like this. `for` goes over any iterable, so you do not write a counter by hand:

```python
age = 20
label = 'adult' if age >= 18 else 'minor'
for i in range(10, 0, -3): print(i, end=' ')      # 10 7 4 1
for name, score in zip(['a', 'b', 'c'], [90, 80]):
    print(name, score)                              # a 90, b 80
```

The second line is the conditional expression (Python has no `?:`). `range(10, 0, -3)` counts from 10 down, three at a time, and stops before 0. `zip` walks two lists together and stops at the shortest one, so `c` is dropped. `enumerate` gives you the index and the value together; we use it next.

Python loops have an odd feature: an `else` that runs only if the loop finished without hitting `break`. It is meant for searching:

```python
def find(items, target):
    for i, v in enumerate(items):
        if v == target:
            print('found at', i)
            break
    else:
        print('not found')

find([3, 5, 7], 5)
find([3, 5, 7], 9)
```

```text
found at 1
not found
```

For the first call, `break` fires and the `else` is skipped. For the second, the loop runs to its end without a `break`, so `else` runs. Read it as "else = no break".

Two small tools remain. The {{< term "walrus-operator" "walrus operator" >}} `:=` assigns inside an expression, and a {{< term "list-comprehension" "list comprehension" >}} builds a list in one line. This is all I plan to say about comprehensions here:

```python
data = [1, 2, 3, 4, 5, 6]
if (k := len(data)) > 5:
    print('long list of', k)
print([x * x for x in data if x % 2 == 0])
```

```text
long list of 6
[4, 16, 36]
```

The walrus saved `len(data)` into `k` while testing it, so we could use `k` in the next line. The comprehension reads: "`x * x` for every `x` in `data`, but only when `x` is even".

## match

Python 3.10 added `match`. {{< term "structural-pattern-matching" "Structural pattern matching" >}} is like a `switch`, but it also takes values apart by their shape: literals, sequences, mappings and classes, with optional guards. The next function checks eight kinds of value (it uses a dataclass `Point`, which we will meet two posts from now; for now it is just a class with fields `x` and `y`):

```python
def describe(v):
    match v:
        case 0:
            return 'zero'
        case int(n) if n < 0:
            return f'negative {n}'
        case [first, *rest]:
            return f'list starting {first}, {len(rest)} more'
        case {'status': 'ok', 'items': items}:
            return f'ok with {len(items)} items'
        case Point(x=0, y=0):
            return 'origin'
        case Point(x=x, y=y):
            return f'point {x},{y}'
        case str() | bytes():
            return 'text'
        case _:
            return 'other'
```

```text
0 -> zero
-5 -> negative -5
[1, 2, 3] -> list starting 1, 2 more
{'status': 'ok', 'items': [1]} -> ok with 1 items
Point(x=0, y=0) -> origin
Point(x=1, y=2) -> point 1,2
'hi' -> text
3.5 -> other
```

Cases are tried from top to bottom, and the first match wins. `int(n) if n < 0` matches an `int` and binds it to `n`, but only when the guard (`n < 0`) is true, which is why `-5` lands there. `[first, *rest]` matches any sequence with at least one item and splits it. The dict pattern checks that the keys exist with those values and pulls out `items`. `Point(x=0, y=0)` is a class pattern, and the more general `Point(x=x, y=y)` after it catches every other point. The last `case _` is the default. One detail: a string is also a sequence, but Python does not treat `str` and `bytes` as sequences in `[first, *rest]` patterns, which is why `'hi'` reaches the `text` case.

## Common traps

- **Naming a script like a standard library module.** I named a script `types.py` once, and every import broke with `cannot import name 'GenericAlias' from 'types'`. Python found my file before the real module. Pick names that the standard library does not use.
- **Using `float` for money.** `0.1 + 0.2 != 0.3` is not a Python bug, it is how binary floating point works. Use `Decimal` built from strings.
- **Using `is` for values.** `is` is for `None` and other singletons. For everything else use `==`, as the `1000` example showed.
- **Forgetting that assignment shares objects.** Copy explicitly when you need independence, and remember that `copy()` is shallow: inner objects are still shared.
- **Misreading `for ... else`.** It does not mean "if the loop did not run". It means "if the loop did not `break`".

## Exercise

1. Print `len` of `'é'` written as one character and of `'é'` (an `e` followed by a combining accent), and explain the result. Also compare the two with `==`.
2. Write `classify(v)` with `match` for ints, empty lists and dicts with a `"type"` key.
3. Use `for ... else` to find the first number divisible by 7 in a list, printing a message if there is none.

## What's next

The next post is "Functions, closures and generators in Python". With values, names and control flow in place, the function is the next building block, and in Python functions are objects too.
