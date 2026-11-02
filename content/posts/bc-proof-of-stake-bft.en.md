+++
date = '2027-07-09T10:00:00+03:30'
draft = false
title = 'Proof of stake, BFT and finality'
description = 'Proof of stake and BFT finality in Go: stake-weighted proposers, signed prevotes and precommits, a 2/3 quorum, and slashing for double-signing.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "proof-of-stake", "bft", "finality"]
cover = { image = "/images/covers/bc-proof-of-stake-bft.png", alt = "Proof of stake, BFT and finality", hiddenInSingle = true }
+++

The previous post, [MEV and transaction ordering](/posts/bc-mev-ordering/), asked who orders transactions in a block. This one asks who produces it, and when it becomes final.

In [Proof of work, difficulty and mining](/posts/bc-proof-of-work-mining/) a vote cost electricity. [Forks, reorgs and the heaviest-chain rule](/posts/bc-forks-reorgs/) showed the price: a block is never final. {{< term "proof-of-stake" "Proof of stake" >}} replaces burned energy with locked money. A {{< term "validator" "validator" >}} deposits stake, its vote weighs as much as its stake, and provable cheating destroys part of the deposit.

The voting is {{< term "byzantine-fault" "Byzantine fault" >}} tolerant consensus. In [Consensus and Raft](/posts/ds-consensus-raft/) nodes could crash but never lie; here some lie on purpose.

> Go 1.27 on macOS (arm64), local example code. The `wallet` package (secp256k1) is copied unchanged from the [small full node](/posts/bc-toy-node-go/) demo; keys come from names like "alice": public, demo only. This is a **teaching model** of one Tendermint-like round: no timeouts, round changes or locking, synchronous delivery. Not a production protocol.

## Who proposes

Validators: alice 30, bob 25, carol 20, dave 15, erin 10. Every node must pick the same proposer, so it is a function of a shared seed, height and round (shortened):

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

```
proposer counts over 10000 heights: alice(30)=2986 bob(25)=2538 carol(20)=1947 dave(15)=1535 erin(10)=994
```

Proportional to stake. The weak point is the seed: if it were the previous block hash, a proposer could try many block variants and publish one that makes it proposer again (grinding). As far as I know, Ethereum mixes a value revealed by each proposer into its seed (RANDAO), so the last proposer can only reveal or skip its slot.

## Two votes and a 2/3 quorum

The proposer sends a block; everyone signs a prevote for it; a validator that sees prevotes for one block from more than 2/3 of the stake signs a precommit for it (otherwise for nil); more than 2/3 of precommits commit the block.

```go
func (s *Set) Quorum(stake uint64) bool { return 3*stake > 2*s.Total() }
```

Why 2/3 and not a majority? Take n validators, f of them Byzantine. The f may stay silent, so a {{< term "quorum" "quorum" >}} must form from n−f. Two quorums overlap in at least 2(n−f)−n = n−2f validators, and the overlap must contain an honest one, who never votes for two blocks: n−2f ≥ f+1, so n ≥ 3f+1. {{< term "raft" "Raft" >}}'s 2f+1 works only because its nodes never lie. With stake, count stake instead of nodes.

## Three runs

`go run ./cmd/posbft`, all honest:

```
== all honest (seed-0)
proposer alice (byzantine=false), A=ce20c9 B=a1237f
after precommit: alice=ce20c9 bob=ce20c9 carol=ce20c9 dave=ce20c9 erin=ce20c9
```

The block is final the moment it is committed. That is {{< term "deterministic-finality" "deterministic finality" >}}, unlike the {{< term "probabilistic-finality" "probabilistic finality" >}} of proof of work: no confirmations to wait for, and no reorg unless a third of the stake signs contradicting votes.

Now dave and erin (25%) are Byzantine. I tried seeds until one of them proposed (seed-5). Erin sends block A to alice and bob, B to carol, and both vote A to alice and bob, B to carol:

```
proposer erin (byzantine=true), A=4444c9 B=7bc6a3
after precommit: alice=4444c9 bob=4444c9 carol=- dave=byz erin=byz
after gossip: alice=4444c9 bob=4444c9 carol=4444c9 dave=byz erin=byz
conflicting commits: false
evidence from carol: dave prevote 7bc6a3 vs 4444c9, check=<nil>
slash dave: stake 15 -> 8
evidence from carol: erin prevote 7bc6a3 vs 4444c9, check=<nil>
slash erin: stake 10 -> 5
evidence from carol: dave precommit 7bc6a3 vs 4444c9, check=<nil>
evidence from carol: erin precommit 7bc6a3 vs 4444c9, check=<nil>
```

B reaches at most 20+25 = 45. After gossip carol commits A and holds two signed votes from dave for the same height, round and type but different blocks. That is {{< term "equivocation" "equivocation" >}}, and the two votes are the whole proof:

```go
case a.Block == b.Block:
	return errors.New("same block: not conflicting")
case !s.VerifyVote(a) || !s.VerifyVote(b):
	return errors.New("bad signature")
```

The verifier holds only public keys, so anyone can check. {{< term "slashing" "Slashing" >}} here burns half the stake, my choice; real chains define their own penalties.

Finally alice and erin (40%) go offline:

```
proposer carol (byzantine=false), A=098419 B=fb4012
after precommit: alice=off bob=- carol=- dave=- erin=off
conflicting commits: false
```

60 is not more than 2/3 of 100: nothing commits. Liveness is lost, safety is not: in [CAP and PACELC](/posts/ds-cap-pacelc/) terms, consistency over availability. A real protocol would time out and retry.

## Breaking the bound

With alice and dave Byzantine (45%) the same attack gives `bob=a1237f carol=ce20c9 erin=ce20c9`, `conflicting commits: true`, though carol holds valid evidence against both. A test runs every Byzantine subset and split over 4 seeds:

```
runs=972 conflicting(byz<1/3)=0 conflicting(byz>=1/3)=68 commits with >=1/3 offline=0
```

## Ethereum, briefly

According to the Ethereum docs, as I understand them, it combines both: a {{< term "fork-choice-rule" "fork-choice rule" >}} (LMD-GHOST) picks the head, and Casper FFG finalizes epoch checkpoints once 2/3 of the stake votes for them. I ran no Ethereum client here.

## A few things to watch

- The quorum is more than 2/3 of stake, not of nodes.
- Safety assumes Byzantine stake under 1/3; above it, evidence still names the cheaters, but after the fact.
- My proposals are unsigned; a real double proposal is evidence too.
- Slashing needs the evidence before the cheater withdraws its stake; as far as I know, that is why proof-of-stake chains delay withdrawals.

## Exercise

Add a second round with locking: whoever precommitted A prevotes only A later, unless it sees a newer 2/3 prevote for something else.

## What's next

Next post: **Layer 2 and rollups: optimistic and ZK**.
