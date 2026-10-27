+++
date = '2027-01-16T10:00:00+03:30'
draft = false
title = 'Testing in Node.js with node:test'
description = 'Testing in Node.js with node:test on v20.13.1: describe/it, hooks, mocks, mock timers, reporters, coverage, exit codes, and what is missing.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "testing", "node-test", "mocking", "coverage"]
cover = { image = "/images/covers/node-testing-builtin.png", alt = "Testing in Node.js with node:test", hiddenInSingle = true }
+++

In the previous post, [Building an API with Fastify](/posts/node-fastify-api/), we got an API running. Now I want to know it keeps working. Node ships a {{< term "test-runner" "test runner" >}} in the standard library, so no Jest or Mocha is needed to start. This is the Node counterpart of [Testing in Go](/posts/go-testing-basics/), and it uses [async/await](/posts/node-promises-async-await/) and the [HTTP server](/posts/node-http-server/) we built earlier.

> Node v20.13.1 (printed by `node --version`). The demo is a local example: `price.js`, `app.js` and two files in `test/`. All outputs are real. I do not publish timings: the machine was busy (load average above 10), so I removed durations from what you see.

## The basics

`test()` registers a test; `describe()`/`it()` group them. With `node:assert/strict` every comparison is strict. Table-driven tests are just a `for ... of` over cases (Go's idiom is a slice of structs and `t.Run`):

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

Async code works by returning a promise: `await assert.rejects(fetchUser(7, db), { message: 'not found' })`. Subtests use `await t.test(...)`; `{ skip: 'reason' }` skips and `{ todo: true }` marks work in progress. Hooks are `before`, `after`, `beforeEach`, `afterEach`; my hooks test recorded `before,beforeEach,afterEach,beforeEach,afterEach` for two tests, as expected.

## Running and reading results

`node --test` finds files by itself. On my run, `test/*.js` and `*.test.js` were picked up, and a file named `failing.js` in the root was not until I passed it explicitly. `--test-name-pattern=health` ran only the matching tests and marked the rest skipped. `--watch` reruns on change; I did not run it, since it is interactive. The spec reporter:

```text
▶ async
  ✔ resolves
  ✔ rejects
  ﹣ skipped one # no network here
  ✖ later # TODO
▶ async
✔ mock.fn and mock.method
ℹ tests 17
ℹ pass 15
ℹ fail 0
ℹ skipped 1
ℹ todo 1
```

The `todo` test fails its assertion but does not count as a failure. The dot reporter prints `...............X....`, one character per test, and the tap reporter prints TAP lines. When stdout is not a terminal, the default is tap. A real failing test shows a diff, and the process exits with code 1:

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

## Mocks and injection

`mock.fn()` records calls (`db.get.mock.callCount()`, `.calls[0].arguments`), and `mock.method(Math, 'random', () => 0.5)` replaces a method until `.mock.restore()`. Before mocking global state, prefer {{< term "dependency-injection" "injection" >}}: `makeToken({ now, rand })` takes time and randomness as parameters with real defaults, so the test passes `now: () => 42, rand: () => 0.1` and gets exactly `t42-100`, no flakiness.

`t.mock.timers` exists on 20.13.1, but it printed `ExperimentalWarning: The MockTimers API is an experimental feature`. With it, `setTimeout(fn, 60_000)` fired right after `tick(60_000)`, with no waiting. These are {{< term "test-double" "test doubles" >}}; use them sparingly.

## An HTTP handler

For a plain `node:http` server ([post](/posts/node-http-server/)) I listen on port 0 inside `before`, read the real port from `server.address()`, and call it with the global `fetch` on loopback. Passing `/health` gave 200 and `{ ok: true }`; an unknown path gave 404. In `after` I call `server.close()` and `closeAllConnections()` so the process can exit. A Fastify app needs none of this: it has `inject()`, which sends a fake request without a socket (see the previous post).

## Coverage and snapshots

`--experimental-test-coverage` prints a table. Mine:

```text
file                 | line % | branch % | funcs % | uncovered lines
app.js               | 100.00 |   100.00 |  100.00 |
price.js             | 100.00 |    88.89 |   60.00 |
test/price.test.js   | 100.00 |   100.00 |   96.67 |
```

It is experimental, and in this version it also lists the test files themselves. `price.js` has 60% of functions covered because I never call `notUsed()`. {{< term "code-coverage" "Coverage" >}} says what ran, not whether it was asserted well.

Snapshot testing: I checked, and on v20.13.1 `t.assert` is `undefined` and `--test-update-snapshots` fails with `bad option`. So it is not available here; I did not test newer versions.

## A few things to watch

- A top-level `before()` next to top-level `test()` calls did not run first in my run: `base` was `undefined` and fetch failed with `Failed to parse URL from undefined/health`. Wrapping in `describe` fixed it.
- Discovery is by name and folder; pass paths when in doubt.
- A `todo` that fails is not a failure; do not leave real tests there.
- Close servers and timers in `after`, or the run hangs.
- Mocks hide integration bugs; mix them with a few real runs.

## Exercise

Add a `GET /price?value=...&percent=...` route to `app.js` that calls `applyDiscount`, and test the 200 and a 400 for bad input, with a fetch against port 0.

## What's next

Next: Project structure and config in Node.js.
