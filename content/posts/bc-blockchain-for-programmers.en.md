+++
date = '2026-11-02T18:00:00+03:30'
draft = false
title = 'Blockchain for programmers: what problem it actually solves'
seoTitle = 'Blockchain for programmers: the problem it solves'
description = 'Blockchain for programmers: a shared append-only ledger without a central operator, tamper evidence in Go, and when a database is better.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "hash", "ledger", "beginner"]
cover = { image = "/images/covers/bc-blockchain-for-programmers.png", alt = "Blockchain for programmers: what problem it actually solves", hiddenInSingle = true }
+++

Most of what we hear about blockchains is about prices and investing. I want to look at them from a different angle: as a programmer, what problem does a blockchain actually solve that an ordinary database does not? And where should you not reach for one at all?

This is the first part of a 32-post course about exactly that: data structures, cryptography, networking and code. No prices, no investment advice. You do not need to know anything about blockchains beforehand. If you want more background, these posts help: [a hash table from scratch](/posts/algo-hash-tables/), [common cryptography mistakes](/posts/sec-crypto-mistakes/), [consensus and Raft](/posts/ds-consensus-raft/), [logging, auditing and incident response](/posts/sec-logging-audit-incident-response/), and the [Binance hack write-up](/posts/binance-hack-hot-wallet-2026/), which shows that sometimes the problem is not on the blockchain at all.

> The demo was run with Go 1.27 on macOS (arm64), and the output is what I saw.

## The problem in one sentence

Several parties who do not trust each other want to keep one shared list together, in a way that only allows adding to it, and without any of them being in charge.

A concrete example: a few companies trade with each other and want one shared ledger. If the ledger lives with one of them, the others have to trust that company not to delete or change anything. A blockchain is an attempt to make that trust unnecessary.

Such a ledger is called a {{< term "distributed-ledger" "distributed ledger" >}}. That one sentence has three conditions worth looking at separately:

- **Shared:** every party keeps a full copy of the ledger.
- **Append-only:** the past is never edited or deleted. If there is a mistake, a new correcting entry is added, just like in bookkeeping.
- **Nobody in charge:** there is no admin who can simply run an `UPDATE`. So the parties need a shared rule for agreeing on the next entry. That rule is called a {{< term "consensus" "consensus" >}} protocol.

There is one subtle point. Because the parties do not trust each other, the protocol has to cope with someone who deliberately lies, not only with a computer that crashes. This kind of failure is called a {{< term "byzantine-fault" "Byzantine fault" >}}. It is the main difference between a blockchain and an algorithm like Raft: Raft assumes every node is honest and can only fail by stopping.

## Why isn't a database with an audit log enough?

This is the first question every programmer asks, and the honest answer is: often it is. If one company runs the system, a database plus an {{< term "audit-log" "audit log" >}} (a log that records who changed what, and when) is the right answer. It is faster, cheaper and simpler.

The real question is not technical. It is **who you trust**:

| | Database + audit log | Blockchain |
|---|---|---|
| Who decides what gets written | The operator | A protocol among several parties |
| Who can rewrite history | The operator, or anyone with access to the server | Nobody alone, without the others noticing |
| Fixing a mistake | An `UPDATE` | Appending a correcting entry |
| Speed and cost | High and cheap | Low, because every node repeats all the work |

The second row matters most. An audit log protects you from your own employees, but it does not protect your customers from you, because you hold both the data and the log. If you wanted to, you could change both together.

## Tampering can be seen, not prevented

The basic tool for making tampering visible is a {{< term "hash-chain" "hash chain" >}}. The idea is simple: compute a "fingerprint" for every record and write each record's fingerprint into the next one. The fingerprint comes from the {{< term "sha-256" "SHA-256" >}} hash function: it takes any input and returns a fixed-size, random-looking string that changes completely when the input changes even slightly (the next post looks at it more closely). Now if someone changes a record, its fingerprint changes and no longer matches what the next record says.

The simplest version in Go looks like this. Each record holds its own data, the previous record's hash and its own hash. `verify` walks from start to end and, for every record, checks that the link to the previous one is right and that its own hash matches its content:

