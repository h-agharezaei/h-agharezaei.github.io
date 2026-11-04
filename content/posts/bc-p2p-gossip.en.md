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


Until now our whole blockchain has lived inside one program. That program builds blocks, checks them, and keeps the one and only copy of the chain. A real blockchain does not work like that. Thousands of computers each keep their own copy, there is no central server, and nobody trusts anybody. So two questions come up right away. When Alice pays Bob on one computer, how does that payment reach all the others? And when a computer that was switched off comes back, how does it catch up?

The answer works much like a rumour among neighbours. Nobody announces the news to the whole town. You tell the few people you know, they tell the people they know, and within a short time everybody has heard it. In networking this is called **gossip**. The difference from a rumour is that every computer checks what it hears before it passes it on.

In the [previous post](/posts/bc-proof-of-work-mining/) we made building a block expensive. Here several separate nodes connect to each other over TCP and pass transactions and blocks among themselves. The socket side is the same as in [A TCP server and client from scratch](/posts/net-sockets-tcp-from-scratch/). What is new compared to [Service discovery and load balancing](/posts/ds-service-discovery-load-balancing/) is trust: there the servers were ours, here any peer might be lying, so every message is validated before it is passed on.

I took a copy of the previous post's module and added a `p2p` package. To keep things simple, all nodes run inside one process, each listening on `127.0.0.1` on a port the operating system picks.

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example and only uses loopback. The keys are derived from words like "alice", so they are public and only good for a demo.

## Nodes and peers

A few words first. Each computer that runs the blockchain program and keeps a copy of the chain is a **node**. The nodes a node is directly connected to are its **peers**. A network in which every member is both a client and a server, with nobody in charge, is called {{< term "peer-to-peer" "peer-to-peer" >}}, or P2P for short.

The core idea of this post fits in two sentences. Each node talks to only a few peers. Whatever new and valid thing it hears, it checks itself and then passes it on to its other peers.

To make this work we need three things: a way to send separate messages over TCP, a greeting at the start of each connection, and a way to stop messages from going round in circles forever. Let's take them in that order.

## Messages on a TCP connection

TCP gives us a stream of bytes, not separate messages. If I write two messages one after the other, the other side may read them in one chunk, or receive half of the first one now and the rest later. TCP only promises that the bytes arrive in order; where one message ends is our problem.

The usual solution is to write each message's length before it. The reader first reads the length, then reads exactly that many bytes. This is called {{< term "message-framing" "framing" >}}, and each message with its length is a frame. In our protocol a frame looks like this:

1. 4 bytes: the length of what follows, big-endian.
2. 1 byte: the message type.
3. The payload: the message itself.

We have four message types:

```go
const (
	MsgVersion   MsgType = 1 // handshake: who I am, which chain, how high
	MsgTx        MsgType = 2 // one transaction
	MsgBlock     MsgType = 3 // one block
	MsgGetBlocks MsgType = 4 // "send me your blocks from this height on"
)

const MaxFrame = 1 << 20
```

- `version` is the greeting at the start of a connection; more on it below.
- `tx` carries one transaction.
- `block` carries one block.
- `getblocks` means "send me your blocks starting from this height".

I wrote the payload in JSON so the demo stays readable. Bitcoin and Ethereum have their own binary encodings.

`MaxFrame` is 1 MiB, and it matters. The length at the start of a frame is just a number the other side has written. A malicious peer can claim the next message is 4 GB long. If we trust that number and allocate memory for it, one fake message can bring our node down. So `ReadMsg` rejects any length above `MaxFrame` before it allocates anything.

## The greeting: the handshake

When two nodes connect, each first sends a `version` message containing three things: its name, the hash of its genesis block, and the height of its chain.

- **The genesis hash** shows whether we are on the same chain at all. If two nodes have different first blocks, they are on two separate networks and have nothing to say to each other. A peer with a different genesis is disconnected.
- **The height** shows who is behind. If the peer's chain is longer than ours, we send it `getblocks` with our height plus one, meaning "send me what I am missing". One reply carries at most 500 blocks.

