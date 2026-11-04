+++
date = '2026-11-28T18:00:00+03:30'
draft = false
title = 'Proof of stake, BFT and finality'
description = 'Proof of stake and BFT finality in Go: stake-weighted proposers, signed prevotes and precommits, a 2/3 quorum, and slashing for double-signing.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "proof-of-stake", "bft", "finality"]
cover = { image = "/images/covers/bc-proof-of-stake-bft.png", alt = "Proof of stake, BFT and finality", hiddenInSingle = true }
+++

In [Proof of work, difficulty and mining](/posts/bc-proof-of-work-mining/) a vote cost electricity, and [Forks, reorgs and the heaviest-chain rule](/posts/bc-forks-reorgs/) showed the other price: a block is never final. Whenever a heavier chain arrives, the earlier blocks are dropped. So two questions remain: who produces a block, and when does it become final? [MEV and transaction ordering](/posts/bc-mev-ordering/) only asked who orders the transactions inside it.

{{< term "proof-of-stake" "Proof of stake" >}} replaces burned energy with locked money. It is like a meeting where everyone puts down a deposit in exchange for a vote. Each {{< term "validator" "validator" >}} locks an amount as its stake. Its vote weighs as much as that stake, and if its cheating is proven, part of the deposit is destroyed.

This voting has to tolerate a {{< term "byzantine-fault" "Byzantine fault" >}}. In [Consensus and Raft](/posts/ds-consensus-raft/) nodes could crash but never lie. A Byzantine node is different: it may tell each person something different. Here some participants lie on purpose.

> Go 1.27 on macOS (arm64), local example code. The `wallet` package (secp256k1) is copied unchanged from the [small full node](/posts/bc-toy-node-go/) demo; keys come from names like "alice": public, demo only. This is a **teaching model** of one Tendermint-like round: no timeouts, round changes or locking, synchronous delivery. Not a production protocol.

## Who proposes

First we must decide whose turn it is. There are five validators: alice with stake 30, bob 25, carol 20, dave 15 and erin 10. The total stake is 100. Each should get a chance proportional to its stake: alice thirty percent of the turns, erin ten percent.

The problem is that all nodes must agree on one proposer without anyone telling them. So the choice must be a function of things everybody knows: a shared seed, the block height and the round number. Everyone computes the same function and gets the same answer (shortened):

```go
func (s *Set) Proposer(seed Hash, height uint64, round uint32) *Validator {
	// h = sha256(seed || height || round)
	r := binary.BigEndian.Uint64(h[:8]) % s.Total()
	for _, v := range s.Vals {
		if r < v.Stake {
			return v
		}
		r -= v.Stake
	}
	panic("unreachable")
}
```

The function turns the hash into a number `r` between 0 and 99. Then it walks the validators in order like consecutive ranges: alice gets 0 to 29, bob 30 to 54, and so on. Whoever's range contains `r` is the proposer. To check that the chances really follow stake, I counted over 10,000 heights:

```
proposer counts over 10000 heights: alice(30)=2986 bob(25)=2538 carol(20)=1947 dave(15)=1535 erin(10)=994
```

Roughly 30, 25, 20, 15 and 10 percent. The weak point of this method is the seed. If the seed were, say, the previous block's hash, a proposer could try many variants of its block and publish the one that makes it proposer again. That is called grinding. As far as I know, Ethereum mixes a value revealed by each proposer into its seed (RANDAO), so the last proposer can only reveal its value or skip its turn.

## Two votes and a 2/3 quorum

Now a proposer is chosen. How is the block approved? In three steps:

1. The proposer sends the block and everyone signs a prevote for it. A prevote means "I have seen this proposal".
2. A validator that sees prevotes for one block from more than 2/3 of the stake signs a precommit for it (otherwise for nil, meaning nothing). A precommit means "I have seen that two thirds of everyone saw the same proposal".
3. If more than 2/3 of the stake has precommitted one block, it is committed.

Two votes are needed because the first only says "I saw it". The second says "I know the others saw it too". Committing is safe only when nobody can later make a different block final.

The two-thirds rule is one line:

```go
func (s *Set) Quorum(stake uint64) bool { return 3*stake > 2*s.Total() }
```

Why two thirds and not a plain majority? First a small example. Four validators, one of them Byzantine. A {{< term "quorum" "quorum" >}} is three. Two groups of three out of four share at least two validators. Since only one is Byzantine, at least one of the two shared validators is honest, and an honest validator never votes for two different blocks. So two quorums for two different blocks cannot exist.

Now in general: n validators, f of them Byzantine. The Byzantine ones may stay silent, so a quorum must be able to form from just n−f, or the protocol would get stuck. Two quorums overlap in at least 2(n−f)−n = n−2f members, and the overlap must contain an honest one. So n−2f ≥ f+1, hence n ≥ 3f+1. A number like 2f+1 in {{< term "raft" "Raft" >}} is enough only because its nodes never lie. Here, instead of nodes, we count stake.

## Three runs

We run the program with `go run ./cmd/posbft`. First, all honest:

```
== all honest (seed-0)
proposer alice (byzantine=false), A=ce20c9 B=a1237f
after precommit: alice=ce20c9 bob=ce20c9 carol=ce20c9 dave=ce20c9 erin=ce20c9
```

