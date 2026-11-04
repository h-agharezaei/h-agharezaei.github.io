+++
date = '2026-12-17T10:00:00+03:30'
draft = false
title = 'Streams and backpressure in Node.js'
description = 'Node.js streams and backpressure with real runs: memory of readFileSync vs a stream, pipeline with gzip, write() returning false, drain and error handling.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "streams", "backpressure", "pipeline", "javascript"]
cover = { image = "/images/covers/node-streams-backpressure.png", alt = "Streams and backpressure in Node.js", hiddenInSingle = true }
+++

Suppose you have a log file of 2 GB and you need to compress it, or count the lines that contain a word. The obvious way is to read the whole file into a variable and then work on it. On a laptop that might work. On a small server it will run out of memory, and even when it works, you wait until the whole file is loaded before the first byte is processed.

The better way is to treat the file like water in a pipe. You do not need the whole lake in your bucket; you only need the water that is passing by right now. Read a small piece, process it, pass it on, and forget it. In Node.js this pipe is called a {{< term "stream" "stream" >}}, and the small pieces are called **chunks**.

Streams bring a second problem. What happens when the part that reads is faster than the part that writes, for example when you read from a fast disk and send to a slow network? The pieces pile up in memory and you are back to the same problem. The rule that prevents this is called {{< term "backpressure" "backpressure" >}}: the slow end tells the fast end "wait, I am full". Most of this post is about seeing that rule work with real numbers.

This builds on [the event loop](/posts/node-event-loop/) and on [promises and async/await](/posts/node-promises-async-await/), and the failure side of streams connects to [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/). If you come from Go, [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/) is the counterpart.

> Everything was run with Node v20.13.1 on one machine. The scripts are local examples; outputs are copied from real runs. Memory numbers differ a little on every run, so read them as approximate.

## Four kinds of stream

Every stream in Node is one of four kinds. The names say which side of the pipe you are on:

- **Readable**: a source you take chunks from (reading a file, an HTTP request body).
- **Writable**: a destination you give chunks to (a file, a network socket).
- **Duplex**: both directions at once, and the two directions are independent (a TCP socket).
- **Transform**: a Duplex whose output is computed from its input (gzip compression, a function that uppercases text).

A pipeline is usually a Readable, zero or more Transforms, and a Writable, connected one after another.

## Memory: reading everything vs reading in chunks

First I want to see the difference instead of just claiming it. I generated a text file of 52,428,805 bytes (about 50 MB, one line repeated many times). Then I counted its bytes in two ways and printed the process's memory (`rss`, the memory the operating system has given the process) before and at its peak.

The first way is `fs.readFileSync`, which loads the whole file into one buffer. The second way reads it as a stream and adds up the chunk sizes as they arrive:

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

Both counted the same number of bytes. The process started at 35 MB. With `readFileSync` it grew by about 50 MB, the size of the file, which is what we expected. With the stream it grew by about 27 MB, roughly half. (Re-running the demo now gave a stream peak of 63 and 64 MB; the numbers move a little each time.)

Why did the stream still grow by that much, if it only holds one chunk at a time? Part of it is the chunks in flight, and part of it is garbage that has not been collected yet; `rss` cannot tell them apart. I did not measure how the gap grows with the file size, so do not read these numbers as a law. What you can rely on is the idea: a stream's memory is tied to the size of a chunk, not to the size of the file.

A small note on the code: `for await` works on a Readable because streams are async iterables, so you read chunks with a plain loop and no event listeners.

## pipeline: connecting the pieces

Now let us build a real chain: read the file, uppercase it, compress it with gzip, and write the result. `pipeline` from `node:stream/promises` connects the streams and waits for the end. It also cleans up if anything fails, which we will see two sections later.

The uppercaser is a Transform. It receives a chunk, and calls the callback with the transformed chunk:

```js
const upper = new Transform({
  transform(chunk, enc, cb) { cb(null, chunk.toString().toUpperCase()); },
});
await pipeline(createReadStream('big.txt'), upper, zlib.createGzip(), createWriteStream('big.txt.gz'));
```

```text
original: 52428805 gzip: 152664
```

The 50 MB file became 152,664 bytes. That is only because my file is one line repeated, which compresses extremely well; a real log would not shrink this much. The point is that the whole 50 MB never sat in memory at once.

Streams do not have to come from files. `Readable.from(asyncGenerator)` turns an async generator into a stream. Such a stream is in {{< term "object-mode" "object mode" >}} by default: normally chunks are bytes or strings, but in object mode every chunk can be a JavaScript object. The demo yields five objects and prints each one:

```js
async function* nums() { for (let i = 1; i <= 5; i++) yield { id: i, sq: i * i }; }
for await (const o of Readable.from(nums())) console.log(o);
```

