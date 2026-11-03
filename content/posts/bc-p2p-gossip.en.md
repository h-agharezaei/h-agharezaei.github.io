+++
date = '2026-11-09T18:00:00+03:30'
draft = false
title = 'P2P networking and gossip between nodes'
description = 'P2P gossip in Go: a length-prefixed TCP protocol on loopback, a seen-set against loops, a late node syncing blocks and an invalid block rejected.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "p2p", "gossip", "tcp"]
cover = { image = "/images/covers/bc-p2p-gossip.png", alt = "P2P networking and gossip between nodes", hiddenInSingle = true }
+++

A blockchain is many nodes with no server in the middle, each checking everything it hears. Our blocks got expensive to make in the [previous post](/posts/bc-proof-of-work-mining/), but they still live in one process. This post connects `toychain` nodes over TCP.

The socket side is the same as in [A TCP server and client from scratch](/posts/net-sockets-tcp-from-scratch/). The difference from [Service discovery and load balancing](/posts/ds-service-discovery-load-balancing/) is trust: here no peer is trusted, and every message is validated before it is passed on.

I copied last post's module and added a package `p2p`. All nodes run in one process on `127.0.0.1`, on ports the OS picks.

> Go 1.27 on macOS (arm64). Local example code, loopback only. The keys are derived from words like "alice": public, demo only.

## The wire format

A {{< term "peer-to-peer" "peer-to-peer" >}} protocol needs {{< term "message-framing" "framing" >}} on top of the TCP byte stream. Each frame is a 4-byte big-endian length, a type byte, then the payload:

```go
const (
	MsgVersion   MsgType = 1 // handshake: who I am, which chain, how high
	MsgTx        MsgType = 2 // one transaction
	MsgBlock     MsgType = 3 // one block
	MsgGetBlocks MsgType = 4 // "send me your blocks from this height on"
)

const MaxFrame = 1 << 20
```

The payload is JSON so the demo stays readable; Bitcoin and Ethereum use their own binary encodings. `ReadMsg` refuses a length above `MaxFrame` before allocating, because a peer could claim 4 GB.

Every connection starts with `version` in both directions: name, genesis hash and height. A peer on another genesis is dropped. If the peer is higher, we ask it for `getblocks` from our height + 1. Each peer has one writer goroutine fed by a bounded channel; if it fills, the peer is dropped.

## Gossip and the seen-set

{{< term "gossip-protocol" "Gossip" >}} is simple: when a node gets something new and valid, it sends it to every peer except the one it came from. In a network with cycles that would loop forever, so each node keeps a set of transaction IDs and block hashes it already handled:

```go
func (n *Node) handleTx(from *peer, tx chain.Tx) {
	n.mu.Lock()
	defer n.mu.Unlock()
	n.stats.TxIn++
	id := tx.ID()
	if n.seen[id] {
		n.stats.Dups++
		return
	}
	n.seen[id] = true
	if _, err := n.checkTx(tx); err != nil {
		n.stats.Rejected++
		n.logf("tx %s from %s rejected: %v", id.Short(), from.label(), err)
		return
	}
	n.pending[id] = tx
	k := n.relay(from, MsgTx, tx)
	n.stats.Relayed += k
	n.logf("tx %s from %s: valid, relayed to %d", id.Short(), from.label(), k)
}
```

`checkTx` validates against the UTXO set and rejects a transaction that spends the same output as one already pending. Blocks go the same way through `AddBlock`, with one difference: a peer that sends an invalid block is disconnected. A bad transaction may be an honest race; a bad block with valid {{< term "proof-of-work" "proof of work" >}} is not an accident.

## A run

`go run ./cmd/toychain gossip`: node A mines two blocks alone, then B, C and A connect in a ring. Alice pays Bob through C, A mines block 3, then D joins late and talks only to C (log lightly trimmed):