Until the greeting is done, the node accepts no other message; a peer that sends something else first is disconnected.

There is one more small but important detail. Writing to a socket can block. If the peer at the other end is slow, or reads nothing on purpose, our write waits. If that wait happened in the middle of the node's main work, one bad peer could freeze the whole node. So every peer gets its own writer goroutine, fed by a queue (a channel) of 256 messages. The node only puts messages into the queue and moves on. If a peer's queue fills up, that peer cannot keep up and is disconnected.

## Gossip and the seen-set

Now the main part. {{< term "gossip-protocol" "Gossip" >}} has one simple rule: when a node receives something new and valid, it sends it to every peer except the one it came from.

But this simple rule has a problem. Suppose A, B and C are connected in a triangle. C sends a transaction to A and B. A passes it to B, and B passes it to A. Now A has received the same transaction a second time. If it passed it on again, the message would go round the triangle forever.

The fix is a memory: each node keeps a set of the IDs of the transactions and the hashes of the blocks it has already handled. I call it the **seen-set**. If something is already in that set, the node drops it silently and passes nothing on:

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

Step by step:

1. If the transaction is in the seen-set, it is a duplicate copy. It is counted and dropped.
2. Otherwise it goes into the seen-set, so the next copy is recognised.
3. `checkTx` validates it: do its inputs exist in the {{< term "utxo" "UTXO" >}} set, are the signatures right, and so on. It also checks one more thing: the transaction must not spend an output that a **pending** transaction already spends. Pending transactions are the valid ones that are not in a block yet. Without this check, someone could send two transactions spending the same coin to two different nodes.
4. If it is valid, it goes into the pending list and `relay` sends it to every peer except the sender.

Notice the order: we validate first, then relay. If we passed things on before checking them, every node would help spread the attacker's garbage across the network.

Blocks take the same path, and are validated with the same `AddBlock` as before, with one difference: a peer that sends an invalid block is disconnected right away, but a peer that sends an invalid transaction is not. The reason is that an honest peer can send a transaction that is invalid from our point of view. For example, a block that spent that coin may have reached us a moment earlier than it reached the peer. An invalid block with valid {{< term "proof-of-work" "proof of work" >}}, on the other hand, is not an accident. Someone spent real hashes on building it.

Two other cases appear in the code. If a block arrives whose height is more than one above our tip, we are behind, and we ask the same peer for the missing blocks with `getblocks`. If a block arrives at a height we already have but with a different hash, it is a competing block. For now the node just logs it and ignores it. What to do with it is the subject of the next post.

## A run

`go run ./cmd/toychain gossip` tells a short story in four scenes:

1. Node A mines two blocks on its own, before anybody is connected to it.
2. B connects to A, then C to B, then A to C, so the three form a triangle (a ring).
3. Alice hands a payment of 30 coins to Bob to node C, and then A mines block 3.
4. Node D joins late and connects only to C.

Because the nodes run concurrently, the order of lines from different nodes can change from run to run. The hashes and counts are the same every time, because the block timestamps are fixed. Here is the full output of the first part:

