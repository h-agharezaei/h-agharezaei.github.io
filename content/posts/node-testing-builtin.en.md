+++
date = '2027-01-16T10:00:00+03:30'
draft = false
title = 'Testing in Node.js with node:test'
description = 'Testing in Node.js with node:test on v20.13.1: describe/it, hooks, mocks, mock timers, reporters, coverage, exit codes, and what is missing.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "testing", "node-test", "mocking", "coverage"]
cover = { image = "/images/covers/node-testing-builtin.png", alt = "Testing in Node.js with node:test", hiddenInSingle = true }
+++

You have a function and you want to be sure it keeps working after the next change. The classic answer is to install a test framework such as Jest or Mocha, with its config file and dozens of dependencies. In Node.js you do not need that to start: the standard library ships a {{< term "test-runner" "test runner" >}}, `node:test`, and the `node --test` command runs it. This is the Node counterpart of [Testing in Go](/posts/go-testing-basics/), where the tool is also built in.

In [Building an API with Fastify](/posts/node-fastify-api/) I got an API running; now I want to know that it keeps working. This post uses [async/await](/posts/node-promises-async-await/) and the [HTTP server](/posts/node-http-server/) from earlier posts. I also want to show one small surprise I ran into, because it is a good reminder: a green result is only trustworthy if you know how your tool behaves.

> Node v20.13.1 (printed by `node --version`). The demo is a local example: `price.js`, `app.js` and two files in `test/`. All outputs are real runs. Every output below has the durations removed, because the machine was busy (load average above 20) and timings would mean nothing.

## The basics

A test is a function that throws if something is wrong. `test()` registers one, and `describe()` and `it()` group tests, exactly as in other frameworks. For assertions, `node:assert/strict` makes every comparison strict (so `1` is not equal to `'1'`).

The code under test is a small function, `applyDiscount(price, percent)`, which returns the price after a percentage discount and throws a `RangeError` for a bad percentage. A table-driven test is just a `for ... of` loop over cases that creates one `it` for each (in Go the idiom is a slice of structs and `t.Run`):

```js
describe('applyDiscount cases', () => {
  const cases = [
    { price: 100, percent: 0, want: 100 },
    { price: 19.99, percent: 10, want: 17.99 },
  ];
  for (const c of cases) {
    it(`${c.price} at ${c.percent}%`, () => {
      assert.equal(applyDiscount(c.price, c.percent), c.want);
    });
  }
  it('throws on bad percent', () => {
    assert.throws(() => applyDiscount(10, 101), { name: 'RangeError', message: 'bad percent' });
  });
});
```

Async code needs nothing special: make the test function `async` or return a promise, and use `assert.rejects` for the failure case: `await assert.rejects(fetchUser(7, db), { message: 'not found' })`. Subtests use `await t.test(...)`. The option `{ skip: 'reason' }` skips a test and `{ todo: true }` marks work in progress.

There are four hooks to run setup and cleanup code: `before` and `after` (once per group), `beforeEach` and `afterEach` (around every test). My hooks test pushed each hook's name into an array and printed it at the end. For two tests the array was `before,beforeEach,afterEach,beforeEach,afterEach`: the hooks ran in the order you would expect.

## Running and reading results

`node --test` finds test files by itself, so you do not list them. In my demo it picked up the two files in `test/` and ignored `failing.js` in the project root; I had to name that file explicitly to run it. `--test-name-pattern=health` ran only the tests whose name matches and reported the other 12 as skipped. There is also `--watch`, which reruns tests when a file changes; I did not run it because it is interactive.

The `spec` reporter prints a readable tree. This is the real output for the whole demo, with durations and the long stack trace removed (the `…` lines):

```text
▶ http
  ✔ GET /health
  ✔ unknown path is 404
after, log = before,beforeEach,afterEach,beforeEach,afterEach
✔ applies a discount
▶ applyDiscount cases
  ✔ 100 at 0%
  ✔ 100 at 100%
  ✔ 19.99 at 10%
  ✔ throws on bad percent
▶ hooks
  ✔ one
  ✔ two
▶ async
  ✔ resolves
  ✔ rejects
  ﹣ skipped one # no network here
  ✖ later # TODO
    AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
    1 !== 2
    …
✔ mock.fn and mock.method
✔ injected time and randomness
✔ mock.timers
ℹ tests 17
ℹ suites 3
ℹ pass 15
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 1
```

Read it like this: `▶` opens a group and `✔` is a pass. The `﹣` line is the skipped test, with its reason after `#`. The `✖` line is the `todo` test: its assertion really fails (`1 !== 2`), but a test marked `todo` is not counted as a failure, so `fail` is 0 and the run still succeeds. That is useful for work in progress, and dangerous if you forget a real test there.

