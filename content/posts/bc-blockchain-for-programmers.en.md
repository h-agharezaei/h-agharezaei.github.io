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

Edit a record in a hash-linked log, recompute every hash, and local verification passes again. So what does a blockchain add? This 32-post course answers it for programmers: no prices, no investing, just data structures, cryptography, networking and code. Background posts: [a hash table from scratch](/posts/algo-hash-tables/), [common cryptography mistakes](/posts/sec-crypto-mistakes/), [consensus and Raft](/posts/ds-consensus-raft/), [logging, auditing and incident response](/posts/sec-logging-audit-incident-response/) and the [Binance hack write-up](/posts/binance-hack-hot-wallet-2026/), where the hard part was off-chain.

> The demo was run with Go 1.27 on macOS (arm64).

## The problem in one sentence

Several parties who do not trust each other want to keep one shared, append-only list of records, and none of them may be the operator who decides what goes in.

That is a {{< term "distributed-ledger" "distributed ledger" >}}. *Shared*: everybody keeps a full copy. *Append-only*: history is not edited, only extended. *No operator*: there is no admin with `UPDATE` rights, so the parties need a rule, a {{< term "consensus" "consensus" >}} protocol, to agree on the next entry. Without trust, the protocol must survive a {{< term "byzantine-fault" "Byzantine fault" >}}: a participant who lies, not one who merely crashes. Raft assumes honest nodes; that is the key difference.

## Why not a database with an audit log?

If one company runs the system, a database plus an {{< term "audit-log" "audit log" >}} is the right answer: faster, cheaper, easier to fix. The question is who you trust:

| | Database + audit log | Blockchain |
|---|---|---|
| Who decides what is written | the operator | a protocol among many parties |
| Who can rewrite history | the operator (or anyone who owns the server) | nobody alone, without others noticing |
| Correcting a mistake | `UPDATE` | append a new correcting entry |
| Throughput and cost | high, cheap | low, every node does the work |

The audit log protects you from your staff, not your customers from you: you hold the keys to both data and log.

## Tamper-evident, not tamper-proof

The basic tool is a {{< term "hash-chain" "hash chain" >}}: each record stores the {{< term "sha-256" "SHA-256" >}} hash of the previous record. Change one record and the next link breaks. A minimal Go version:

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

`main` appends three records, lets a "peer" remember the last hash, edits record 1, then recomputes every hash (`rehash`):

```
0 "alice -> bob: 10" prev=-            hash=a09bc3c354a1
1 "bob -> carol: 4"  prev=a09bc3c354a1 hash=e2dcc871b98a
2 "carol -> dave: 1" prev=e2dcc871b98a hash=89e56e1e69d6
verify: <nil>
after edit: record 1: hash mismatch
after rehash: <nil>
head matches peer: false
```

The last two lines are the lesson. Whoever controls the whole file can recompute the chain and pass local verification. The chain is only *tamper-evident* if someone else holds a hash you cannot change. In a blockchain many independent nodes hold the head, so a rewrite shows up. Making rewrites *expensive* (proof of work, stake) comes later.

The missing piece is identity: who may append "bob -> carol"? That needs Bob's {{< term "digital-signature" "digital signature" >}}, covered later.

## Where blockchain is the wrong tool

- One organization controls all writers: use a database. Add a hash-chained audit log if you need evidence.
- You need to delete data (privacy law, mistakes): append-only and fully replicated makes that very hard.
- The data comes from the outside world: the chain proves *what was written*, not that it is *true*.
- You need high throughput or low latency: every node validates everything.
- The parties already trust a neutral operator (a bank, a registry): that operator is simpler.

## The course

1. Fundamentals (Go, one Rust post): hashes, Merkle trees, keys, transactions, proof of work, P2P, forks, a small full node.
2. Ethereum (Solidity, Go, Rust): the EVM, contracts with Foundry, tokens, clients, an indexer, wallets.
3. DeFi and security (Solidity, Go): AMMs, lending, oracles, contract security, MEV.
4. Advanced: proof of stake, rollups, bridges, zero-knowledge, exchange engineering, a capstone.

Everything runs locally, without real keys.

## What a hash chain does not prove

- A hash chain proves order and integrity, not truth or authorship.
- Tamper evidence needs an independent copy of the head hash.
- Without the no-operator requirement, you are building a slow database.
- Hash a well-defined encoding. The `"|"` separator here is a toy; a real format needs an unambiguous byte layout.

## Exercise

1. Run the demo and delete record 1 instead of editing it. Which error do you get?
2. Swap records 1 and 2. Which check catches it?
3. Store `peerHead` in a second file and write a `check` command that compares it to the log.

## What's next

*Hashes, blocks and the chain: a first blockchain in Go* turns these records into the real blocks everything else builds on.
