+++
date = '2027-01-18T10:00:00+03:30'
draft = false
title = 'Types and control flow in Python'
description = 'Python types and control flow for Go and Node.js developers: strong dynamic typing, int, float, str, references, for-else and match, all run on 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/py-types-control-flow.png", alt = "Types and control flow in Python", hiddenInSingle = true }
+++

In the [previous post](/posts/py-environment-uv-venv/) we set up the Python environment with venv and uv. Now we need the building blocks: types, names and control flow. If you came from Go like me, the biggest shift is that types live on values, not on variables. I compare with [Go's types and control flow](/posts/go-types-control-flow/) only where I am sure of the facts.

> Everything below ran with Python 3.14.0 on macOS (`python3 --version` prints `Python 3.14.0`). The demo files are local scripts, `basics.py` and `flow.py`. For syntax errors I show only the last line of the output.

## Dynamic, but strong

A name can point to any value, but Python does not guess conversions between unrelated types:

```python
try:
    1 + '1'
except TypeError as e:
    print("TypeError:", e)
```

```text
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

The check happens at run time, not at compile time. That is the difference from Go, where the same mistake is a compile error.

## Numbers

`int` has {{< term "arbitrary-precision" "arbitrary precision" >}} integers: `2**200` just works, where Go's `int` has a fixed width.

```text
>>> 2**200
1606938044258990275541962092341162602522202993782792835301376
>>> 0.1 + 0.2
0.30000000000000004
>>> 0.1 + 0.2 == 0.3
False
>>> Decimal('0.1') + Decimal('0.2')
Decimal('0.3')
>>> Fraction(1, 10) + Fraction(2, 10)
Fraction(3, 10)
```

`float` is the usual binary floating point, so `0.1 + 0.2` is inexact. For money use `decimal.Decimal` (build it from a string, not a float), or `fractions.Fraction` for exact ratios.

## Strings and bytes

`str` is an immutable sequence of Unicode characters. `bytes` is a different type, and they never compare equal:

```python
s = 'سلام'
print(len(s), len(s.encode()), s.encode())
print(s[1:3], s[::-1])
s[0] = 'x'
print(b'abc'[0], 'abc'.encode() == b'abc', 'abc' == b'abc')
```

```text
4 8 b'\xd8\xb3\xd9\x84\xd8\xa7\xd9\x85'
لا مالس
TypeError: 'str' object does not support item assignment
97 True False
```

Four characters, eight UTF-8 bytes. Unlike Go, indexing a `str` gives characters, so `len` and slicing work on text directly. `s[1:3]` and `s[::-1]` work per character, so the reversed text is just the characters in the opposite order.

F-strings take format specs after a colon:

```python
name, price = 'Roham', 1234.5678
print(f'{name:>8}|{price:,.2f}|{42:05d}|{255:#x}|{0.256:.1%}')
```

```text
   Roham|1,234.57|00042|0xff|25.6%
```

## Truthiness and None

Every object has a {{< term "truthiness" "truthiness" >}}. I ran `bool()` on a few:

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

Empty containers and zero are false. `[0]` is true because the list is not empty. Compare to `None` with `is`, not `==`: `x is None` asks about identity and cannot be fooled by a custom `__eq__`.

## Names are references

A name is a label on an object, not a box that holds a value:

```python
a = [1, 2, 3]
b = a
b.append(4)
print(a, a is b, id(a) == id(b))

nested = [[1], [2]]
sh = nested.copy()          # shallow
dp = copy.deepcopy(nested)  # deep
nested[0].append(99)
print(sh, dp)
```

```text
[1, 2, 3, 4] True True
[[1, 99], [2]] [[1], [2]]
```

`b = a` copies nothing. A {{< term "shallow-copy" "shallow copy" >}} duplicates only the outer list, so the inner lists are still shared. `copy.deepcopy` copies everything.

There is also an identity gotcha: `int('1000') is int('1000')` printed `False`, while `int('100') is int('100')` printed `True`. That is a CPython implementation detail (small integers are reused), so never use `is` to compare numbers.

## Control flow

Blocks are made by indentation, and a block header ends with a colon. Both mistakes give errors at parse time:

```text
IndentationError: expected an indented block after 'if' statement on line 1
SyntaxError: expected ':'
IndentationError: unindent does not match any outer indentation level
```

`if/elif/else`, the conditional expression and `for` over iterables:

```python
label = 'adult' if age >= 18 else 'minor'
for i in range(10, 0, -3): print(i, end=' ')      # 10 7 4 1
for name, score in zip(['a', 'b', 'c'], [90, 80]):
    print(name, score)                              # a 90, b 80
```

`zip` stops at the shortest input, so `c` is dropped. `enumerate` gives index and value.

Loops can have an `else` that runs only if no `break` happened:

```python
for i, v in enumerate([3, 5, 7]):
    if v == 9:
        print('found at', i)
        break
else:
    print('not found')       # printed
```

The {{< term "walrus-operator" "walrus operator" >}} assigns inside an expression, and a {{< term "list-comprehension" "list comprehension" >}} builds a list in one line (this is all I plan to say about comprehensions):

```python
if (k := len(data)) > 5:
    print('long list of', k)             # long list of 6
print([x * x for x in data if x % 2 == 0])   # [4, 16, 36]
```

## match

{{< term "structural-pattern-matching" "Structural pattern matching" >}} destructures values: literals, sequences, mappings, classes, guards. This is the body of a `describe(v)` function, with a dataclass `Point`:

```python
match v:
    case 0: return 'zero'
    case int(n) if n < 0: return f'negative {n}'
    case [first, *rest]: return f'list starting {first}, {len(rest)} more'
    case {'status': 'ok', 'items': items}: return f'ok with {len(items)} items'
    case Point(x=0, y=0): return 'origin'
    case Point(x=x, y=y): return f'point {x},{y}'
    case str() | bytes(): return 'text'
    case _: return 'other'
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

Cases are tried top to bottom. The guard (`if n < 0`) is the `-5` case, `Point(x=0, y=0)` is a class pattern, and `case _` is the default.

## A few things to watch

- I named a script `types.py` and every import broke with `cannot import name 'GenericAlias' from 'types'`. Never name your files like standard library modules.
- `float` for money is a bug. Use `Decimal` built from strings.
- `is` is for `None` (and other singletons), `==` is for values.
- Assignment shares objects. Copy explicitly when you need independence, and remember `copy()` is shallow.
- `for ... else` reads oddly: think "else = no break".

## Exercise

1. Print `len` of `'é'` written as one character and as `'e'` plus a combining accent (`'é'`), and explain the result.
2. Write `classify(v)` with `match` for ints, empty lists and dicts with a `"type"` key.
3. Use `for ... else` to find the first number divisible by 7 in a list, printing a message if there is none.

## What's next

The next post is "Functions, closures and generators in Python".
