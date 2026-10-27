+++
date = '2027-02-07T10:00:00+03:30'
draft = false
title = 'Classes and dataclasses in Python'
description = 'Python classes and dataclasses for Go and Node.js developers: properties, dunder methods, slots, MRO, Protocol and enum, all run on Python 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "classes", "dataclasses"]
cover = { image = "/images/covers/py-classes-dataclasses.png", alt = "Classes and dataclasses in Python", hiddenInSingle = true }
+++

In the [previous post](/posts/py-functions-generators/) we wrote functions, closures and generators. Now we group data and behavior: classes. Coming from Go, the closest thing to a struct with methods is [Go's structs and methods](/posts/go-structs-methods-interfaces/), and I compare with it only where I am sure.

> Everything ran with Python 3.14.0 on macOS (`python3 --version`). The demos are three local scripts. Byte counts are specific to this machine and version.

## A class, attributes and methods

```python
class Account:
    bank = "Demo"            # class attribute
    history = []             # shared mutable class attribute
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
print(a.bank, b.bank, Account.bank)
```

```text
[3, 7] [3, 7] True
Mine Demo Demo
```

`self` is explicit: it is just the first parameter. A `@classmethod` gets the class (an alternative constructor), a `@staticmethod` gets nothing. The gotcha: `history` lives on the class, so both accounts share one list. Assigning `a.bank` creates an instance attribute and leaves the class untouched. Put mutable state in `__init__`.

## Properties

A `@property` keeps the attribute syntax while running code:

```python
@property
def celsius(self): return self._c
@celsius.setter
def celsius(self, v):
    if v < -273.15: raise ValueError("below absolute zero")
    self._c = v
```

```text
212.0                              # Temp(100).fahrenheit, a computed property
ValueError: below absolute zero    # t.celsius = -300
```

So you start with a plain attribute and add validation later without changing callers.

## Dunder methods

A {{< term "dunder-method" "dunder method" >}} is what Python calls behind the syntax. `__repr__` is for developers (and lists), `__str__` is for display:

```text
repr(p) = P(1, 2)   str(p) = (1; 2)   [p] = [P(1, 2)]   p == q -> True
TypeError: cannot use 'P' as a set element (unhashable type: 'P')
```

Defining `__eq__` without `__hash__` sets `__hash__` to `None`, so `{p}` fails. Adding `__hash__` based on the same fields fixed it: two equal points gave a set of length 1. For ordering, write `__eq__` and `__lt__` and let `functools.total_ordering` fill in `<=`, `>` and `>=`: `V(1) <= V(2)` and `sorted(...)` worked.

## dataclass

That is a lot of boilerplate, so a {{< term "dataclass" "dataclass" >}} generates it:

```python
@dataclass
class Item:
    name: str
    price: float = 0.0
    tags: list[str] = field(default_factory=list)
    def __post_init__(self):
        if self.price < 0: raise ValueError("price must be >= 0")
```

```text
Item(name='pen', price=1.5, tags=[]) True False
ValueError: price must be >= 0
ValueError: mutable default <class 'list'> for field xs is not allowed: use default_factory
```

The first line is the generated `__repr__`, then `==` on equal and different items. `__post_init__` is where validation goes, and a bare `[]` default is rejected, which protects you from the shared-list gotcha above.

`@dataclass(frozen=True, order=True)` made `Ver(1, 2) < Ver(1, 10)` true, raised `FrozenInstanceError: cannot assign to field 'major'` on assignment, and was hashable (a set of two equal values had length 1). A `NamedTuple` is the immutable, tuple-like alternative: `NT(x=1, y=2)` unpacks and indexes like a tuple. I use a dataclass when I want methods, defaults or mutability.

## Memory and slots

Normal instances keep attributes in a per-instance `__dict__`. With `@dataclass(slots=True)` the {{< term "slots" "slots" >}} are fixed. I created 100,000 instances of a three-int class and measured with `tracemalloc`:

```text
Plain    10403616 bytes  (104 per object)
Slotted   6400928 bytes  (64 per object)
AttributeError: 'Slotted' object has no attribute 'd' and no __dict__ for setting new attributes
```

About 40 bytes saved per object here, and you cannot add new attributes. Worth it for millions of small objects, not otherwise.

## Inheritance, MRO and composition

```python
class Dog(Animal):
    def speak(self): return super().speak() + " (woof)"
```

This printed `rex makes a sound (woof)`. With a diamond (`D(B, C)`, both extending `A`) the {{< term "mro" "MRO" >}} decides the order, and `super()` follows it:

```text
['D', 'B', 'C', 'A', 'object']
D>B>C>A
```

Each `who()` called `super().who()` once, so every class ran exactly once. My rule: prefer composition (`Car` holds an `Engine` and calls `self.engine.start()`, which printed `vroom`) and inherit only for a real "is a" relation.

## Protocol: duck typing made explicit

Python uses {{< term "duck-typing" "duck typing" >}}: anything with `speak()` works. A `typing.Protocol` writes that shape down as {{< term "structural-typing" "structural typing" >}}:

```python
class Speaker(Protocol):
    def speak(self) -> str: ...
def talk(s: Speaker): return s.speak()
```

`Robot` never mentions `Speaker` and still satisfies it, like a Go interface, which is satisfied implicitly. The difference: a Protocol is checked by the type checker, not at run time. I did not run a type checker here. At run time `talk(42)` failed with `AttributeError: 'int' object has no attribute 'speak'`, and `isinstance(Robot(), Speaker)` raised `TypeError: Instance and class checks can only be used with @runtime_checkable protocols`. With `@runtime_checkable`, `isinstance` returned `True` for `Robot` and `False` for `42` (it only checks that the method exists).

## enum

```python
class Status(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
```

`Status("active")` gives `Status.ACTIVE`, `.name` is `ACTIVE`, `.value` is `active`, and `Status("nope")` raises `ValueError: 'nope' is not a valid Status`.

## A few things to watch

- Mutable class attributes are shared. Create lists and dicts in `__init__` or with `default_factory`.
- Define `__eq__` and you lose `__hash__` unless you define it too.
- `auto()` after a string value failed for me with `TypeError: unable to increment 'active'`. Do not mix them.
- A Protocol is not enforced at run time. Run a type checker if you want that.
- `frozen=True` stops attribute assignment only, not mutation of a list inside.

## Exercise

1. Write a `Money` frozen dataclass with `amount` (int cents) and `currency`, validate in `__post_init__`, and add an `__add__` method.
2. Print the MRO of a class with two parents and predict the order first.
3. Measure plain versus `slots=True` for five fields with `tracemalloc`.

## What's next

The next post is "Errors and context managers in Python".
