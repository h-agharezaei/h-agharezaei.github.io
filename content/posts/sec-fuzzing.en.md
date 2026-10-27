+++
date = '2027-05-27T10:00:00+03:30'
draft = false
title = 'Fuzzing to find security bugs'
description = 'Fuzzing in Go: find three deliberate parser bugs (bounds, int32 overflow, hang) with go test -fuzz, replay the saved inputs and fix them.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "fuzzing", "go", "testing", "parser"]
cover = { image = "/images/covers/sec-fuzzing.png", alt = "Fuzzing to find security bugs", hiddenInSingle = true }
+++

The previous post, [Memory safety: C versus Rust](/posts/sec-memory-safety-c-vs-rust/), showed what a bad index can do. Today I let a machine look for such bad inputs. A parser reads bytes that someone else controls, so it is where a missing check becomes a {{< term "denial-of-service" "denial of service" >}} or worse. {{< term "fuzzing" "Fuzzing" >}} feeds it mutated inputs until something breaks. It complements [Property-based testing](/posts/eng-property-based-testing/).

> Defensive only. I fuzzed my own 60-line parser, in my own test, with Go 1.26. Nothing third-party was touched. The three bugs are deliberate. The demo is a local example.

## The parser

Format: `TLV1`, then records of type (1 byte), length (2 bytes), value. Type 1 is bytes, type 2 is "repeat" (a count, a size, a fill byte), type 3 is text with backslash escapes. The fuzz target is tiny:

```go
func FuzzParse(f *testing.F) {
	f.Add([]byte("TLV1\x01\x00\x03abc"))
	f.Add([]byte("TLV1\x02\x00\x06\x00\x00\x00\x03\x02x"))
	f.Add([]byte("TLV1\x03\x00\x04a\\nb"))
	f.Fuzz(func(t *testing.T, b []byte) { Parse(b) })
}
```

The `f.Add` calls are the {{< term "seed-corpus" "seed corpus" >}}. Real samples make the best seeds. The fuzzer is {{< term "coverage-guided-fuzzing" "coverage-guided" >}}: an input that reaches new code is kept and mutated further. That is what the `new interesting` counter shows.

## Bug 1: the length is trusted

```
$ go test -fuzz=FuzzParse -fuzztime=200000x
fuzz: elapsed: 0s, execs: 251 (2132/sec), new interesting: 1 (total: 4)
--- FAIL: FuzzParse (0.12s)
  panic: runtime error: slice bounds out of range [:12343] with capacity 16
  Failing input written to testdata/fuzz/FuzzParse/a3c431880a157b71
```

It took about 250 executions. The file holds the minimized input, `[]byte("TLV1\x0200")`: the length bytes are the characters `00`, which is 12336, far past the end. Plain `go test` now replays this file and fails, until the fix:

```go
if n > len(b)-pos-3 { return nil, ErrFormat }
```

A saved input stays in `testdata/fuzz` as a permanent {{< term "regression" "regression" >}} test; commit it.

## Bug 2: int32 arithmetic

Next run, same command:

```
--- FAIL: FuzzParse (0.12s)
  panic: runtime error: makeslice: len out of range
  Failing input written to testdata/fuzz/FuzzParse/1461c70ced3bd442
[]byte("TLV1\x02\x00\x06A00020")
```

Here count is `0x41303030` and size is `'2'` (50). My code did `int32(count) * int32(size)`, which wraps to a negative number, passes the `> maxTotal` check, and crashes `make`. This is {{< term "integer-overflow" "integer overflow" >}} in the length arithmetic. If it had wrapped to a small positive number, the buffer would just be too short. If the check had been missing, a 4-byte field could ask for gigabytes. The fix is to compute in `uint64` and compare against a cap first:

```go
total := uint64(count) * uint64(val[4])
if total > maxTotal { return nil, ErrFormat }
```

## Bug 3: the hang

```
fuzz: elapsed: 12s, execs: 154326 (0/sec), new interesting: 15 (total: 25)
--- FAIL: FuzzParse (12.09s)
  fuzzing process hung or terminated unexpectedly: exit status 2
```

The exec counter stalled at about 154300 and Go killed the worker after about ten seconds. A trailing backslash made `unescape` loop forever, because the index did not advance. The saved input was not minimized, since minimizing a hang is slow. Plain `go test` would hang too, so use `-timeout 5s` while reproducing: it printed `panic: test timed out after 5s`. Fix: always `i += 2`.

## After the fixes

```
$ go test -v          # three regression files plus seeds
--- PASS: FuzzParse/1461c70ced3bd442
--- PASS: FuzzParse/a3c431880a157b71
--- PASS: FuzzParse/da26de22b41b4c2d
$ go test -fuzz=FuzzParse -fuzztime=2000000x
fuzz: elapsed: 13s, execs: 2000000 (55021/sec), new interesting: 9 (total: 36)
ok
```

Two million executions, no crash. That is **not** proof that the parser is correct; it only means this search did not find one. I report counts, not timings, because my machine was busy.

## Properties and differences

A fuzzer needs an oracle. A panic is a free one. A better one is a property. `FuzzRoundTrip` checks that `Parse(Encode(x))` returns `x` for type 3 records. It passed 500000 executions here, so I found no logic bug. I did not run {{< term "differential-testing" "differential fuzzing" >}} (compare your parser with another implementation, for example a JSON subset against `encoding/json`), but the shape is the same.

## In real projects

- CI: a short budget on pull requests (`-fuzztime=30s`), a long one nightly; see [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/).
- C and C++: libFuzzer, AFL++, and OSS-Fuzz run them at scale; Rust has `cargo-fuzz`. I only name them; I did not run them.
- Pair the fuzzer with a sanitizer such as {{< term "addresssanitizer" "AddressSanitizer" >}} for C. Go and Rust give you {{< term "memory-safety" "memory safety" >}} but still panic and hang.
- Dictionaries of keywords and structure-aware fuzzing help with formats that have checksums or grammars.

## A few things to watch

- Commit the files under `testdata/fuzz`.
- Seeds from real samples beat empty seeds.
- Fuzz your parsers, never other people's services.
- Cap every allocation that depends on input.
- Silence is not proof.

## Exercise

Add a type 4 record whose 4-byte length is used directly in `make([]byte, n)`. Let the fuzzer find the problem, then add a cap and a regression test.

## What's next

The next post is Logging, auditing and incident response.
