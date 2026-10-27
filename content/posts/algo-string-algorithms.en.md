+++
date = '2027-04-28T10:00:00+03:30'
draft = false
title = 'String algorithms: KMP and Rabin–Karp'
description = 'String search in Go: KMP and Rabin–Karp with real comparison counts, spurious hash hits, UTF-8 byte offsets and a test against strings.Index.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "strings", "kmp", "rabin-karp", "hashing", "go"]
cover = { image = "/images/covers/algo-string-algorithms.png", alt = "String algorithms: KMP and Rabin–Karp", hiddenInSingle = true }
+++

After [Greedy algorithms and backtracking](/posts/algo-greedy-backtracking/) we leave choices and look at text. Finding a pattern inside a text looks trivial, yet the naive way can do four times the necessary work. Two classic fixes are the {{< term "kmp-algorithm" "KMP algorithm" >}} and {{< term "rabin-karp" "Rabin–Karp" >}}. Costs are counted as in [Big-O measured](/posts/algo-big-o-measured/); Rabin–Karp leans on [hash tables](/posts/algo-hash-tables/) ideas such as a {{< term "hash-collision" "collision" >}}.

> Go 1.26, local example, tests with `go test -race`. Machine load was not low, so I publish counts, not timings.

## Naive search

Slide the pattern over the text and compare byte by byte. My version increments a counter on every byte comparison. Worst case is O(n·m): text `aaaa…ab` (10000 a's and a b), pattern `aaab`.

## KMP: never go back in the text

When a mismatch happens, the part already matched tells us where the next match could start. The **failure function** stores, for each prefix of the pattern, the length of its longest proper prefix that is also its suffix. For `ababaca`:

```
i       0 1 2 3 4 5 6
pat    a b a b a c a 
fail   0 0 1 2 3 0 1 
```

Read `fail[4] = 3`: after matching `ababa`, if the next byte fails, we keep `aba` and continue from there. The search loop never moves the text index backwards:

```go
for k > 0 && text[i] != pat[k] {
	k = fail[k-1]
}
if text[i] == pat[k] { k++ }
if k == len(pat) { /* match at i-k+1 */ k = fail[k-1] }
```

Building the table is O(m) and the search is O(n). Comparison counts from my run (`cmp` counts every byte comparison):

```
adversarial  n=10001 matches=1 naive=39992 kmp=19998
random abcd  n=10000 matches=32 naive=13290 kmp=12471
```

On the adversarial text KMP does about 2n comparisons and naive about 4n. On random text over four letters they are almost the same, because mismatches come early. KMP guarantees the worst case; it does not win on typical input.

## Rabin–Karp: compare hashes first

Hash every window of length m and compare with the pattern's hash. Moving the window must cost O(1), hence the {{< term "rolling-hash" "rolling hash" >}}:

```go
ht = ((ht - int(text[i])*pow%mod + mod)*base + int(text[i+m])) % mod
```

`pow` is base^(m-1) mod `mod`. Equal hashes do not prove equal strings, so each hit is verified with a real comparison. I counted hits and spurious hits (hash equal, text different) on 10000 random bytes over `abcd`, pattern `abcabd`, with a deliberately small modulus and a large one:

```
RK random mod=101        matches=1 hash-hits=81 spurious=80
RK random mod=1000000007 matches=1 hash-hits=1 spurious=0
```

With 101 possible hash values, a window matches by luck about one time in 101: 80 false alarms here, each costing a verification. Correctness never depends on the modulus (verification catches every one); only speed does. Real implementations use a large modulus or a 32/64-bit wraparound hash. Rabin–Karp also searches many patterns of equal length at once: put their hashes in a set and look each window up.

## Bytes, runes and Persian

KMP above works on bytes. For exact matching this is also correct on UTF-8, because a valid UTF-8 pattern can only match at a character boundary. The catch is the index:

```
bytes: [0 20] len bytes 33 runes 18
 byte 0 -> rune 0
 byte 20 -> rune 11
```

Searching "سلام" in "سلام دنیا، سلام گو" returns byte offsets 0 and 20; the second match is the 11th {{< term "rune" "rune" >}}. Persian letters take two bytes each. Case-insensitive search and Unicode normalisation (the same letter written as different code point sequences) are different problems; I describe them but did not run them: normalise both strings first, then search.

## What `strings.Index` does

I read the Go 1.26 source. According to it, `strings.Index` handles a one-byte pattern with `IndexByte`, uses optimised routines for short patterns, and when `IndexByte` keeps producing false starts it switches to a Rabin–Karp fallback (`bytealg.IndexRabinKarp`, a 32-bit wraparound hash). These are implementation details that can change; in production just call it.

## Testing against the standard library

A test generates 5000 random texts and patterns over `{a,b}` (seed 7, lengths up to 60 and 5), and checks that KMP and Rabin–Karp (modulus 101, to force collisions) return the same matches as a plain scan, and the first match equals `strings.Index`. `go test -race` passes. A small alphabet makes repeated prefixes common, exactly what breaks KMP bugs.

## Complexity

| Algorithm | Preprocessing | Search | Worst case |
|---|---|---|---|
| Naive | none | O(n·m) | O(n·m) |
| KMP | O(m) | O(n) | O(n + m) |
| Rabin–Karp | O(m) | O(n) expected | O(n·m) if hashes collide |

Other tools I only name: the Z-algorithm (same idea as the failure function, computed differently) and suffix arrays (index a text once, then answer many pattern queries).

## A few things to watch

- Check how your language indexes strings: bytes, UTF-16 units or code points.
- A hash hit is a hint; always verify.
- Test with a tiny alphabet and compare with a trivial implementation.
- In practice, use the standard library first.

## Exercise

Make `RabinKarp` search for several patterns of equal length with a map of hashes, and count the spurious hits for modulus 101. Then print the failure table for `aabaaab` by hand first, and check it with `Prefix`.

## What's next

Next up: "Bloom filters and consistent hashing".