```text
{ id: 1, sq: 1 }
{ id: 2, sq: 4 }
{ id: 3, sq: 9 }
{ id: 4, sq: 16 }
{ id: 5, sq: 25 }
```

## Backpressure: the writer says "wait"

Now the problem I mentioned at the start. Think of a Writable stream as a sink with a small waiting room. If it can process a chunk right now, it does. If not, the chunk waits in an internal buffer. The buffer has a size limit called the {{< term "high-water-mark" "highWaterMark" >}}, 16 KiB (16384 bytes) by default for a normal Writable.

When you call `writable.write(chunk)`, it returns `true` or `false`:

- `true` means "go ahead, there is room".
- `false` means "the buffer is at or above the limit, please stop". The data you just wrote is still accepted, but you should wait for the `'drain'` event, which says the buffer has emptied, before writing more.

That signal is backpressure. It is a polite request, not a wall: if you ignore it, nothing stops you, and the buffer simply grows.

To see this, I wrote a deliberately slow Writable that finishes one chunk per turn of the event loop, and wrote 100 chunks of 1 KiB into it. I did it twice. The first time I ignored the return value of `write()`. The second time I waited for `'drain'` whenever it returned `false`. I also tracked the largest buffer size (`writableLength`):

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

Line by line:

- `highWaterMark: 16384` is the default limit, 16 KiB.
- In the **ignoring** run, `write()` returned `false` 85 times. The first 15 writes fit under the limit, the 16th reached it, and every write from then on was told to stop. I kept writing anyway, so the buffer held all 100 chunks at once: 102,400 bytes, more than six times the limit. `drains: 0` because I never gave the stream a chance to empty.
- In the **respecting** run, the buffer filled to 16,384 bytes six times (6 `false` results), and each time I waited for `'drain'` (6 drains). The buffer never held more than the limit.

These counts are deterministic, so I trust them more than any timing. With 100 KiB the difference is small, but imagine the producer being a 2 GB file: ignoring the signal means the whole file ends up in memory, and the stream bought you nothing.

The good news is that you rarely write this waiting code yourself. `pipeline` (and `.pipe()`) call `write()`, watch its result and wait for `'drain'` for you. That is the main reason to prefer them.

## When something fails: pipeline vs .pipe()

A chain of streams has many places to fail: the disk, the transform, the network. What happens to the other streams when one of them fails? I tested this with a Transform that throws an error on its second chunk, once through `pipeline` and once through the older `.pipe()`. The demo prints a line each time one of the three streams closes.

With `pipeline`:

```text
pipeline transform closed, destroyed = true
pipeline writable closed, destroyed = true
pipeline rejected: bad chunk
pipeline readable closed, destroyed = true
```

All three streams were destroyed (closed, with their resources released), and the promise rejected with the error. So a plain `try/catch` around `await pipeline(...)` handles the whole chain. (The order of the lines is what the run printed; do not rely on the order.)

With `readable.pipe(transform).pipe(writable)` and an error listener on the transform:

```text
transform error event: bad chunk
pipe transform closed, destroyed = true
readable destroyed: false writable destroyed: false writable ended: false
```

Only the stream that failed was closed. The source (the readable) and the destination (the writable) were left open, and the writable never finishes. In a real program that means an open file or socket that is never released: a leak. `.pipe()` does not pass errors along the chain, so you would have to attach an error handler to every stream and close the others yourself. `pipeline` does exactly that for you.

## Where buffers grow silently

- **Using `.pipe()` where `pipeline` would do.** It leaks the other streams on error. Prefer `pipeline`, and always handle its rejection.
- **Calling `write()` yourself and ignoring the result.** Check the return value and wait for `'drain'` when it is `false`, as in the second run above.
- **Treating `highWaterMark` as a hard limit.** It is a threshold: the buffer can grow past it if you keep writing, as the 102,400 bytes showed.
- **Using `readFileSync` on files whose size you do not control.** A file that is 50 MB today may be 5 GB next year.
- **Expecting Go behaviour.** In Go, `io.Copy` between a Reader and a Writer gets this for free, because `Write` blocks the goroutine until the data is accepted. In Node everything is non-blocking, so the writer has to say "wait" explicitly, through `write()` and `'drain'`.

## Exercise

Write a script that reads `big.txt` line by line, keeps only the lines that contain `fox`, and writes them to a new file with `pipeline`. Then change the Transform so that it throws on the 1000th chunk, and confirm that the promise rejects and the output stream is destroyed.

## What's next

"An HTTP server with node:http" is the next post. In it the request and the response are themselves streams, so everything above applies directly.