```
== A mines 2 blocks alone
[A] mined block 1 0004060375af (bits 12, 5076 hashes, 1 txs), sent to 0 peers
[A] mined block 2 000d7c19dc57 (bits 12, 1480 hashes, 1 txs), sent to 0 peers
== ring A-B-C-A on loopback
[B] connected to A (its height 2, mine 0)
[A] connected to B (its height 0, mine 2)
[A] getblocks from 1 by B: sent 2 blocks
[B] block 1 0004060375af from A: valid, 1 txs, relayed to 0
[B] block 2 000d7c19dc57 from A: valid, 1 txs, relayed to 0
[C] connected to B (its height 2, mine 0)
[B] connected to C (its height 0, mine 2)
[B] getblocks from 1 by C: sent 2 blocks
[C] block 1 0004060375af from B: valid, 1 txs, relayed to 0
[C] block 2 000d7c19dc57 from B: valid, 1 txs, relayed to 0
[C] connected to A (its height 2, mine 2)
[A] connected to C (its height 2, mine 2)
== alice pays bob 30 through C
[C] tx ef4d0ece5dfd submitted locally, sent to 2 peers
[A] tx ef4d0ece5dfd from C: valid, relayed to 1
[B] tx ef4d0ece5dfd from C: valid, relayed to 1
== A mines block 3
[A] mined block 3 0004a6f9de1f (bits 12, 37 hashes, 2 txs), sent to 2 peers
[C] block 3 0004a6f9de1f from A: valid, 2 txs, relayed to 1
[B] block 3 0004a6f9de1f from A: valid, 2 txs, relayed to 1
== D joins late, connects to C only
[D] connected to C (its height 3, mine 0)
[C] connected to D (its height 0, mine 3)
[C] getblocks from 1 by D: sent 3 blocks
[D] block 1 0004060375af from C: valid, 1 txs, relayed to 0
[D] block 2 000d7c19dc57 from C: valid, 1 txs, relayed to 0
[D] block 3 0004a6f9de1f from C: valid, 2 txs, relayed to 0
D: tip 0004a6f9de1f, bob 30, pending 0
```

Scene by scene:

- **A alone:** A mines blocks 1 and 2 and sends them to 0 peers, because nobody is connected yet. Each block has one transaction, the coinbase, the transaction with which the miner pays itself the block reward.
- **Building the ring:** B connects to A. In the greeting, each one says its height: A is at 2, B at 0. B is behind, so it asks for blocks from height 1, and A sends 2 blocks. B validates each one itself. `relayed to 0` means B had no other peer yet to pass them to. C then syncs from B the same way. When A connects to C at the end, both are at height 2 and nothing needs to be exchanged.
- **The payment:** C gets the transaction locally and sends it to its 2 peers, A and B. Each of them validates it and passes it to its only other peer: A to B, B to A. Those two copies are the duplicates that the seen-set catches. They do not appear in the log, because a duplicate is dropped silently, but we will see them in the stats at the end.
- **Block 3:** A mines a block with 2 transactions: the coinbase and Alice's payment. B and C each receive it from A and pass it to each other. Again, each one receives one duplicate copy.
- **D arrives late:** D connects only to C, sees it is 3 blocks behind, and fetches all 3. It does not trust C: it validates every block itself, from proof of work to signatures. Only then does it accept that Bob has 30 coins. `pending 0` means the payment is no longer waiting, because it is now inside block 3.

## A peer that lies

So far everyone has been honest. Now Mallory connects to B. She does not run a real node; the demo speaks the protocol to B by hand: a `version`, and then a single block 4. She tries twice. The first time the block was never mined. The second time it is properly mined, but its coinbase pays her 1000 coins, while the reward in our chain is 50:

```
== mallory connects to B with bad blocks
[B] connected to mallory (its height 3, mine 3)
mallory: got version, sending unmined block
[B] REJECT block from mallory: block 4: hash does not meet the difficulty target
[B] disconnect mallory: sent an invalid block
mallory: connection: EOF
[B] connected to mallory (its height 3, mine 3)
mallory: got version, sending mined (4258 hashes), coinbase 1000
[B] REJECT block from mallory: block 4: tx 0: coinbase pays more than reward + fees or has the wrong height
[B] disconnect mallory: sent an invalid block
mallory: connection: EOF
A: height 3, tx in 2, block in 0, duplicates 1, relayed 1, rejected 0
B: height 3, tx in 2, block in 6, duplicates 2, relayed 2, rejected 2
C: height 3, tx in 0, block in 4, duplicates 1, relayed 1, rejected 0
D: height 3, tx in 0, block in 3, duplicates 0, relayed 0, rejected 0
```

