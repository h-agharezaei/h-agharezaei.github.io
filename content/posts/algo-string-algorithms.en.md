+++
date = '2027-04-28T10:00:00+03:30'
draft = false
title = 'String algorithms: KMP and Rabin–Karp'
description = 'String search in Go: KMP and Rabin–Karp with real comparison counts, spurious hash hits, UTF-8 byte offsets and a test against strings.Index.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "strings", "kmp", "rabin-karp", "hashing", "go"]
cover = { image = "/images/covers/algo-string-algorithms.png", alt = "String algorithms: KMP and Rabin–Karp", hiddenInSingle = true }
+++

You search for a word in a document and the editor answers instantly. How? The simplest idea is to try every position: put the word at the start of the text, compare letter by letter, and if something differs, move one step right and start over. That works, and for everyday text it is fast enough. But it has a bad case. Searching for `aaab` in a text of 10,000 a's followed by one b costs 39,992 byte comparisons, about four times the length of the text, because at nearly every position it matches `aaa` and only fails at the fourth letter. With a longer pattern the waste grows.

This post is about two classic ways to avoid that waste. The {{< term "kmp-algorithm" "KMP algorithm" >}} never goes back in the text. {{< term "rabin-karp" "Rabin–Karp" >}} compares a short number computed from each piece of text instead of the letters themselves. The [previous post](/posts/algo-greedy-backtracking/) searched through choices; here we search through text. Costs are counted as in [Big-O with real measurements](/posts/algo-big-o-measured/), and Rabin–Karp uses ideas from [hash tables](/posts/algo-hash-tables/) such as a {{< term "hash-collision" "collision" >}}, two different inputs with the same hash.

> I re-ran every output with Go 1.27 on macOS (arm64). It is a local example and its tests pass with `go test -race`. The machine was busy, so I publish comparison counts, not timings.

## Naive search

In the rest of the post, `n` is the length of the text and `m` the length of the pattern. Naive search slides the pattern over the text and compares byte by byte. In the worst case it does about n·m comparisons, as in the opening example (n ≈ 10,000, m = 4).

The waste comes from forgetting. When the pattern `aaab` has matched `aaa` and then fails, naive search throws that knowledge away and starts again one position later, re-reading letters it has already seen. KMP's whole idea is to keep what the failed attempt taught us.

## KMP: never go back in the text

Take a small case. We search for `ababaca` in `abababaca`. The first five letters of the text, `ababa`, match the pattern. Then the text has `b` where the pattern wants `c`: a mismatch.

Naive search would now go back to text position 1 and begin again. But we know the text just had `ababa`. The last three letters of that, `aba`, are also the first three letters of the pattern. So there is no need to re-read anything: we can pretend the match so far is `aba` and carry on by comparing the pattern's fourth letter with the same text letter. The text position stays where it is.

To make that decision for any mismatch, KMP precomputes a table from the pattern alone. The **failure function** `fail` stores, for each prefix of the pattern, the length of its longest *proper* prefix that is also a suffix of it. (A proper prefix is one that is shorter than the whole string.) For the prefix `ababa`: its prefixes are `a`, `ab`, `aba`, `abab`; its suffixes are `a`, `ba`, `aba`, `baba`. The longest one in both lists is `aba`, length 3. Here is the whole table for `ababaca`, as printed by the demo:

```
i       0 1 2 3 4 5 6
pat    a b a b a c a 
fail   0 0 1 2 3 0 1 
```

Each column describes the prefix that ends at that position. `fail[4] = 3` is exactly what we just worked out: after matching `ababa`, if the next letter does not fit, we can keep the 3 letters `aba` and continue from there. If that fails too, we look at `fail[2] = 1` and keep just `a`, and so on, down to 0 (start over).

Now the search itself. The text index `i` only moves forward. The variable `k` says how many pattern letters are matched right now. On a mismatch we do not touch `i`; we only shrink `k` to `fail[k-1]`:

```go
for k > 0 && text[i] != pat[k] {
	k = fail[k-1]
}
if text[i] == pat[k] { k++ }
if k == len(pat) { /* match at i-k+1 */ k = fail[k-1] }
```