```
== ring A-B-C-A on loopback
[A] connected to B (its height 0, mine 2)
[B] connected to A (its height 2, mine 0)
[A] getblocks from 1 by B: sent 2 blocks
[B] block 1 0004060375af from A: valid, 1 txs, relayed to 0
[B] block 2 000d7c19dc57 from A: valid, 1 txs, relayed to 0
...
== alice pays bob 30 through C
[C] tx ef4d0ece5dfd submitted locally, sent to 2 peers
[B] tx ef4d0ece5dfd from C: valid, relayed to 1
[A] tx ef4d0ece5dfd from C: valid, relayed to 1
== A mines block 3
[A] mined block 3 0004a6f9de1f (bits 12, 37 hashes, 2 txs), sent to 2 peers
[B] block 3 0004a6f9de1f from A: valid, 2 txs, relayed to 1
[C] block 3 0004a6f9de1f from A: valid, 2 txs, relayed to 1
== D joins late, connects to C only
[D] connected to C (its height 3, mine 0)
[C] connected to D (its height 0, mine 3)
[C] getblocks from 1 by D: sent 3 blocks
[D] block 1 0004060375af from C: valid, 1 txs, relayed to 0
[D] block 2 000d7c19dc57 from C: valid, 1 txs, relayed to 0
[D] block 3 0004a6f9de1f from C: valid, 2 txs, relayed to 0
D: tip 0004a6f9de1f, bob 30, pending 0
```

A and B each relayed the transaction to the other; the seen-set dropped the second copy (`duplicates 1` on A below). D checked all three blocks itself, proof of work and signatures included, before it believed Bob had 30.

## A peer that lies

Then Mallory speaks the protocol by hand to B: a `version`, then a block. First one that was never mined, then one with valid proof of work and a coinbase of 1000:

```
mallory: got version, sending unmined block
[B] REJECT block from mallory: block 4: hash does not meet the difficulty target
[B] disconnect mallory: sent an invalid block
mallory: connection: EOF
mallory: got version, sending mined (4258 hashes), coinbase 1000
[B] REJECT block from mallory: block 4: tx 0: coinbase pays more than reward + fees or has the wrong height
[B] disconnect mallory: sent an invalid block
mallory: connection: EOF
A: height 3, tx in 2, block in 0, duplicates 1, relayed 1, rejected 0
B: height 3, tx in 2, block in 6, duplicates 2, relayed 2, rejected 2
C: height 3, tx in 0, block in 4, duplicates 1, relayed 1, rejected 0
D: height 3, tx in 0, block in 3, duplicates 0, relayed 0, rejected 0
```

The second block cost real hashes and still failed: proof of work does not make a block valid, it only makes it costly. Tests also check that a peer on another genesis is dropped; `go test -race ./...` passes.

## How real networks do it

I did not implement discovery: my nodes get addresses by hand. As far as I know, a new Bitcoin node finds its first peers through DNS seeds, hostnames that resolve to addresses of active nodes, and then learns more addresses from peers. Ethereum clients use a Kademlia-style discovery protocol over UDP, described in the devp2p specs (discv4, discv5). Bitcoin also announces with `inv` (just hashes) and sends data on `getdata`, and syncs headers first; my nodes push whole blocks. {{< term "peer-discovery" "Peer discovery" >}} is also where eclipse attacks live: a node whose every peer is the attacker sees only the attacker's chain.

## Where a gossip node breaks

- Cap every length from the network before allocating, and limit what one request may return.
- Validate before you relay; otherwise you amplify garbage for the attacker.
- Never let a slow peer block the node: one writer per peer, bounded queue.
- My seen-set grows forever; as far as I know, Bitcoin Core uses rolling Bloom filters for this.

## Exercise

1. Replace full-block push with `inv`/`getdata`: announce hashes, send blocks only on request.
2. Add a ban score: drop a peer after three rejected transactions, and keep its address out for a minute.
3. Make `getblocks` send headers first and verify their proof of work before asking for bodies.

## What's next

Next post: **Forks, reorgs and the heaviest-chain rule**. Our nodes ignore competing blocks for now; next we keep a block tree and let the chain with the most work win.
