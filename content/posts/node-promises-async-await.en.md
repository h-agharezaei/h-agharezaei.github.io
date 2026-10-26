+++
date = '2026-12-03T10:00:00+03:30'
draft = false
title = 'Promises and async/await in Node.js'
description = 'Promises and async/await in Node.js with real runs: chaining, return await, common mistakes, Promise.all, AbortController and a concurrency limiter.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "promises", "async-await", "javascript", "abortcontroller"]
cover = { image = "/images/covers/node-promises-async-await.png", alt = "Promises and async/await in Node.js", hiddenInSingle = true }
+++

In the previous post, [npm, package.json and lockfiles](/posts/node-npm-package-json/), we managed dependencies. Now we write the code itself, and almost every Node.js API you will touch returns a {{< term "promise" "promise" >}}. It builds directly on [the event loop](/posts/node-event-loop/): a promise callback is a microtask. If you come from Go, see the short comparison near the end, and [goroutines and channels](/posts/go-goroutines-channels/) for the other model.

> Everything was run with Node v20.13.1. The scripts are local examples; outputs are copied from real runs.

## States and chaining

A promise is pending, then fulfilled or rejected, once. A `.then` that returns a plain value passes it on; one that returns a promise waits for it; a throw skips to the next `.catch`:

```js
const p = new Promise((res) => setTimeout(() => res('done'), 50));
console.log('right after creation:', p);
p.then(() => console.log('after settle:', p));

Promise.resolve(1)
  .then((v) => v + 1)
  .then((v) => Promise.resolve(v * 10))
  .then((v) => { console.log('chain value:', v); throw new Error('boom'); })
  .then(() => console.log('skipped'))
  .catch((e) => { console.log('caught:', e.message); return 'recovered'; })
  .then((v) => console.log('after catch:', v));
```

```text
right after creation: Promise { <pending> }
chain value: 20
caught: boom
after catch: recovered
after settle: Promise { 'done' }
```

## async/await is sugar, with microtask rules

{{< term "async-await" "async/await" >}} is syntax over the same promises. An `async` function always returns a promise, and code after `await` runs as a {{< term "microtask" "microtask" >}}:

```js
async function f() {
  console.log('f start');
  await null;
  console.log('f after await');
}
console.log('script start');
f();
Promise.resolve().then(() => console.log('then 1'));
process.nextTick(() => console.log('nextTick'));
setTimeout(() => console.log('timeout'), 0);
console.log('script end');
```

```text
script start
f start
script end
nextTick
f after await
then 1
timeout
```

The function runs synchronously until the first `await`; the rest is queued behind `nextTick` and before the timer, exactly as in the event loop post.

## return vs return await

Inside `try/catch` the difference matters:

```js
async function fail() { throw new Error('inner failure'); }
async function withoutAwait() {
  try { return fail(); } catch (e) { return 'caught inside (no await)'; }
}
async function withAwait() {
  try { return await fail(); } catch (e) { return 'caught inside (with await)'; }
}
```

```text
withAwait -> caught inside (with await)
withoutAwait rejected -> inner failure
```

Without `await` the rejected promise leaves the function and the `catch` never sees it.

## Classic mistakes

```js
const forgotten = getUser();           // no await
console.log('forgotten await:', forgotten, forgotten.name);
[1, 2, 3].forEach(async (n) => { await sleep(10); seen.push(n); });
console.log('right after forEach, seen =', seen);
```

```text
forgotten await: Promise { <pending> } undefined
right after forEach, seen = []
later, seen = [ 1, 2, 3 ]
```

A forgotten `await` gives you a pending promise and `undefined` properties. `forEach` ignores the promises its callback returns, so nothing waits. Use `for...of` with `await`, or `Promise.all(items.map(...))`. Three 100 ms tasks, in a loop of awaits versus `Promise.all` (load average was under 2.5):

```text
sequential ~ 300 ms, Promise.all ~ 100 ms (measured here)
```

## all, allSettled, race, any

```text
all: [ 'a', 'b' ]
all rejected: bad
allSettled: [ { status: 'fulfilled', value: 'a' }, { status: 'rejected', reason: Error: bad ... } ]
race: fast
any: winner
AggregateError All promises were rejected [ 'x', 'y' ]
```

(I shortened the printed stack of the `allSettled` reason.) `all` fails fast on the first rejection, `allSettled` always reports every result, `race` takes the first to settle, and `any` takes the first to fulfill and throws an `AggregateError` only if all fail.

## An unhandled rejection

```js
Promise.reject(new Error('nobody handles me'));
setTimeout(() => console.log('never printed'), 100);
```

On Node 20 this prints the error with its stack, then `Node.js v20.13.1`, and the exit code is 1; the timer never fires. An {{< term "unhandled-rejection" "unhandled rejection" >}} kills the process. The next post covers errors in depth.

## Cancellation and timeouts

```js
const { setTimeout: sleep } = require('node:timers/promises');
const ac = new AbortController();
setTimeout(() => ac.abort(), 50);
try { await sleep(1000, 'x', { signal: ac.signal }); }
catch (e) { console.log('manual abort:', e.name, e.code); }
try { await sleep(1000, 'x', { signal: AbortSignal.timeout(50) }); }
catch (e) { console.log('timeout signal:', e.name, e.code); }
```

```text
manual abort: AbortError ABORT_ERR
timeout signal: AbortError ABORT_ERR
```

An {{< term "abort-controller" "AbortController" >}} signal is the standard way to cancel; `AbortSignal.timeout(ms)` gives a deadline. Both ended the sleep early with `AbortError`. Pass the signal to every API that accepts one.

## Callback APIs and a concurrency limit

`util.promisify` wraps a Node-style `(err, result)` callback function:

```text
double(21) = 42
rejected: negative
isFile: true
```

Unbounded `Promise.all` over thousands of items can overwhelm a database. A hand-written limiter, with N workers pulling from a shared index:

```js
async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
```

Ten tasks of 100 ms, limit 3, counting how many were in flight:

```text
results: 0,1,4,9,16,25,36,49,64,81
max in flight: 3
elapsed ~ 400 ms (measured here)
```

The max of 3 is the proof; 4 rounds of 100 ms matches ten tasks in groups of three. This is safe without locks because JavaScript runs one thread (`next++` cannot interleave).

## Compared with Go

A promise is a value standing for a future result. A goroutine is a function scheduled to run concurrently, and results travel over channels. Promises give you no parallelism for JavaScript code; they organize waiting.

## A few things to watch

- Every promise must be awaited, returned or given a `.catch`.
- Use `return await` inside `try/catch` when you want to handle the error there.
- Never `await` inside `forEach`; use `for...of` or `Promise.all`.
- Bound concurrency for external resources, and pass an `AbortSignal` for timeouts.

## Exercise

Change `mapLimit` so that when one task throws, no new tasks start. Prove it with a counter of started tasks.

## What's next

The next post is "Errors and unhandled rejections in Node.js".
