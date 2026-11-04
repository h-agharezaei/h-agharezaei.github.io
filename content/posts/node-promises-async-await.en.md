+++
date = '2026-12-03T10:00:00+03:30'
draft = false
title = 'Promises and async/await in Node.js'
description = 'Promises and async/await in Node.js with real runs: chaining, return await, common mistakes, Promise.all, AbortController and a concurrency limiter.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "promises", "async-await", "javascript", "abortcontroller"]
cover = { image = "/images/covers/node-promises-async-await.png", alt = "Promises and async/await in Node.js", hiddenInSingle = true }
+++

Suppose a function has to load a user from a database. It cannot return the user right away, because the answer is on the other side of a network connection. In Node.js (remember the [event loop](/posts/node-event-loop/): there is only one thread, and it must never sit and wait) such a function gives you something else immediately: a **ticket**. It is like the numbered buzzer you get at a restaurant counter. The buzzer is not your food, but it stands for your food, and later it will either announce "ready" or "we ran out". That ticket is a {{< term "promise" "promise" >}}, and almost every Node.js API you will touch returns one.

This post is about using tickets correctly. A few small rules decide whether an error is handled or kills the whole process. For example, wrap `return fail()` in a `try/catch` inside an async function and the `catch` never runs; add one `await` and it does. We will see why. With dependencies sorted out in [npm, package.json and lockfiles](/posts/node-npm-package-json/), the series now turns to the code itself. If you come from Go, there is a short comparison near the end, and [goroutines and channels](/posts/go-goroutines-channels/) shows the other model.

> Everything was run with Node v20.13.1. The scripts are local examples; outputs are copied from real runs.

## States and chaining

A promise is in one of three states: **pending** (no answer yet), **fulfilled** (it has a value) or **rejected** (it has an error). It leaves pending exactly once and never changes again. You attach work to it with `.then(...)` for success and `.catch(...)` for failure. Three rules explain chaining:

- A `.then` that returns a plain value passes it to the next `.then`.
- A `.then` that returns a promise makes the chain wait for that promise.
- A `throw` skips ahead to the next `.catch`. And what `.catch` returns becomes a normal value again.

The script below creates a promise that is fulfilled after 50 ms, prints it right away, and prints it again after it settled. Then it runs one chain that uses all three rules:

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

Line by line:

- `right after creation`: the promise is still pending, because the timer has not fired.
- `chain value: 20`: 1 became 2, then the `.then` that returned a promise made the chain wait and produce 20. A plain value and a promise were both handled.
- `caught: boom`: the `throw` skipped the `skipped` step (it never printed) and landed in `.catch`.
- `after catch: recovered`: `.catch` returned a value, so the chain continued normally.
- `after settle`: the 50 ms timer finally fired, a long time after everything else, and now the promise holds `'done'`.

## async/await is syntax over the same promises

Chains get hard to read when the logic is long. {{< term "async-await" "async/await" >}} lets you write the same thing as if it were ordinary sequential code. An `async` function always returns a promise, and `await somePromise` waits for that promise and gives you its value (or throws its error). The key question is what `await` does to your program, since the thread must not block. This script shows it:

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

Here is what happens at the `await`:

1. `f()` is called like any function and runs on the call stack. It prints `f start`.
2. At `await null`, `f` is **paused**. Its place on the call stack is given up, and `f()` returns a pending promise to the caller. The rest of `f` is saved as a callback, a {{< term "microtask" "microtask" >}}, to be resumed as soon as the awaited value is ready.
3. The script carries on: `script end` is printed, and the call stack empties.
4. The queues are drained in the order we learned in the event loop post: `nextTick` first, then the microtasks in the order they were added. `f` queued its continuation before `then 1` was queued, so `f after await` comes first.
5. The timer is in a later phase, so `timeout` is last.

So `await` does not block anything. It cuts the function in two: the part before runs now, the part after runs later as a microtask. The thread stays free for everything else in between.

## return versus return await

Now the puzzle from the beginning. Both functions below call `fail()`, which always rejects, and both wrap it in `try/catch`:

```js
async function fail() { throw new Error('inner failure'); }
async function withoutAwait() {
  try { return fail(); } catch (e) { return 'caught inside (no await)'; }
}
async function withAwait() {
  try { return await fail(); } catch (e) { return 'caught inside (with await)'; }
}
```

The demo calls both and prints how each promise ended:

```text
is promise: true
withAwait -> caught inside (with await)
withoutAwait rejected -> inner failure
```

Without `await`, `return fail()` hands the rejected promise out of the function without looking at it. The function has already finished by the time the promise rejects, so the `catch` is no longer there to see it, and the caller gets the rejection. With `await`, the function waits inside the `try`, the rejection becomes a thrown error right there, and the `catch` handles it.

## Classic mistakes

Three mistakes show up again and again. This is the demo that reproduces them (`sleep` and `getUser` are small helpers in the file):

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

- **A forgotten `await`.** You get the ticket instead of the user: a pending promise, and `undefined` for any property you read from it.
- **`forEach` with an async callback.** `forEach` ignores the promises that its callback returns, so it finishes at once and nothing waits. `seen` is empty right after the loop and only fills up later. Use `for...of` with `await`, or `Promise.all(items.map(...))`.
- **Waiting one by one when you could wait together.** Three tasks of 100 ms each, first in a loop of awaits and then with `Promise.all`:

