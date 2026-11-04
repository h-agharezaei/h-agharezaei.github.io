+++
date = '2027-03-24T10:00:00+03:30'
draft = false
title = 'Testing in Python with pytest'
description = 'Testing in Python with pytest: assertion rewriting, fixtures, parametrize, monkeypatch, mock and coverage, all run with pytest 9.1.1 on Python 3.14.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "pytest", "testing", "fixtures", "coverage"]
cover = { image = "/images/covers/py-testing-pytest.png", alt = "Testing in Python with pytest", hiddenInSingle = true }
+++

Here is a test that passes and proves nothing. It replaces the function under test with a fake that returns 999, and then asserts that the function returns 999. Green, every time. I will come back to it, because it is the most important trap in testing: a green test only means something if it could have failed.

The previous post, [Type hints and mypy](/posts/py-type-hints-mypy/), catches one kind of bug: values of the wrong type. Tests catch the rest, the cases where the types are fine and the behavior is wrong. Python ships a test module called `unittest`, but almost everyone uses **pytest**. It is a {{< term "test-runner" "test runner" >}}: a program that finds your tests, runs them and reports which ones failed and why.

The core idea is small. A test is just a function whose name starts with `test_`. pytest finds it, calls it, and if it finishes without raising an exception, the test passes. The check itself is a plain `assert` statement. That is all you need to start. If you know [table-driven tests in Go](/posts/go-testing-basics/), the ideas will feel familiar, and I wrote about the thinking behind tests in [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/).

> I re-ran everything with Python 3.14.0, pytest 9.1.1 and pytest-cov 7.1.0 (`pytest --version`), in a scratch copy of the demo and a throwaway virtual environment. The demo is a tiny local `app/` package with a `tests/` folder. Home paths are left out. The scratch tests for the failing asserts, the 999 test and the mock typo are not in the demo folder; I ran them in the scratch copy.

## The code under test

The demo has a small module, `app/pricing.py`, with a function that applies a percentage discount:

```python
def apply_discount(price, percent):
    if not 0 <= percent <= 100:
        raise ValueError(f"percent out of range: {percent}")
    return round(price * (100 - percent) / 100, 2)
```

and `app/service.py`, which uses a function that would call the network:

```python
def fetch_user(uid):
    raise RuntimeError("would hit the network")

def welcome(uid):
    user = fetch_user(uid)
    return f"welcome {user['name']}"
```

The first test is a function and an assert:

```python
def test_plain_assert():
    assert pricing.apply_discount(200, 10) == 180.0
```

## Plain assert and its failure output

In `unittest` you write `self.assertEqual(a, b)` inside a class. In pytest you write `assert a == b`. That looks like it would tell you nothing when it fails, but pytest rewrites the assert statements of your test files when it imports them, so the failure message explains itself. I made two tests fail on purpose, one comparing two lists and one comparing two dicts:

```text
E       assert [1, 2, 3, 4] == [1, 2, 9, 4]
E
E         At index 2 diff: 3 != 9
E         Use -v to get more diff
E       AssertionError: assert {'a': 1, 'b': 2} == {'a': 1, 'b': 3}
E
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'b': 2} != {'b': 3}
E         Use -v to get more diff
```

(I removed the file paths and the code lines.) You do not have to compare the lists by eye: pytest points at the index that differs, and for the dict it points at the key and omits the items that match. `-v` or `-vv` shows more.

One gotcha hit me here. My tests did `from app import pricing`, and when I ran the `pytest` command collection failed with `ModuleNotFoundError: No module named 'app'`. The `tests/` folder is put on the import path, but the project root is not. Adding `pythonpath = .` to `pytest.ini` fixed it. (If you start it as `python -m pytest`, the current folder is added to the path, and the problem hides. I checked both ways.)

## Fixtures

Many tests need some setup first: a temporary file, a configured object, a connection. If you copy that setup into every test, the tests get long and fragile. pytest has a better answer, the {{< term "fixture" "fixture" >}}.

A fixture is a function that prepares something a test needs. The test asks for it simply by naming it as a parameter, and pytest runs the fixture and passes in the result. If the fixture uses `yield`, the code before it is the setup and the code after it is the teardown, which runs when the test is done, pass or fail. This is the same idea as a {{< term "context-manager" "context manager" >}} from [Errors and context managers in Python](/posts/py-errors-context-managers/). I put the fixtures in a file called `conftest.py`. pytest loads that file automatically, so every test in the folder can use them:

```python
@pytest.fixture
def order(request):
    LOG.append(f"setup  {request.node.name}")
    yield LOG
    LOG.append(f"teardown {request.node.name}")

@pytest.fixture(scope="module")
def shared():
    print("\n[module fixture setup]")
    yield {"n": 1}
    print("\n[module fixture teardown]")
```

The first fixture records the name of each test when it is set up and torn down. The second has `scope="module"`, which means it is created once for the whole test file and not once per test. Two tests, `test_order_a` and `test_order_b`, asked for both. At the end of the session `conftest.py` prints the log, and running with `-s` (which lets `print` through) gave:

```text
tests/test_pricing.py::test_order_a
[module fixture setup]
PASSED
tests/test_pricing.py::test_order_b PASSED
tests/test_pricing.py::test_slow_one PASSED
[module fixture teardown]
...
ORDER:
  setup  test_order_a
  teardown test_order_a
  setup  test_order_b
  teardown test_order_b
```