The second line shows the proposer and two short hashes: `A` is the block an honest proposer gives everyone, and `B` is another block used only in the Byzantine scenarios. The last line says which block each node committed after the precommit round: everyone committed A.

The block is final the moment it is committed. That is {{< term "deterministic-finality" "deterministic finality" >}}, unlike the {{< term "probabilistic-finality" "probabilistic finality" >}} of proof of work. You do not wait for more blocks to pile on top, and a reorg is only possible if a third of the stake signs contradicting votes.

Second scenario: dave and erin (together 25% of the stake) are Byzantine. I tried seeds until one of them proposed (seed-5). Erin gives block A to alice and bob and B to carol. Both Byzantine validators do the same with votes: they vote A to alice and bob and B to carol. The three honest validators each vote for the block they saw:

```
proposer erin (byzantine=true), A=4444c9 B=7bc6a3
after precommit: alice=4444c9 bob=4444c9 carol=- dave=byz erin=byz
after gossip: alice=4444c9 bob=4444c9 carol=4444c9 dave=byz erin=byz
conflicting commits: false
evidence from carol: dave prevote 7bc6a3 vs 4444c9, check=<nil>
slash dave: stake 15 -> 8
evidence from carol: erin prevote 7bc6a3 vs 4444c9, check=<nil>
slash erin: stake 10 -> 5
evidence from carol: erin precommit 7bc6a3 vs 4444c9, check=<nil>
evidence from carol: dave precommit 7bc6a3 vs 4444c9, check=<nil>
```

(The order of the last two lines is not fixed and changes between runs. The program prints a few more lines that I left out for brevity.)

Line by line:

- **`after precommit`:** alice and bob committed block A, because A saw votes from alice (30) + bob (25) + the two Byzantine validators (25), 80 in total, and 80 is more than two thirds. Carol has not committed yet (`-`), because she saw only 45 stake for B and 55 for A, and neither is above two thirds.
- **`after gossip`:** the honest nodes forward what they saw to each other (gossip). Now carol sees the votes for A too and commits A. All three honest nodes hold the same block.
- **`conflicting commits: false`:** no two honest nodes committed different blocks. Safety held.
- **`evidence`:** carol now holds two signed prevotes from dave, one for B (which dave sent to her directly) and one for A (which arrived from alice and bob). The same is true for erin and for the precommits.
- **`slash`:** dave's stake went from 15 to 8 and erin's from 10 to 5.

B could not be committed for a simple reason: its share is at most 20 + 25 = 45, which is under two thirds.

Two contradicting signed votes from one validator are called {{< term "equivocation" "equivocation" >}}, and by themselves they are complete proof of cheating. The check, shortened:

```go
case a.Block == b.Block:
	return errors.New("same block: not conflicting")
case !s.VerifyVote(a) || !s.VerifyVote(b):
	return errors.New("bad signature")
```

The two votes must come from the same validator, be of the same type, have the same height and round, differ in block, and both carry a valid signature. The verifier holds only public keys, so anyone can check the evidence. The program also shows that two identical votes are not evidence (`same vote twice: same block: not conflicting`), and the package tests check that tampered evidence is rejected.

{{< term "slashing" "Slashing" >}} here burns half of the stake. That is my choice; real chains have their own penalties.

Third scenario: alice and erin (40% of the stake) are offline.

```
proposer carol (byzantine=false), A=098419 B=fb4012
after precommit: alice=off bob=- carol=- dave=- erin=off
conflicting commits: false
```

The online validators hold 60 stake, and 60 is not more than two thirds of 100. So nobody commits (`-`). The protocol is stuck but not wrong: liveness (progress) is gone, safety (agreement on one block) is not. In the terms of [CAP and PACELC, done right](/posts/ds-cap-pacelc/), consistency took priority over availability. A real protocol would try again after a timeout.

## Breaking the boundary

What if the Byzantine side goes beyond a third? With alice and dave Byzantine (45%), the same attack gives `bob=a1237f carol=ce20c9 erin=ce20c9` and `conflicting commits: true`: bob committed block B and the other two committed A. Safety broke. Still, carol holds evidence against both, so their cheating is provable, but the damage is done. A test runs every Byzantine subset and split over 4 seeds:

```
runs=972 conflicting(byz<1/3)=0 conflicting(byz>=1/3)=68 commits with >=1/3 offline=0
```

That is, in 972 runs, when the Byzantine stake was under a third, two conflicting blocks were never committed. When it was a third or more, 68 runs failed. And when a third or more was offline, nothing was ever committed.

## Ethereum, briefly

According to the Ethereum docs, as far as I understand them, it combines both ideas: a {{< term "fork-choice-rule" "fork choice rule" >}} (LMD-GHOST) picks the chain head, and Casper FFG finalizes epoch checkpoints once two thirds of the stake vote for them. I did not run an Ethereum client.

## What the safety stands on

- **A quorum is more than two thirds of the stake, not of the nodes.**
- **Safety assumes the Byzantine stake is under a third.** Above that, evidence only shows the cheaters after the fact.
- **The proposals in my model are unsigned.** A double proposal would be evidence too.
- **Slashing must arrive before the stake can be withdrawn.** As far as I know, that is why withdrawals in proof of stake are delayed.

## Exercise

Build a second round with locking: someone who precommitted A may only prevote A later, unless they see a more recent two-thirds prevote for something else.

## What's next

**Layer 2 and rollups: optimistic and ZK**: a final block is not a bigger block.