```text
sequential ~ 300 ms, Promise.all ~ 100 ms (measured here)
```

The loop runs the tasks one after another (3 x 100 ms). `Promise.all` starts all three together and waits for the slowest. The numbers are rounded to 100 ms. The original run was made with a load average under 2.5, and my re-run for this version printed the same line.

## all, allSettled, race, any

When you have several promises, there are four ways to combine them. This script tries each with a few timers that succeed or fail after a short delay:

```js
// inside an async function
console.log('all:', await Promise.all([later(10, 'a'), later(20, 'b')]));
// ... a rejecting input for all; then allSettled, race, any ...
```

```text
all: [ 'a', 'b' ]
all rejected: bad
allSettled: [ { status: 'fulfilled', value: 'a' }, { status: 'rejected', reason: Error: bad ... } ]
race: fast
any: winner
AggregateError All promises were rejected [ 'x', 'y' ]
```

(I shortened the printed stack of the `allSettled` reason. The full script is in the demo folder.) In plain words:

- `Promise.all` waits for all and gives an array of values. It **fails fast**: the first rejection rejects the whole thing (`all rejected: bad`).
- `Promise.allSettled` never rejects. It waits for all and reports a status for each one, so you see the successes and the failures together.
- `Promise.race` takes whichever promise settles first, success or failure (`fast`).
- `Promise.any` takes the first one that *fulfills*. It rejects only if all of them fail, with an {{< term "aggregate-error" "AggregateError" >}} that collects all the reasons.

## An unhandled rejection

What if a rejected promise has nobody to handle it? This two-line script finds out:

```js
Promise.reject(new Error('nobody handles me'));
setTimeout(() => console.log('never printed'), 100);
```

On Node 20 this prints the error with its stack and then `Node.js v20.13.1` (I left out the stack lines that show paths), the exit code is 1, and the timer never fires. An {{< term "unhandled-rejection" "unhandled rejection" >}} kills the process. This is also why a forgotten `.catch` is dangerous: it is not a silent bug, it is a crash. The next post covers errors in depth.

## Cancellation and timeouts

A promise cannot be cancelled by itself, so Node uses a separate object for it: an {{< term "abort-controller" "AbortController" >}}. You hand its `signal` to the operation, and calling `abort()` makes the operation stop with an `AbortError`. `AbortSignal.timeout(ms)` gives a signal that aborts by itself after a deadline. The first script below sleeps for 1000 ms but cancels after 50 ms, then does the same with a timeout signal. Because `await` is used, the demo wraps the code in an async function:

```js
const { setTimeout: sleep } = require('node:timers/promises');
(async () => {
  const ac = new AbortController();
  setTimeout(() => ac.abort(), 50);
  try { await sleep(1000, 'x', { signal: ac.signal }); }
  catch (e) { console.log('manual abort:', e.name, e.code); }
  try { await sleep(1000, 'x', { signal: AbortSignal.timeout(50) }); }
  catch (e) { console.log('timeout signal:', e.name, e.code); }
})();
```

```text
manual abort: AbortError ABORT_ERR
timeout signal: AbortError ABORT_ERR
```

Both sleeps ended after about 50 ms instead of 1000, with an `AbortError`. Pass the signal to every API that accepts one (`fetch` does, for example).

## Callback APIs and a concurrency limit

Older Node APIs take a callback `(err, result)` instead of returning a promise. `util.promisify` wraps such a function so that it returns a promise. This demo wraps a fake function and `fs.stat`:

```js
const double = promisify(legacyDouble);
const stat = promisify(fs.stat);
```

```text
double(21) = 42
rejected: negative
isFile: true
```

Another limit you will hit: an unbounded `Promise.all` over thousands of items starts thousands of operations at once, and can overwhelm a database. The fix is a limiter: N workers that pull the next item from a shared index until none are left.

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

The demo runs ten tasks of 100 ms with a limit of 3, and counts how many were running at the same moment:

```text
results: 0,1,4,9,16,25,36,49,64,81
max in flight: 3
elapsed ~ 400 ms (measured here)
```

`max in flight: 3` is the proof that the limit holds. Ten tasks in groups of three need four rounds of 100 ms, which matches the 400 ms. This is safe without any lock because JavaScript runs on one thread, so `next++` cannot be interrupted halfway by another worker. (The elapsed line is rounded to 100 ms and was the same in my re-run.)

## Compared with Go

A promise is a value that stands for a future result. A goroutine is a function scheduled to run concurrently, and results travel through channels. Promises give you no parallelism for your JavaScript code; they organize waiting.

## Promises that get lost

- **A promise nobody handles.** Every promise must be awaited, returned or given a `.catch`; otherwise a rejection can crash the process.
- **`return` instead of `return await` inside `try/catch`.** Use `return await` when you want the error handled in the same function.
- **`await` inside `forEach`.** It does not wait. Use `for...of` or `Promise.all`.
- **Unbounded concurrency.** Limit it for external resources like databases, and pass an `AbortSignal` so slow calls can time out.

## Exercise

Change `mapLimit` so that when one task throws, no new tasks start. Prove it with a counter of started tasks.

## What's next

"Errors and unhandled rejections in Node.js": we saw an unhandled rejection kill the process, so the next step is deciding where errors should be caught and where they should not.