(This is the core of the demo's `KMP`; the real function also counts comparisons.) Tracing `abababaca`: `i` = 0 to 4 match `ababa`, so `k` = 5. At `i` = 5 the text has `b` but the pattern wants `c`, so `k` becomes `fail[4]` = 3. The pattern's letter at position 3 is `b`, which matches, so `k` becomes 4. At `i` = 6, 7 and 8 the letters `a`, `c`, `a` match, `k` reaches 7, and we report a match starting at 8 − 7 + 1 = 2. The text index went 0 to 8 once. I ran this tiny case separately: naive search needs 14 comparisons for it and KMP needs 10.

On the opening example, the demo counts every byte comparison for naive search and KMP. The second input is 10,000 random letters from `abcd`, searched for `abca`:

```
adversarial  n=10001 matches=1 naive=39992 kmp=19998
random abcd  n=10000 matches=32 naive=13290 kmp=12471
```

On the adversarial text (10,000 a's and one b, pattern `aaab`) KMP does about 2n comparisons, and naive does about 4n. On random text over four letters they are almost the same, because mismatches come early and there is little to save. So KMP does not make typical searches faster. What it gives is a guarantee: the cost is O(n + m) no matter what the input looks like.

## Rabin–Karp: compare numbers first

Rabin–Karp takes a different road. Comparing two numbers costs one step, comparing two strings costs up to m. So turn each window of m letters into a number (a **hash**) and compare numbers; only look at the letters when the numbers agree.

Computing a fresh hash for every window would cost m each time, which is no better. The trick is to update the hash as the window slides, in O(1). This is a {{< term "rolling-hash" "rolling hash" >}}. Here is the idea with ordinary decimal digits. The text is `31415`, the window is 3 digits, and the window's number is `314`. Slide one step: drop the 3, shift, and add the new digit 1. That is (314 − 3·100) · 10 + 1 = 141. No need to re-read the middle digits. Rabin–Karp does the same, treating each byte as a digit in base 256:

```go
ht = ((ht - int(text[i])*pow%mod + mod)*base + int(text[i+m])) % mod
```

`pow` is base^(m−1) mod `mod`, the "weight" of the leftmost digit (it was 100 in the decimal example). The `% mod` keeps the numbers small enough to fit in an integer; the `+ mod` keeps the subtraction from going negative.

Because of `mod`, different windows can have the same hash. Suppose we work with base 10 and mod 7, and search for `265`. It hashes to 265 mod 7 = 6. The window `314` hashes to 314 mod 7 = 6 as well. Same hash, different text. This is a **spurious hit**. So an equal hash is only a hint, and every hit must be verified by comparing the real letters. That is why the demo counts hash hits and spurious hits separately.

To see the effect of `mod`, the demo searches 10,000 random letters over `abcd` for the pattern `abcabd`, once with a deliberately tiny modulus and once with a large one:

```
RK random mod=101        matches=1 hash-hits=81 spurious=80
RK random mod=1000000007 matches=1 hash-hits=1 spurious=0
```

With 101 possible hash values, a window that is not the pattern still has about a 1 in 101 chance of hitting by luck. For almost 10,000 windows that suggests around 99 false alarms, and the run gave 80, the same order of size. Each false alarm costs a verification of up to m letters. With the large modulus, there was no false alarm at all. Correctness never depends on the modulus, because verification catches every false alarm; only speed does. Real implementations use a large modulus or let a 32- or 64-bit integer wrap around. Rabin–Karp has one more strength: it can look for many patterns of the same length at once. Put their hashes in a set and look up each window's hash in it.

## Bytes, runes and Persian

Everything above worked on bytes. For exact matching this is also correct for UTF-8 text, because a valid UTF-8 pattern can only match starting at the beginning of a character. The thing to watch is the *index* you get back. The demo searches the Persian word "سلام" in "سلام دنیا، سلام گو":

```
bytes: [0 20] len bytes 33 runes 18
 byte 0 -> rune 0
 byte 20 -> rune 11
```

The matches are at byte offsets 0 and 20. Each Persian letter takes two bytes in UTF-8, so the string is 33 bytes but only 18 characters. A {{< term "rune" "rune" >}} is Go's name for one character (one Unicode code point). Counting runes before byte 20 gives 11, so the second match starts at rune index 11. If you show a user "found at position 20" for this text, they would count the wrong thing. Two related problems, case-insensitive search and Unicode normalisation (the same letter written as different sequences of code points), are different from exact matching. I did not run either of them; the usual advice is to normalise both strings first and then search.

## What `strings.Index` does

I read the Go 1.27 source. According to it, `strings.Index` handles an empty pattern and a one-byte pattern separately (the latter with `IndexByte`), uses a brute-force routine when both strings are small, and otherwise looks for the pattern's first byte with `IndexByte`. If that keeps producing false starts, it switches to a different routine. For patterns longer than `bytealg.MaxLen` that routine is a Rabin–Karp one (`bytealg.IndexRabinKarp`, using a 32-bit hash that wraps around). `MaxLen` and the short-pattern routines depend on the platform. These are implementation details that can change; in production, just call `strings.Index`.

## Testing against the standard library

How do we know our KMP and Rabin–Karp are right? A test generates 5,000 random texts (up to 59 letters) and patterns (1 to 5 letters) over the alphabet `{a, b}`, with seed 7. For each pair it compares KMP and Rabin–Karp (with modulus 101, to force collisions) against a plain scan of every position, and checks that the first match equals `strings.Index`. `go test -race` passes. A tiny alphabet is on purpose: it makes repeated prefixes common, which is exactly what breaks wrong KMP code.

## Complexity

| Algorithm | Preprocessing | Search | Worst case |
|---|---|---|---|
| Naive | none | O(n·m) | O(n·m) |
| KMP | O(m) | O(n) | O(n + m) |
| Rabin–Karp | O(m) | O(n) expected | O(n·m) if hashes collide |

Two other tools I only name here: the Z-algorithm (the same idea as the failure function, computed differently) and suffix arrays (index a text once, then answer many pattern queries quickly).

## Where string search bites

- **Know what your language indexes.** Bytes, UTF-16 units and code points give different positions for the same text. Decide which one your API returns and say so.
- **A hash hit is a hint, not an answer.** Always verify with a real comparison, or your search will occasionally report matches that are not there.
- **Test with a tiny alphabet and compare with a trivial implementation.** Bugs in prefix logic hide in random text over 26 letters but show up quickly over two.
- **In practice, use the standard library first.** Writing KMP is a good way to understand it, not a reason to replace `strings.Index`.

## Exercise

Make `RabinKarp` search for several patterns of equal length using a map of hashes, and count the spurious hits for modulus 101. Then work out the failure table for `aabaaab` by hand first, and check it with `Prefix`.

## What's next

"Bloom filters and consistent hashing" ends the series with two more ideas built on hashing.
