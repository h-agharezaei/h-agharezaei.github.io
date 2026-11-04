+++
date = '2027-05-27T10:00:00+03:30'
draft = false
title = 'Fuzzing to find security bugs'
description = 'Fuzzing in Go: find three deliberate parser bugs (bounds, int32 overflow, hang) with go test -fuzz, replay the saved inputs and fix them.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "fuzzing", "go", "testing", "parser"]
cover = { image = "/images/covers/sec-fuzzing.png", alt = "Fuzzing to find security bugs", hiddenInSingle = true }
+++

Suppose you write a small parser for a binary format. It reads a header, then a sequence of records, each with a type, a length and a value. You test it with a few good files and a few obviously broken ones, and everything passes. Then you let a program feed it random mutations of those files. After about 250 attempts, the parser crashes with `slice bounds out of range`. The reason is simple: it trusted the length field in the file.

That program is a fuzzer, and this post is about how it works, how small the harness is, and what to do with the crash it finds. [Memory safety: C versus Rust](/posts/sec-memory-safety-c-vs-rust/) showed what a bad index can do. Here a machine looks for the inputs that cause one.

A parser is the right target, because it reads bytes that somebody else controls. A missing check there can become a {{< term "denial-of-service" "denial of service" >}} (the service crashes or hangs) or something worse. {{< term "fuzzing" "Fuzzing" >}} means feeding a program a large number of generated, mutated inputs until something breaks. It complements [Property-based testing](/posts/eng-property-based-testing/): that checks a rule you state, fuzzing starts by checking only "does it crash".

> Defensive only. I fuzzed my own 60-line parser, in my own test, on my own machine. Nothing third-party was touched. The three bugs are deliberate. The demo is a local example. The original run used Go 1.26; I re-ran it for this rewrite with Go 1.27.3. The demo directory holds the final, fixed parser, so to show the bugs again I rebuilt each buggy version in a scratch copy (the same three mistakes, one at a time) and fuzzed those. The fuzzer is random, so counts and times differ from run to run, and I say where.

## The parser

The format is called `TLV1` (type, length, value). It starts with the four bytes `TLV1`, then has any number of records. Each record is a type (1 byte), a length (2 bytes, big endian) and then that many bytes of value:

- type 1 is plain bytes;
- type 2 is "repeat": a 4-byte count, a 1-byte size and a fill byte, meaning "produce count times size bytes of the fill byte";
- type 3 is text with backslash escapes, such as `\n`.

The fuzz target is tiny. It is an ordinary Go test function that takes a `*testing.F`:

```go
func FuzzParse(f *testing.F) {
	f.Add([]byte("TLV1\x01\x00\x03abc"))
	f.Add([]byte("TLV1\x02\x00\x06\x00\x00\x00\x03\x02x"))
	f.Add([]byte("TLV1\x03\x00\x04a\\nb"))
	f.Fuzz(func(t *testing.T, b []byte) { Parse(b) })
}
```

The body of `f.Fuzz` is the whole harness: take some bytes, call `Parse`, ignore the result. If `Parse` panics or hangs, that is a failure. Nothing else is needed.

The three `f.Add` calls are the {{< term "seed-corpus" "seed corpus" >}}, the valid inputs the fuzzer starts from, one for each record type. Real samples make the best seeds. From there, the fuzzer is {{< term "coverage-guided-fuzzing" "coverage-guided" >}}: it watches which parts of the code each input reaches, keeps any input that reaches something new, and mutates that one further. That is what the `new interesting` counter in the output means: how many inputs were kept for reaching new code.

## Bug 1: the length is trusted

In the first buggy version, `Parse` slices `b[pos+3 : pos+3+n]` without checking that `n` bytes are really left. I fuzzed it:

```
$ go test -fuzz=FuzzParse -fuzztime=200000x
fuzz: elapsed: 0s, execs: 289 (2489/sec), new interesting: 1 (total: 4)
--- FAIL: FuzzParse (0.12s)
    testing.go:2078: panic: runtime error: slice bounds out of range [:12343] with capacity 24
    Failing input written to testdata/fuzz/FuzzParse/a3c431880a157b71
```

(I cut the stack trace. Go 1.27.3 prints more detail than Go 1.26 did, and the capacity number differs from run to run.) `-fuzztime=200000x` means "stop after 200000 executions"; here it failed after 289, which is the same ballpark as the original run's 251. The file name is a hash of the content, so the same crashing input got the same name as before.

The file holds the input after Go **minimized** it. Minimizing means the fuzzer tries to shrink a crashing input while it still crashes, so you get the smallest example instead of a pile of noise:

```
go test fuzz v1
[]byte("TLV1\x0200")
```

Read it as: `TLV1`, type 2, then the two length bytes are the characters `0` and `0`, which is `0x3030`, 12336. The parser tried to take 12336 bytes from an input of 7. Now the crash is saved, so a plain `go test` replays it and fails, until the fix:

```go
if n > len(b)-pos-3 { return nil, ErrFormat }
```

That is, check the length against what is really left before using it. The saved file stays in `testdata/fuzz` as a permanent {{< term "regression" "regression" >}} test, so this bug can never come back unnoticed. Commit it.

## Bug 2: int32 arithmetic

The second buggy version fixed bug 1 but computed the size of a "repeat" record with 32-bit signed numbers. Same command, new crash:

```
--- FAIL: FuzzParse (0.12s)
    panic: runtime error: makeslice: len out of range
    Failing input written to testdata/fuzz/FuzzParse/1461c70ced3bd442
```

(Again with a stack trace that I cut.) The minimized input is:

```
[]byte("TLV1\x02\x00\x06A00020")
```

Type 2, length 6, and value `A00020`. The count is the first four bytes `A000`, which is `0x41303030`. The size is the next byte, `'2'`, which is 50. My code multiplied `int32(count) * int32(size)`. That product does not fit in 32 bits and wraps around to a **negative** number (here about -1.15 billion). A negative total passes the check `total > maxTotal`, because it is less than the maximum, and then `make` fails with "len out of range".

This is an {{< term "integer-overflow" "integer overflow" >}} in the length arithmetic. It could have gone differently: if the product had wrapped to a small positive number, the buffer would just be too short. If the check had been missing, a 4-byte field could ask for gigabytes. The fix is to compute in `uint64` and compare with a cap before allocating:

```go
total := uint64(count) * uint64(val[4])
if total > maxTotal { return nil, ErrFormat }
```

## Bug 3: the hang

The third buggy version handled a trailing backslash wrongly. In `unescape`, the index only advanced when there was a character after the backslash; with a backslash at the very end, the loop ran forever. This failure is different, because nothing panics:

```
fuzz: elapsed: 3s, execs: 180125 (60020/sec), new interesting: 21 (total: 26)
fuzz: elapsed: 6s, execs: 180125 (0/sec), new interesting: 21 (total: 26)
...
--- FAIL: FuzzParse (60.98s)
    fuzzing process hung or terminated unexpectedly: exit status 2
    Failing input written to testdata/fuzz/FuzzParse/7c12144b9877ed15
```

(I removed the repeated progress lines in the middle.) The exec counter stops at 180125 and shows `0/sec`: the workers are stuck inside an input that never returns. In the original run Go gave up after about ten seconds; in this re-run it took about a minute, so treat that time as machine- and version-dependent. The saved input is not minimized, because minimizing a hang is slow, so it contains some noise:

```
[]byte("TLV1\x03\x00\x04a\x1cJ\\nb")
```

(The exact bytes differ from run to run and from the original run; the file name changes with them.) Read it as: type 3, length 4, and a value of four bytes, `a`, a control character, `J` and a final backslash. The `nb` after it is leftover noise. That final backslash is the trailing-backslash case. Replaying a hang with plain `go test` would hang too, so give it a timeout: `go test -run=FuzzParse/7c12144b9877ed15 -timeout 5s` printed `panic: test timed out after 5s`. The fix is to move the index forward on every path (`i += 2` unconditionally), so each loop turn consumes at least one byte.

## After the fixes

With the final parser and the three saved inputs in `testdata/fuzz/FuzzParse/`, a plain `go test -v` runs the seeds and the saved inputs as ordinary tests:

```
$ go test -v -run=FuzzParse
--- PASS: FuzzParse (0.00s)
    --- PASS: FuzzParse/seed#0 (0.00s)
    --- PASS: FuzzParse/seed#1 (0.00s)
    --- PASS: FuzzParse/seed#2 (0.00s)
    --- PASS: FuzzParse/1461c70ced3bd442 (0.00s)
    ...
```

(The listing continues with the other two saved inputs, `a3c431880a157b71` and `da26de22b41b4c2d`; I cut it. The third file is the saved hang from the original run.) Then I let the fuzzer search again, with a bigger budget:

```
$ go test -fuzz=FuzzParse -fuzztime=2000000x
fuzz: elapsed: 8s, execs: 2000000 (140601/sec), new interesting: 4 (total: 42)
PASS
```

Two million executions, no crash. That is **not** proof that the parser is correct; it only means this search did not find a problem. I report counts, not speed: execs per second vary with the machine and the other programs running on it.

## Properties and differences

So far the only "oracle", the thing that tells the fuzzer it found a bug, was "it panicked or hung". That one is free. A better oracle is a property. `FuzzRoundTrip` checks that encoding a type 3 record and parsing it again gives back the same data:

```go
rs, err := Parse(Encode([]Record{{3, d}}))
if err != nil || len(rs) != 1 || !bytes.Equal(rs[0].Data, d) {
	t.Fatalf("round trip failed for %q: %v %v", d, rs, err)
}
```

It passed 500000 executions here, so I found no logic bug. I did not run {{< term "differential-testing" "differential fuzzing" >}}: it compares your parser with another implementation on the same input (for example a JSON subset against `encoding/json`) and reports any disagreement. The shape is the same.

## In real projects

- CI: give fuzzing a short budget on pull requests (`-fuzztime=30s`) and a long one nightly. See [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/).
- C and C++: libFuzzer and AFL++ are the usual tools, and OSS-Fuzz runs them at scale; Rust has `cargo-fuzz`. I only name them; I did not run them.
- Pair the fuzzer with a sanitizer such as {{< term "addresssanitizer" "AddressSanitizer" >}} for C, because a memory bug in C may not crash by itself. Go and Rust give you {{< term "memory-safety" "memory safety" >}}, but their programs can still panic and hang.
- Dictionaries of keywords, and structure-aware fuzzing, help with formats that have checksums or grammars, where random bytes are rejected at the first check.

## Making fuzzing pay off

- Commit the files under `testdata/fuzz`; they are your regression tests.
- Seeds from real samples beat empty seeds.
- Fuzz your own parsers, never other people's services.
- Cap every allocation that depends on input.
- Silence is not proof.

## Exercise

Add a type 4 record whose 4-byte length is used directly in `make([]byte, n)`. Let the fuzzer find the problem, then add a cap and a regression test.

## What's next

The next post is "Logging, auditing and incident response". It covers the bugs that get through anyway: then what matters is whether you can tell what happened.