Look at how the two fixtures behave. The function-scoped one was set up and torn down around each test: setup, teardown, setup, teardown. The module-scoped one printed `[module fixture setup]` only once, just before the first test that needed it, and `[module fixture teardown]` only once, after the last test of the file, even though `test_slow_one` did not use it. Pick the scope by cost: a cheap object per test, an expensive one per module.

## Built-in fixtures

pytest also ships useful fixtures, and the demo uses three:

- `tmp_path` gives each test a fresh temporary directory. I wrote a JSON file there and loaded it with the code under test, so no test leaves files behind.
- `monkeypatch` changes things temporarily, an environment variable or an attribute, and puts them back after the test ({{< term "monkeypatch" "monkeypatching" >}}). `monkeypatch.setenv("RATE", "2.5")` made `get_rate()` return `2.5`, and the next test, which did not use it, got the default `1.0`.
- `capsys` captures what the code prints. `greet("roham")` printed exactly `"hello roham\n"`, and the test asserted on that string.

## Parametrize

Often you want the same test with several inputs. You could copy the test three times, or you could write a loop, but a loop stops at the first failure. A {{< term "parametrized-test" "parametrized test" >}} runs one body over many rows, and each row is reported as its own test. Go has the same idea as a table plus `t.Run`:

```python
@pytest.mark.parametrize("price,percent,expected",
    [(100, 0, 100.0), (100, 50, 50.0), (19.99, 10, 17.99)],
    ids=["none", "half", "cents"])
def test_discount(price, percent, expected): ...
```

```text
tests/test_pricing.py::test_discount[none] PASSED
tests/test_pricing.py::test_discount[half] PASSED
tests/test_pricing.py::test_discount[cents] PASSED
```

The first argument names the parameters, the list holds one tuple per case, and `ids` gives each case a readable name that shows up in the output. If the `cents` row failed, the report would say exactly which one.

## Expected errors

Sometimes the correct behavior is to fail. `pytest.raises` checks that:

```python
with pytest.raises(ValueError, match=r"out of range: 120"):
    pricing.apply_discount(10, 120)
```

The test passes only if the block raises a `ValueError`. `match` is a regular expression searched in the message, so the test also fails if a different `ValueError` shows up for another reason.

## Markers and selection

You can label tests and choose which to run. I marked one test with `@pytest.mark.slow`. The marker has to be registered in `pytest.ini` (the demo's file lists `slow`), otherwise pytest warns about an unknown marker. Then I ran with different filters:

- `-m "not slow"` gave `12 passed, 1 deselected`.
- `-m slow` gave `1 passed, 12 deselected`.
- `-k "discount and not bad"` picks tests by a part of their name and selected the 3 parametrized rows (`3 passed, 10 deselected`).

## Mocking, and its trap

Sometimes a test must not call the real thing, such as the network. `unittest.mock` replaces a dependency with a stand-in. `welcome(7)` calls `fetch_user`, which in the demo would fail, so the test replaces it:

```python
with mock.patch("app.service.fetch_user", return_value={"name": "Ana"}) as m:
    assert service.welcome(7) == "welcome Ana"
m.assert_called_once_with(7)
```

It passed. Two things to remember. First, patch where the name is *looked up*, here `app.service.fetch_user`, not where it is defined. Second, a mock is a {{< term "test-double" "test double" >}}, and the danger is over-mocking. Remember the test from the start: it patched `apply_discount` itself, to return 999, and asserted 999. In the scratch copy I ran that test and it passed, and it tests only the mock. The rule I follow: mock the edges of the system (network, clock, disk), never the logic you want to test.

A related detail: a typo in a mock assertion is not silently ignored. `m.assert_called_once_wiht(1)` raised an `AttributeError`, and the message ended with `Did you mean: 'assert_called_once_with'?`. That protects you from a test that checks nothing because of a spelling mistake.

## Property-based testing

Instead of listing examples, {{< term "property-based-testing" "property-based testing" >}} states a rule that must always hold and lets a tool generate many inputs; see [Property-based testing](/posts/eng-property-based-testing/). The usual tool with pytest is Hypothesis. I did not install or run it, so there is no output for it here.

## Coverage

How do you know which lines your tests never reach? Coverage measures it. With `pytest --cov=app --cov-report=term-missing`, the run printed:

```text
Name              Stmts   Miss  Cover   Missing
-----------------------------------------------
app/__init__.py       0      0   100%
app/pricing.py       17      3    82%   20-22
app/service.py        6      1    83%   5
-----------------------------------------------
TOTAL                23      4    83%
```

Read the `Missing` column. Lines 20 to 22 of `pricing.py` are the function `unused_branch`, which no test calls. Line 5 of `service.py` is the body of the real `fetch_user`, which I always replaced with a mock. {{< term "code-coverage" "Coverage" >}} tells you which lines ran, not whether the asserts were any good. A test with no `assert` can give 100%.

## Common testing traps

- Tests need `pythonpath` or an installed package, otherwise the imports fail, as we saw with `ModuleNotFoundError`.
- Patch the name where it is used, not where it is defined, or the patch has no effect.
- Prefer fixtures over setup code copied between tests; they also clean up even when a test fails.
- Register custom markers, so pytest warns you about a misspelled marker name.
- Chasing 100% coverage rewards weak tests that only run lines. Use the report to find untested code, not as a score.

## Exercise

1. Write a fixture that yields a temp SQLite file and deletes it afterwards, then prove the order with `-s`.
2. Parametrize a `slugify` function with `ids`, including an empty string.
3. Cover `unused_branch` and watch the `Missing` column shrink.

## What's next

Tested code is correct on one thread, so the next post is "The GIL and threading", about what changes when the same code runs concurrently.