```go
type Record struct {
	Data     string
	PrevHash string
	Hash     string
}

func hashOf(data, prev string) string {
	sum := sha256.Sum256([]byte(prev + "|" + data))
	return hex.EncodeToString(sum[:])
}

func verify(log []Record) error {
	prev := ""
	for i, r := range log {
		if r.PrevHash != prev {
			return fmt.Errorf("record %d: prev link broken", i)
		}
		if hashOf(r.Data, r.PrevHash) != r.Hash {
			return fmt.Errorf("record %d: hash mismatch", i)
		}
		prev = r.Hash
	}
	return nil
}
```

The `main` program does these steps in order:

1. It builds three records and prints them.
2. A "peer" keeps only the hash of the last record.
3. Record 1 is quietly edited.
4. Whoever edited it recomputes every hash (`rehash`) to cover their tracks.

```
0 "alice -> bob: 10" prev=-            hash=a09bc3c354a1
1 "bob -> carol: 4"  prev=a09bc3c354a1 hash=e2dcc871b98a
2 "carol -> dave: 1" prev=e2dcc871b98a hash=89e56e1e69d6
verify: <nil>
after edit: record 1: hash mismatch
after rehash: <nil>
head matches peer: false
```

The first three lines are the healthy chain: each record's `prev` is the `hash` of the record above it. `verify: <nil>` means nothing is wrong. After the edit, `verify` immediately reports that record 1's hash does not match.

But the last two lines are the real lesson of this post. Whoever holds the whole file can recompute every hash after the edit, and `verify` no longer reports anything (`after rehash: <nil>`). So a hash chain alone does not prevent tampering. The only thing that gives it away is the last line: the final hash no longer matches what the peer kept.

So a chain only shows tampering (it is *tamper-evident*) when **someone else** holds the last hash, someone whose copy you cannot change. In a blockchain many independent nodes hold the last hash, so rewriting history gets noticed. Making a rewrite not only visible but also **expensive** is the job of proof of work and proof of stake, which come later.

One piece is still missing: identity. In this demo anyone can add the record "bob -> carol", even if they are not bob. For only bob to be able to spend his money, we need his {{< term "digital-signature" "digital signature" >}}, which also comes in a later part.

## Where a blockchain is the wrong tool

A blockchain is an expensive tool, so it is worth knowing where it does not belong:

- **Everyone who writes is under one organisation.** A database is enough. If you need tamper evidence, build an audit log with a hash chain.
- **You must be able to delete data.** For example because of privacy law or a mistake. A ledger that is append-only and copied to everyone makes that very hard.
- **The data comes from the outside world.** The chain only proves *what was recorded*, not that it is *true*. If someone records the wrong temperature of a warehouse, the blockchain just keeps that wrong temperature very carefully.
- **You need high throughput or low latency.** Every node checks everything itself, so the system is slow.
- **Everyone already trusts a neutral party.** Like a bank or a land registry. That party is simpler and cheaper.

In short: drop the "nobody in charge" condition and you are just building a slow database.

## The course map

The course has four parts:

1. **Foundations** (Go, plus one Rust post): hashes, Merkle trees, keys, transactions, proof of work, P2P networking, forks, and finally a small complete node.
2. **Ethereum** (Solidity, Go, Rust): the Ethereum Virtual Machine (EVM), writing contracts with Foundry, tokens, clients, an indexer and wallets.
3. **DeFi and security** (Solidity, Go): automated market makers (AMMs), lending, oracles, contract security and MEV.
4. **Advanced**: proof of stake, rollups, bridges, zero knowledge, exchange engineering, and a capstone project.

Everything runs on your own machine, with no real keys and no real money.

## What a hash chain does not prove

Before moving on, let's go over the limits of this tool once more:

- A hash chain proves that the order and content of the records were not changed. It does not prove the content is correct, or who wrote it.
- Tampering can only be seen when an independent copy of the last hash exists somewhere else.
- The bytes you hash must be defined exactly and without ambiguity. The `"|"` separator in this demo only works because `PrevHash` is always either empty or exactly 64 characters. Glue several free-text fields together like this and the boundaries between them become ambiguous, so two different records can give the same hash. The next post solves this properly.

## Exercise

1. Run the demo and this time, instead of editing record 1, delete it entirely. Which error do you get?
2. Swap records 1 and 2. Which check catches it?
3. Store `peerHead` in a separate file and write a `check` command that compares it with the log.

## What's next

The next part is "Hashes, blocks and the chain: a first blockchain in Go". There we turn these simple records into real blocks, with a header and an exact encoding, which is the foundation the rest of the course builds on.
