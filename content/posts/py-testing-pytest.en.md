+++
date = '2027-03-24T10:00:00+03:30'
draft = false
title = 'Testing in Python with pytest'
description = 'Testing in Python with pytest: assertion rewriting, fixtures, parametrize, monkeypatch, mock and coverage, all run with pytest 9.1.1 on Python 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "pytest", "testing", "fixtures", "coverage"]
cover = { image = "/images/covers/py-testing-pytest.png", alt = "Testing in Python with pytest", hiddenInSingle = true }
+++

In the [previous post](/posts/py-type-hints-mypy/) we added type hints and mypy; types catch one class of bugs, tests catch the rest. Python ships `unittest`, but almost everyone uses pytest. It is a {{< term "test-runner" "test runner" >}} that finds `test_*` functions and lets you write plain `assert`. If you know [Go's table-driven tests](/posts/go-testing-basics/) the ideas will feel familiar, and I wrote about the test mindset in [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/).

> Everything ran with Python 3.14.0, pytest 9.1.1 and pytest-cov 7.1.0 (`pytest --version`) in a throwaway venv, now deleted. The demo is a tiny local `app/` package with a `tests/` folder; home paths are redacted.

## Plain assert and its failure output

No `self.assertEqual`; you write `assert a == b`. pytest rewrites the assert when it imports the test, so failures explain themselves. I compared two lists and two dicts:

```text
E       assert [1, 2, 3, 4] == [1, 2, 9, 4]
E         At index 2 diff: 3 != 9
E       AssertionError: assert {'a': 1, 'b': 2} == {'a': 1, 'b': 3}
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'b': 2} != {'b': 3}
```

The tool pointed at the differing index and key. `-v` or `-vv` shows more.

One gotcha I hit for real: my tests did `from app import pricing` and collection failed with `ModuleNotFoundError: No module named 'app'`. Adding `pythonpath = .` to `pytest.ini` fixed it.

## Fixtures

A {{< term "fixture" "fixture" >}} prepares what a test needs. The test names it as a parameter. With `yield`, the code after it is teardown (like a {{< term "context-manager" "context manager" >}} from [Errors and context managers in Python](/posts/py-errors-context-managers/)). I put these in `conftest.py`, which pytest loads automatically so every test in the folder can use them:

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

Two tests used both; the log printed at the end of the session was:

```text
setup  test_order_a
teardown test_order_a
setup  test_order_b
teardown test_order_b
```

The function-scoped fixture ran per test, while with `-s` the module-scoped one printed `[module fixture setup]` once, before the first test that needed it, and `[module fixture teardown]` once after the last test of the file.

## Built-in fixtures

- `tmp_path`: a fresh temporary directory. I wrote a JSON file there and loaded it with the code under test.
- `monkeypatch`: {{< term "monkeypatch" "monkeypatching" >}} undone after the test. `monkeypatch.setenv("RATE", "2.5")` made `get_rate()` return `2.5`, and the next test without it got the default `1.0`.
- `capsys`: captures stdout. `greet("roham")` produced exactly `"hello roham\n"`.

## Parametrize

A {{< term "parametrized-test" "parametrized test" >}} runs one body over many rows. Go has the same idea as a table plus `t.Run`; here each row is its own test:

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

## Expected errors

```python
with pytest.raises(ValueError, match=r"out of range: 120"):
    pricing.apply_discount(10, 120)
```

`match` is a regex searched in the message, so the test fails if a different `ValueError` appears.

## Markers and selection

I marked one test `@pytest.mark.slow` (registered in `pytest.ini`, otherwise pytest warns). Then: `-m "not slow"` gave `12 passed, 1 deselected`, `-m slow` gave `1 passed, 12 deselected`, and `-k "discount and not bad"` selected the 3 parametrized rows (`3 passed, 10 deselected`).

## Mocking, and its trap

`unittest.mock` replaces a dependency. `welcome(7)` calls `fetch_user`, which would hit the network:

```python
with mock.patch("app.service.fetch_user", return_value={"name": "Ana"}) as m:
    assert service.welcome(7) == "welcome Ana"
m.assert_called_once_with(7)
```

It passed. Patch where the name is *looked up* (`app.service.fetch_user`), not where it is defined. A mock is a {{< term "test-double" "test double" >}}, and over-mocking is the trap: I patched `apply_discount` itself to return 999 and asserted 999. It passed, and tested nothing. Also, a typo like `m.assert_called_once_wiht(1)` is not silently ignored: it raised `AttributeError ... Did you mean: 'assert_called_once_with'?`. Mock only the edges (network, clock), never the logic you want to test.

## Property-based testing

Instead of examples, {{< term "property-based-testing" "property-based testing" >}} states a rule and generates inputs; see [Property-based testing](/posts/eng-property-based-testing/). The usual pytest tool is Hypothesis. I did not install or run it for this post, so I show no output.

## Coverage

```text
Name              Stmts   Miss  Cover   Missing
app/pricing.py       17      3    82%   20-22
app/service.py        6      1    83%   5
TOTAL                23      4    83%
```

From `pytest --cov=app --cov-report=term-missing`. Lines 20-22 of `pricing.py` are `unused_branch`, which no test calls; line 5 of `service.py` is the real `fetch_user` that I always patched. {{< term "code-coverage" "Coverage" >}} says what ran, not whether the asserts are good.

## A few things to watch

- Tests need `pythonpath` or an installed package, or imports fail.
- Patch the name where it is used.
- Prefer fixtures over setup code copied between tests.
- Register custom markers.
- Chasing 100% coverage rewards weak tests.

## Exercise

1. Write a fixture that yields a temp SQLite file and deletes it afterwards, then prove the order with `-s`.
2. Parametrize a `slugify` function with `ids`, including an empty string.
3. Cover `unused_branch` and watch the `Missing` column shrink.

## What's next

The next post is "The GIL and threading".