- **The first attempt:** B checks the block's hash and sees it does not start with enough zero bits. The block is rejected and Mallory is disconnected. `connection: EOF` is what Mallory sees: B has hung up.
- **The second attempt:** this time the proof of work is right; Mallory spent 4258 hashes on it. But B goes further and checks the transactions too. The coinbase pays more than the reward plus fees, so the block is rejected again and Mallory is disconnected again.

The second attempt is the most important point of this section. **Proof of work does not make a block valid; it only makes it expensive.** A node checks every rule of the chain, whatever amount of work is behind a block.

The last four lines are each node's counters, and with them we can count the duplicates we did not see in the log:

- **A:** received the transaction twice, once from C and once from B, so 1 duplicate. It passed it on once (to B). It received no blocks, because it built all of them itself.
- **B:** received the transaction twice too (from C and A). It received 6 blocks: 2 during sync, block 3 from A and its copy from C, and Mallory's 2 blocks. Its 2 duplicates are the second copy of the transaction and the second copy of block 3, and its 2 rejections are Mallory's blocks.
- **C:** received no transaction from the network, because it submitted it itself. It received 4 blocks: 2 during sync, and block 3 from A and from B, one of which was a duplicate.
- **D:** exactly 3 blocks, with no duplicates, because it had only one peer.

`go test -race ./...` repeats these scenarios as tests, together with a test that a peer on a different genesis is disconnected, and passes. `-race` turns on Go's race detector, which matters for code that has several goroutines per peer.

## How real networks do it

My nodes are far simpler than real ones. Three differences are worth knowing:

- **Finding peers.** I did not implement {{< term "peer-discovery" "peer discovery" >}}; my nodes are given addresses by hand. As far as I know, a new Bitcoin node finds its first peers through DNS seeds, domain names that resolve to the addresses of active nodes, and then learns more addresses from its peers. According to the devp2p specs, Ethereum clients use a Kademlia-style discovery protocol over UDP (discv4 and discv5).
- **Announce first, send later.** My nodes push whole blocks to every peer, even if the peer already has them; that is why we saw duplicates. In Bitcoin a node first announces only the hash with an `inv` message, and the peer asks for the data itself with `getdata` only if it does not have it. Bitcoin also syncs headers first and fetches block bodies after that.
- **The eclipse attack.** Peer discovery is also an attack surface. If all of a node's peers belong to an attacker, the node is "eclipsed": it only sees what the attacker shows it, for example a chain in which a payment never happened.

## Where a gossip node breaks

- **Limit every number that comes from the network before you trust it.** We saw this with frame length: an unchecked length means unbounded memory allocation. The same is true for the reply to a request: our `getblocks` sends at most 500 blocks, so one request cannot make the node send its whole chain at once.
- **Validate before you relay.** Gossip is an amplifier. If an invalid message passes through you, you hand it to all your peers and help the attacker spread it.
- **Do not let a slow peer hold up the node.** Writing to a socket can block. With a separate writer and a bounded queue per peer, a slow peer only harms itself: its queue fills up and it is disconnected.
- **The seen-set must not grow forever.** In my code it is a map that only gets bigger; on a real network, with millions of transactions, it would eventually eat all the memory. As far as I know, Bitcoin Core uses a rolling {{< term "bloom-filter" "Bloom filter" >}} for this: a compact data structure that only remembers the most recent items and, in exchange, can occasionally give a wrong "I have seen it".

## Exercise

1. Replace pushing whole blocks with `inv`/`getdata`: announce only the hash, and send the block only when it is asked for.
2. Add a ban score: disconnect a peer after three rejected transactions, and refuse its address for one minute.
3. Change `getblocks` so that headers come first, and check their proof of work before asking for the block bodies.

## What's next

The next post is "Forks, reorgs and the heaviest-chain rule". Right now our nodes ignore a competing block at the same height; there we keep a tree of blocks instead of a single line, and let the chain with the most work win.
