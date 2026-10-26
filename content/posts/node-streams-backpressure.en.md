+++
date = '2026-12-17T10:00:00+03:30'
draft = false
title = 'Streams and backpressure in Node.js'
description = 'Node.js streams and backpressure with real runs: memory of readFileSync vs a stream, pipeline with gzip, write() returning false, drain and error handling.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "streams", "backpressure", "pipeline", "javascript"]
cover = { image = "/images/covers/node-streams-backpressure.png", alt = "Streams and backpressure in Node.js", hiddenInSingle = true }
+++

In the previous post, [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/), we made failures visible. Now a different kind of problem: data that is bigger than you want to hold in memory. The answer is the {{< term "stream" "stream" >}}. It builds on [the event loop](/posts/node-event-loop/) and on [promises and async/await](/posts/node-promises-async-await/). If you come from Go, [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/) is the counterpart.

> Everything was run with Node v20.13.1 on one machine. The scripts are local examples; outputs are copied from real runs.

## Four kinds of stream

- **Readable**: a source you take chunks from (a file read, an HTTP request body).
- **Writable**: a destination you give chunks to (a file, a socket).
- **Duplex**: both directions, independent (a TCP socket).
- **Transform**: a Duplex whose output is computed from its input (gzip, an uppercaser).

## Memory: readFileSync vs a stream

I generated a 52,428,805-byte text file and counted its bytes two ways, printing `process.memoryUsage().rss`:

```js
// sync mode: const buf = fs.readFileSync('big.txt'); bytes = buf.length;
// stream mode:
for await (const chunk of fs.createReadStream('big.txt')) {
  bytes += chunk.length;
  peak = Math.max(peak, process.memoryUsage().rss);
}
```

```text
sync bytes: 52428805 rss before MB: 35 peak rss MB: 85
stream bytes: 52428805 rss before MB: 35 peak rss MB: 62
```

`for await` over a Readable works because streams are async iterables. The growth was about 50 MB for `readFileSync` and about 27 MB for the stream, roughly half. Treat this as approximate: RSS includes garbage not yet collected, and the numbers depend on the machine. The stream holds only a few chunks at a time, but I did not measure how the gap scales with file size.

## pipeline

`pipeline` from `node:stream/promises` connects streams and cleans up for you:

```js
const upper = new Transform({
  transform(chunk, enc, cb) { cb(null, chunk.toString().toUpperCase()); },
});
await pipeline(createReadStream('big.txt'), upper, zlib.createGzip(), createWriteStream('big.txt.gz'));
```

```text
original: 52428805 gzip: 152664
```

(The input is one repeated line, so it compresses extremely well.) `Readable.from(asyncGenerator)` turns a generator into a stream, and it is in {{< term "object-mode" "object mode" >}} by default, so chunks can be objects:

```js
async function* nums() { for (let i = 1; i <= 5; i++) yield { id: i, sq: i * i }; }
for await (const o of Readable.from(nums())) console.log(o);
```

```text
{ id: 1, sq: 1 }
{ id: 2, sq: 4 }
...
{ id: 5, sq: 25 }
```

## Backpressure

A Writable buffers what it cannot process yet. {{< term "backpressure" "Backpressure" >}} is the rule that when the buffer is full, `write()` returns `false` and the producer waits for `'drain'`. The threshold is the {{< term "high-water-mark" "highWaterMark" >}}. I wrote 100 chunks of 1 KiB into a deliberately slow Writable (one chunk per event loop turn), once ignoring the return value and once awaiting `'drain'`:

```js
const ok = slow.write(chunk);
maxBuffered = Math.max(maxBuffered, slow.writableLength);
if (!ok) {
  falseCount++;
  if (respect) await new Promise((r) => slow.once('drain', r));
}
```

```text
highWaterMark: 16384
ignoring { written: 100, falseCount: 85, drains: 0, maxBufferedBytes: 102400 }
respecting { written: 100, falseCount: 6, drains: 6, maxBufferedBytes: 16384 }
```

Ignoring the signal buffered all 100 KiB. Respecting it never held more than 16 KiB. The counts are deterministic; I report no timings. With `pipeline` or `.pipe()` this is handled for you, which is the main reason to use them.

## Errors: pipeline vs .pipe()

I made the Transform fail on its second chunk. With `pipeline`:

```text
pipeline transform closed, destroyed = true
pipeline writable closed, destroyed = true
pipeline rejected: bad chunk
pipeline readable closed, destroyed = true
```

Every stream was destroyed and the promise rejected, so `try/catch` works. With `readable.pipe(transform).pipe(writable)`:

```text
transform error event: bad chunk
pipe transform closed, destroyed = true
readable destroyed: false writable destroyed: false writable ended: false
```

Only the failing stream closed. The source and the destination were left open: a leak, and the writable never ends. `.pipe()` does not forward errors.

## A few things to watch

- Prefer `pipeline` over `.pipe()`; always handle its rejection.
- When you call `write()` yourself, check the return value and wait for `'drain'`.
- `highWaterMark` is a threshold, not a limit: the buffer can exceed it if you keep writing.
- Do not use `readFileSync` on files whose size you do not control.
- In Go, `io.Copy` between a Reader and a Writer gets this for free because `Write` blocks; Node has to signal it explicitly because everything is non-blocking.

## Exercise

Write a script that reads `big.txt` line by line, keeps only lines containing `fox`, and writes them to a new file with `pipeline`. Then make the Transform throw on the 1000th chunk and confirm the promise rejects and the output stream is destroyed.

## What's next

The next post is An HTTP server with node:http, where requests and responses are themselves streams.
