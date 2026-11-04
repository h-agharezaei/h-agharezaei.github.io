+++
date = '2027-02-07T10:00:00+03:30'
draft = false
title = 'Classes and dataclasses in Python'
description = 'Python classes and dataclasses for Go and Node.js developers: properties, dunder methods, slots, MRO, Protocol and enum, all run on Python 3.14.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "classes", "dataclasses"]
cover = { image = "/images/covers/py-classes-dataclasses.png", alt = "Classes and dataclasses in Python", hiddenInSingle = true }
+++

Here is a small bank account class, and a surprise:

```python
class Account:
    history = []
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance
    def deposit(self, n):
        self.balance += n
        self.history.append(n)
```

If I create two separate accounts, deposit 3 into the first and 7 into the second, and print each account's `history`, both print `[3, 7]`. Two accounts, one history. The reason is a difference you do not have in Go: a Python class can hold data in two places, on the class itself (shared by everyone) and on each instance (private). Most of what is confusing about Python classes is knowing which of the two you are touching.

This post goes from plain classes to `dataclass`, which removes most of the boilerplate. It follows [functions, closures and generators](/posts/py-functions-generators/), because a method is just a function that lives on a class. If you come from Go, the nearest thing is [Go's structs and methods](/posts/go-structs-methods-interfaces/), and I compare with it only where I am sure.

> Everything ran with Python 3.14.0 on macOS (`python3 --version`). The demos are three local scripts: `a.py`, `b.py` and `c.py`. Byte counts depend on this machine and this Python version.

## A class, attributes and methods

A class is a blueprint, and each call like `Account("ali", 10)` builds an object (an *instance*) from it. Python runs `__init__` on the new object, and `self` is that object. Unlike Go's receiver or JavaScript's `this`, `self` is explicit: it is simply the first parameter of every method, and you write it yourself. Here is the full demo class:

```python
class Account:
    bank = "Demo"            # class attribute
    history = []             # shared mutable class attribute (gotcha)
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance
    def deposit(self, n):
        self.balance += n
        self.history.append(n)
    @classmethod
    def from_string(cls, s):
        o, b = s.split(":")
        return cls(o, int(b))
    @staticmethod
    def valid(n): return n > 0

a, b = Account("ali", 10), Account.from_string("sara:5")
a.deposit(3); b.deposit(7)
print(a.history, b.history, a.history is b.history)
a.bank = "Mine"
print(a.bank, b.bank, Account.bank, Account.valid(3))
```

```text
[3, 7] [3, 7] True
Mine Demo Demo True
```

Two kinds of attribute are in play here. `bank` and `history` are written directly in the class body, so they are **class attributes**: one copy, shared. `owner` and `balance` are assigned through `self` inside `__init__`, so every instance has its own.

- **First output line:** `history` is a class attribute holding a list. `a.deposit(3)` and `b.deposit(7)` both did `self.history.append(...)`. Python looks for `history` on the instance, does not find it, and falls back to the class, so both appended to the one shared list. `a.history is b.history` confirms that it is the same object. The fix is to create the list in `__init__`: `self.history = []`.
- **Second output line:** `a.bank = "Mine"` does not change the class. It creates a new attribute on the instance `a` that hides the class one. `b` and the class still say `Demo`. (Assigning creates; the sharing trap comes from *mutating* a shared object.)

Two decorators appear. `@classmethod` receives the class itself (here as `cls`), which makes it a natural place for an alternative constructor: `Account.from_string("sara:5")` builds an account from a string. `@staticmethod` receives nothing special; it is an ordinary function that happens to live in the class's namespace.

## Properties

Suppose `celsius` starts as a plain attribute and later you want to reject impossible values. In Java you would have written getters and setters from day one. In Python you can wait, because a `@property` keeps the plain attribute syntax while running code behind it:

```python
class Temp:
    def __init__(self, c): self.celsius = c
    @property
    def celsius(self): return self._c
    @celsius.setter
    def celsius(self, v):
        if v < -273.15: raise ValueError("below absolute zero")
        self._c = v
    @property
    def fahrenheit(self): return self._c * 9 / 5 + 32

t = Temp(100); print(t.fahrenheit)
try: t.celsius = -300
except ValueError as e: print("ValueError:", e)
```

```text
212.0
ValueError: below absolute zero
```

`t.fahrenheit` looks like an attribute but is computed on every access. Assigning `t.celsius = -300` looks like a plain assignment but runs the setter, which rejects it. The real value lives in `_c`; the leading underscore is only a convention that says "internal". Callers never change how they write `t.celsius`, so you can add validation later without breaking anything.

## Dunder methods

How does `print(p)` know how to show your object, and how does `p == q` work? Python calls special methods whose names have double underscores on both sides, called {{< term "dunder-method" "dunder methods" >}} (from "double underscore"). You rarely call them yourself; Python calls them behind the syntax. Here is a small point class that defines three of them:

```python
class P:
    def __init__(self, x, y): self.x, self.y = x, y
    def __repr__(self): return f"P({self.x}, {self.y})"
    def __str__(self): return f"({self.x}; {self.y})"
    def __eq__(self, o): return (self.x, self.y) == (o.x, o.y)
p, q = P(1, 2), P(1, 2)
print(repr(p), str(p), p == q, [p])
try: {p}
except TypeError as e: print("TypeError:", e)
print(P.__hash__)
```

```text
P(1, 2) (1; 2) True [P(1, 2)]
TypeError: cannot use 'P' as a set element (unhashable type: 'P')
None
```

- `__repr__` is for developers: an unambiguous text, ideally one that looks like code. `__str__` is for display to a user, and `print` uses it. When objects sit inside a list, Python shows each item with `__repr__`, which is why `[p]` printed `[P(1, 2)]` and not `[(1; 2)]`.
- `__eq__` makes `p == q` compare by content (`True`), not by identity.
- Then comes a surprise. Putting `p` into a set failed with "unhashable type". When you define `__eq__` without `__hash__`, Python sets `__hash__` to `None`, which the last line shows. The reasoning is that two objects that are equal must have equal hashes, and Python will not guess how to compute yours.

Adding a `__hash__` that uses the same fields fixes it: in the demo a subclass with `def __hash__(self): return hash((self.x, self.y))` made a set of two equal points have length 1.

For ordering, you do not need to write all six comparison methods. Write `__eq__` and `__lt__`, and `functools.total_ordering` fills in `<=`, `>` and `>=`. With a small class `V`, `V(1) <= V(2)` and `V(3) > V(2)` were both `True`, and `sorted([V(3), V(1)])` gave `[V(1), V(3)]`.

## dataclass

Look at what `P` needed: an `__init__`, a `__repr__`, an `__eq__`, and still a `__hash__`. That is a lot of repeated code for a class that only holds data. A {{< term "dataclass" "dataclass" >}} generates it from the field list. You write the fields with type annotations, and the `@dataclass` decorator builds the methods:

```python
@dataclass
class Item:
    name: str
    price: float = 0.0
    tags: list[str] = field(default_factory=list)
    def __post_init__(self):
        if self.price < 0: raise ValueError("price must be >= 0")

i = Item("pen", 1.5)
print(i, i == Item("pen", 1.5), i == Item("pen", 2))
try: Item("x", -1)
except ValueError as e: print("ValueError:", e)
```

```text
Item(name='pen', price=1.5, tags=[]) True False
ValueError: price must be >= 0
```

The first line shows the generated `__repr__`, then `==` on an equal item (`True`) and a different one (`False`). Equality compares all fields. `__post_init__` runs right after the generated `__init__`, which makes it the place for validation: the second line is the `ValueError` for a negative price. The annotations (`str`, `float`) are not enforced at run time; Python does not check them here.

One more detail, and it connects to the shared-list trap above. The `tags` field uses `field(default_factory=list)`, which means "call `list()` for each new instance". The demo also tried a bare `[]` default:

```text
ValueError: mutable default <class 'list'> for field xs is not allowed: use default_factory
```

The dataclass refuses it and tells you what to use instead, so it protects you from the shared-default bug we saw in the previous post.

Two common options are `frozen` and `order`. With `@dataclass(frozen=True, order=True)`, a `Ver(major, minor)` class behaves like this:

```python
v = Ver(1, 2)
try: v.major = 3
except FrozenInstanceError as e: print("FrozenInstanceError:", e)
print(Ver(1, 2) < Ver(1, 10), hash(v) == hash(Ver(1, 2)), len({v, Ver(1, 2)}))
```

```text
FrozenInstanceError: cannot assign to field 'major'
True True 1
```

Assigning to a field raises `FrozenInstanceError`. `order=True` gives comparison, so `Ver(1, 2) < Ver(1, 10)` is `True`. And a frozen dataclass is hashable, so two equal values collapse to one element in a set (length 1).

If you only need an immutable bundle of values, `typing.NamedTuple` is a lighter alternative: `NT(x=1, y=2)` prints like a dataclass but also unpacks and indexes like a tuple (the demo printed `NT(x=1, y=2) 1 3` for the instance, its first element and `a + b` after unpacking). I use a dataclass when I want methods, defaults or mutability.

## Memory and slots

A normal instance keeps its attributes in a dictionary, `__dict__`, which lets you add attributes whenever you like. With `@dataclass(slots=True)` the attribute names are fixed in advance ({{< term "slots" "slots" >}}), and instances have no `__dict__`. I created 100,000 instances of a class with three int fields, in two versions, and measured with `tracemalloc`:

```text
Plain    10403616 bytes  (104 per object)
Slotted   6400928 bytes  (64 per object)
AttributeError: 'Slotted' object has no attribute 'd' and no __dict__ for setting new attributes
```

In the same demo `hasattr(..., "__dict__")` was `True` for the plain class and `False` for the slotted one. These totals include the list that holds the objects (8 bytes per entry), which is why the slotted figure is 64 and not the 56 that `sys.getsizeof` reports for one instance. The saving is about 40 bytes per object here, and the cost is the last line: you cannot add an attribute that is not declared. It is worth it for millions of small objects, not otherwise.

## Inheritance, MRO and composition

Inheritance works as you would expect. A subclass can call its parent's version with `super()`:

```python
class Dog(Animal):
    def __init__(self, name, trick):
        super().__init__(name); self.trick = trick
    def speak(self): return super().speak() + " (woof)"
```

`Dog("rex", "sit").speak()` printed `rex makes a sound (woof)`, and `isinstance(d, Animal)` was `True`. Python also allows several parents. In the "diamond" shape, `D(B, C)` where both `B` and `C` extend `A`, which `who()` runs first? The {{< term "mro" "MRO" >}} (method resolution order) decides, and `super()` follows it:

```text
['D', 'B', 'C', 'A', 'object']
D>B>C>A
```

The first line is `D.__mro__`: look in `D`, then `B`, then `C`, then `A`. Each `who()` called `super().who()`, so the second line shows every class ran exactly once, in that order, and `A` was not run twice. My rule is to prefer composition and inherit only for a real "is a" relation. For example, `Car` holds an `Engine` and calls `self.engine.start()`, which printed `vroom`.

## Protocol: duck typing made explicit

Python uses {{< term "duck-typing" "duck typing" >}}: if an object has a `speak()` method, you can call `speak()` on it, and its class does not matter. A `typing.Protocol` writes that expectation down. It is {{< term "structural-typing" "structural typing" >}}: a type matches when it has the right methods.

```python
class Speaker(Protocol):
    def speak(self) -> str: ...
def talk(s: Speaker): return s.speak()
```

`Robot` has a `speak()` method and never mentions `Speaker`, and it still satisfies it, which is like a Go interface being satisfied implicitly. The difference is who checks. A Protocol is for the **type checker**, not for run time, and I did not run a type checker here. At run time `talk(42)` failed with `AttributeError: 'int' object has no attribute 'speak'`, and a plain `isinstance(Robot(), Speaker)` raised:

```text
TypeError: Instance and class checks can only be used with @runtime_checkable protocols
```

With `@runtime_checkable`, `isinstance` returned `True` for `Robot` and `False` for `42`. It only checks that the method exists, not its signature.

## enum

When a value can only be one of a few named options, use an `Enum`:

```python
class Status(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
```

`Status("active")` gives `Status.ACTIVE`, whose `.name` is `ACTIVE` and `.value` is `active`. `Status.BLOCKED is Status("blocked")` is `True`, so you compare enum members with `is`. `Status("nope")` raises `ValueError: 'nope' is not a valid Status`.

## Where classes surprise you

- **Mutable class attributes are shared.** A list or dict written in the class body is one object for all instances. Create it in `__init__`, or with `default_factory` in a dataclass.
- **Defining `__eq__` removes `__hash__`.** Your objects stop working in sets and as dict keys until you define `__hash__` too (or use a frozen dataclass).
- **Mixing `auto()` with string values.** In the demo, an `Enum` with `A = "active"` followed by `B = auto()` raised `TypeError: unable to increment 'active'`, because `auto()` tries to add one to the previous value. Do not mix them.
- **A Protocol is not enforced at run time.** Run a type checker if you want it checked.
- **`frozen=True` blocks assignment only.** A frozen dataclass with a list field still lets you `append` to that list: I ran it and got `F(xs=[1])`.

## Exercise

1. Write a `Money` frozen dataclass with `amount` (int cents) and `currency`, validate in `__post_init__`, and add an `__add__` method.
2. Print the MRO of a class with two parents and predict the order first.
3. Measure plain versus `slots=True` for five fields with `tracemalloc`.

## What's next

The next post is "Errors and context managers in Python". Custom exceptions are classes too, so everything here applies to them.