Other reporters exist. The dot reporter printed `...............X....`, one character per test (the `X` is the todo test). When the output is not a terminal, for example in a pipe or in CI, the default reporter on Node 20 is `tap`, a line-based format that begins with `TAP version 13`. A real failing test (the file `failing.js` compares `{ a: 1, b: [1, 2] }` with `{ a: 1, b: [1, 3] }`) shows a diff, and the process exits with code 1, which is what CI looks at:

```text
✖ bad sum
  AssertionError [ERR_ASSERTION]: Expected values to be strictly deep-equal:
  + actual - expected

    {
      a: 1,
      b: [
        1,
  +     2
  -     3
      ]
    }
```

The `+` line is what the code produced and the `-` line is what the test expected, so you see the difference right away.

## Mocks and injection

Sometimes a test must not call the real thing: a database, the clock, a random number generator. A **mock** is a stand-in that records how it was called. `mock.fn()` makes a recording function (`db.get.mock.callCount()`, `.calls[0].arguments`), and `mock.method(Math, 'random', () => 0.5)` replaces an existing method until you call `.mock.restore()`.

Before you replace global state, think about a cleaner option: {{< term "dependency-injection" "injection" >}}, which means passing the dependency in as a parameter. In the demo, `makeToken({ now, rand })` takes the time and the randomness as parameters with real defaults. A test passes `now: () => 42, rand: () => 0.1` and gets exactly `t42-100`, every time, with no flakiness and no mocking.

The runner can also fake time. `t.mock.timers` exists on 20.13.1, and it printed `ExperimentalWarning: The MockTimers API is an experimental feature`. With it, a `setTimeout(fn, 60_000)` fired right after `tick(60_000)`, with no real waiting. Mocks, fake timers and the like are called {{< term "test-double" "test doubles" >}}; use them sparingly, because a test full of doubles may pass while the real system is broken.

## An HTTP handler

For a plain `node:http` server ([post](/posts/node-http-server/)) the pattern is the same one as in that post. Inside `before` I start the server on port 0 (the operating system picks a free port), read the real port from `server.address()`, and call the server with the global `fetch` on loopback. `/health` gave 200 and `{ ok: true }`, and an unknown path gave 404. In `after` I call `server.close()` and `closeAllConnections()` so the process can exit; otherwise the open connections keep it alive and the run hangs. A Fastify app needs none of this: it has `inject()`, which sends a fake request without a socket (see the previous post).

## Coverage and snapshots

`--experimental-test-coverage` adds a table of how much of your code the tests ran. Mine (with the spec reporter, the `ℹ` prefix removed):

```text
file               | line % | branch % | funcs % | uncovered lines
app.js             | 100.00 |   100.00 |  100.00 |
price.js           | 100.00 |    88.89 |   60.00 |
test/app.test.js   | 100.00 |   100.00 |  100.00 |
test/price.test.js | 100.00 |   100.00 |   96.67 |
all files          | 100.00 |    98.08 |   93.18 |
```

It is experimental, and in this version it also lists the test files themselves. `price.js` has 60% of functions covered because I never call `notUsed()`, which I added to see exactly that. {{< term "code-coverage" "Coverage" >}} says what ran, not whether it was asserted well: a test that calls a function and checks nothing still counts.

Snapshot testing, where the runner stores an output and compares it next time, is not available here. On v20.13.1 `t.assert` is `undefined`, and `--test-update-snapshots` fails with `bad option`. I did not test newer Node versions.

## Where node:test surprises you

- **A top-level `before()` does not make top-level tests wait for it.** In a scratch file with `before(async () => {...})` and a top-level `test()` next to it, the hook did start (it printed `before ran`), but the test body ran before the hook's `await` had finished: `base` was `undefined` and fetch failed with `Failed to parse URL from undefined/health`. Wrapping the hook and the tests in a `describe` fixed it, which is what the demo does. I reproduced this in a scratch copy; it is not one of the demo files.
- **Discovery is by name and folder.** `failing.js` in the root was not picked up. Pass paths explicitly when in doubt.
- **A failing `todo` is not a failure.** Do not leave real tests there.
- **Close servers and timers in `after`.** Otherwise the run hangs.
- **Mocks hide integration bugs.** Mix them with a few tests against real parts.

## Exercise

Add a `GET /price?value=...&percent=...` route to `app.js` that calls `applyDiscount`, and test the 200 and a 400 for bad input, with a fetch against port 0.

## What's next

"Project structure and config in Node.js" is the next post. Testability comes down to structure, that is, to where dependencies and config are built and injected.
