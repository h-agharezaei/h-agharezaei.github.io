+++
date = '2026-11-13T18:00:00+03:30'
draft = false
title = 'Part one wrap-up: a small full node in Go'
description = 'A small full node in Go: separate processes on loopback, blocks on disk re-validated at start, a JSON-RPC API, a wallet CLI and graceful shutdown.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "full-node", "json-rpc", "bitcoin"]
cover = { image = "/images/covers/bc-toy-node-go.png", alt = "Part one wrap-up: a small full node in Go", hiddenInSingle = true }
+++

Every node we have built so far had the same weakness: it lived inside a demo program, and when that program ended, the node forgot everything. The blocks, the UTXO set, the mempool were all in memory. A real node is a long-running program. It is stopped and started again, it sometimes crashes, and every time it has to come back with its chain intact.

This post closes part one of the series by fixing that. The result is a small {{< term "full-node" "full node" >}}: a program that keeps the whole chain itself, checks every block itself, and trusts nobody. It is a separate binary called `toynode`, which keeps its blocks on disk, answers questions through an API, and has a separate command-line wallet next to it.

The Go code continues from [The mempool, fees and transaction selection](/posts/bc-mempool-fees/); [the Script interpreter](/posts/bc-bitcoin-script-rust/) in the previous post was a side trip in Rust and is not part of this node. The new pieces come from earlier posts outside this series: [Building a CLI tool in Go](/posts/go-cli-tool/), [Building an API with net/http in Go](/posts/go-http-api-stdlib/) and [Graceful shutdown of workers in Go](/posts/go-graceful-shutdown-workers/).

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example and only uses loopback. The keys are derived from words like "miner", so they are public and only good for a demo. Temporary paths are shown as `<tmp>`.

## One process per node

Until now, all nodes lived in one process and talked to each other through Go function calls and loopback sockets. Now each node is its own operating-system process, started from the command line with flags:

```
$ toynode -h
Usage of <tmp>/bin/toynode:
  -data string
    	directory for blocks.dat (required)
  -interval duration
    	time between mined blocks (default 2s)
  -listen string
    	P2P address (default "127.0.0.1:19001")
  -mine
    	mine blocks
  -miner string
    	demo key name that receives block rewards (default "miner")
  -name string
    	name used in logs and the handshake (default "node")
  -peers string
    	comma-separated P2P addresses to keep connected to
  -rpc string
    	JSON-RPC address (loopback only) (default "127.0.0.1:18001")
```

- `-data` is the directory where the node keeps its blocks. It is required, because a node without a disk is exactly what we are trying to get rid of.
- `-listen` is the address for P2P connections to other nodes, and `-rpc` is the address of the API, which comes later.
- `-peers` is a list of nodes this node should stay connected to.
- `-mine` turns mining on; `-interval` sets how often a block is mined, and `-miner` whose demo key gets the reward.

One small but important piece: a goroutine tries every address in `-peers` once a second, and dials the ones it is not connected to. So if a peer is restarted, the connection comes back on its own, without anyone doing anything.

## Blocks on disk

How do we keep blocks on disk? The simplest possible way: one file, `blocks.dat`, to which we only append. Each record is the same framing we used on the network: a 4-byte length, then the block as JSON. After each write the node calls `fsync`, which tells the operating system to really write the data to the disk, not just keep it in its memory. Only then does the node consider the block stored.

Every block the node adds to its tree is written, side branches included. Because a block can only enter the tree after its parent, parents always come before children in the file.

When the node starts, two things happen:

1. **A torn record is cut off.** If the node crashed in the middle of writing a block, the last record in the file is incomplete. `store.Open` reads every complete record, and if the last one is incomplete, it truncates the file back to the end of the last complete record.
2. **Everything is checked again.** Each block read from disk goes through the same `AddBlock` as a block from the network: headers and proof of work for every block, transactions and signatures for the active chain, and fork choice by chainwork.

```go
for _, b := range blocks {
	if b.Header.Height == 0 {
		continue // genesis is built in
	}
	if _, err := n.chain.AddBlock(b); err != nil {
		return err
	}
}
```

The genesis block is built into the code, so it is skipped. Everything else goes through `AddBlock` again.

Why check again what we wrote ourselves? Because the disk is input too. The file may have been damaged, a bug may have written something wrong, or someone may have edited it. Re-validating is slow for a big chain, but the node trusts nothing it has not checked itself. A test cuts 5 bytes off the end of the file, as if a crash happened in the middle of a write, and checks that the earlier blocks still load and that writing can continue after them.

The mempool is not saved; after a restart it is empty. As far as I know, Bitcoin Core writes its mempool to disk when it shuts down and reads it back on start.

## A JSON-RPC API on loopback

A node on its own is not much use; other programs have to be able to ask it things. For that it has an API in {{< term "json-rpc" "JSON-RPC" >}} 2.0 over HTTP. JSON-RPC is a simple convention: each request is a JSON object with a method name and its parameters, and each response is a JSON object with `result` or `error`. The methods are:

- `getblockcount`: the height of the tip.
- `getblock`: a block at a given height.
- `getbalance` and `listunspent`: an address's balance and unspent outputs.
- `sendtx`: hand a signed transaction to the node.
- `getmempoolinfo`: the state of the mempool.

This API has no authentication. Anyone who can reach it can, for example, send transactions to the node. So the node refuses to listen on any address that is not loopback:

```
$ toynode -data <tmp>/x -rpc 0.0.0.0:18109
rpc address 0.0.0.0:18109 is not a loopback IP
```

As far as I know, bitcoind protects its RPC with a cookie file or with credentials set in its configuration.

The private key does not live in the node; it lives in a separate program, `toywallet`. Its `send` command does this:

1. It asks the node for the sender's confirmed outputs (`listunspent`).
2. It picks them from the largest down, until they cover the amount plus the fee.
3. Whatever is left over goes back to the sender as a new output, the **change**.
4. It signs the transaction and hands it to the node with `sendtx`.

The node only sees the signed transaction. It never sees the private key.

## Three nodes, one restart

`demo.sh` puts all of this together. It starts three processes on loopback:

- **n1** mines a block every 2 seconds.
- **n2** connects to n1.
- **n3** connects to both.

Then the miner pays Bob 20 coins, n2 is stopped with `SIGTERM` (the normal "please shut down" signal), the network goes on for a while without it, and then n2 is started again. Block hashes, timestamps and the exact heights depend on timing, so they are different on every run:

```
== heights
{"jsonrpc":"2.0","id":1,"result":3}
{"jsonrpc":"2.0","id":1,"result":3}
{"jsonrpc":"2.0","id":1,"result":3}
== wallet
miner 0xb7885750: 150
sent a1ee6a59dee4: 1 inputs, 20 to 0xd94f176c, fee 1, 233 bytes
bob 0xd94f176c: 20
bob 0xd94f176c: 20
{"jsonrpc":"2.0","id":2,"result":{"height":4,"hash":"0000359c9480ba929389cca89523c1967ec04f8a1ac2e78190ad31f398cefd25","prev":"0003f6b32dc59ccac63d9416036d5b5de9c241b3d48b71f8b1f6cb946ea2ef07","time":1793564462,"bits":12,"txids":["3f4cb1ba34d5822b628abfb47aad11a6b376e22600327143c0d1b1ed43d2b2bf","a1ee6a59dee410ccacc13ce9482db04bf2d46a2276b85fd227564a89e95df997"]}}
== stop n2 (SIGTERM)
== heights while n2 is down
{"jsonrpc":"2.0","id":1,"result":7}
{"jsonrpc":"2.0","id":1,"result":7}
== restart n2
== heights
{"jsonrpc":"2.0","id":1,"result":9}
{"jsonrpc":"2.0","id":1,"result":9}
{"jsonrpc":"2.0","id":1,"result":9}
bob 0xd94f176c: 20
```

- **`== heights`:** after 7 seconds all three nodes are at height 3. Each line is the raw JSON-RPC response to `getblockcount`.
- **`== wallet`:** the wallet asks n2 for the miner's balance: 150, the rewards of 3 blocks. It then sends the payment through **n3**: one input, 20 coins to Bob, a fee of 1, 233 bytes. Three seconds later both n1 and n2 report that Bob has 20. The payment went into n3, gossip carried it to n1, n1 put it in a block, and the block reached n2.
- **The `getblock` line:** block 4, as n2 sees it. It has two transaction IDs: the coinbase, and the miner's payment to Bob, whose ID starts with `a1ee6a59dee4`, the same as in the wallet line.
- **`== heights while n2 is down`:** n2 is stopped, and only n1 and n3 answer. The chain has moved on to height 7.
- **After the restart:** all three are at the same height again, and n2 still knows that Bob has 20.

The more interesting part is n2's own log, around the stop and the restart:

```
[n2] block 4 0000359c9480 from n1: extended, 2 txs, relayed to 1
[n2] signal received, shutting down
[n2] block 5 000a8de373da from n1: extended, 1 txs, relayed to 1
[n2] stopped at height 5
[n2] loaded 5 blocks from disk, re-validated, tip 5 000a8de373da
[n2] p2p 127.0.0.1:19102, rpc 127.0.0.1:18102, mining false
[n2] connected to n1 (its height 7 work 32768, mine 5 work 24576)
[n2] block 6 00015ccd8617 from n1: extended, 1 txs, relayed to 0
[n2] block 7 00087e9fdc04 from n1: extended, 1 txs, relayed to 0
```

- **`signal received, shutting down`:** n2 got the `SIGTERM`.
- **`block 5 ... extended`:** block 5 arrived **after** the signal, and was still added and stored. That is not a bug; it is what an orderly shutdown looks like, explained below.
- **`stopped at height 5`:** n2 exited cleanly, with block 5 on disk.
- **`loaded 5 blocks from disk, re-validated`:** on restart, n2 read its 5 blocks from the file and checked every one of them again.
- **`connected to n1 (its height 7 ..., mine 5 ...)`:** in the handshake n1 says it has more work, so n2 sends its block locator, as in the reorg post.
- **Blocks 6 and 7:** n2 receives what it missed while it was down, and is back in step.

Why could block 5 still get in? Because a {{< term "graceful-shutdown" "graceful shutdown" >}} goes in a deliberate order:

1. Stop the HTTP server. Requests that are already in progress are allowed to finish.
2. Stop the miner and the dialer, and wait for them, so no new blocks come from us.
3. Close the node: drop the peers and wait for their goroutines to finish.
4. Only at the end, sync the file and close it.

Between the signal and step 3, the node is still connected to its peers, so block 5 could arrive and be stored. The rule behind this order is: stop the inputs first, and close the storage last. If the order were reversed, a block could arrive after the file was closed and be lost.

The restart itself is a tiny {{< term "initial-block-download" "initial block download" >}}, the process by which a node that is behind, or brand new, fetches and checks the chain from its peers. Here it was only two blocks, but the mechanism is the same.

## Part one in one table

This is where part one ends. Each post added one piece to this node:

| Post | What the node gained |
|---|---|
| [Hashes, blocks and the chain](/posts/bc-hashes-blocks-chain/) | SHA-256, a canonical header, linked blocks |
| [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/) | Merkle root, inclusion proofs |
| [Keys, ECDSA signatures and addresses](/posts/bc-keys-ecdsa-addresses/) | secp256k1 keys, low-S signatures |
| [Transactions and the UTXO model](/posts/bc-transactions-utxo/) | UTXO transactions, fees, coinbase |
| [The account model, nonces and replay protection](/posts/bc-account-model-nonce/) | a comparison with the account model |
| [Proof of work, difficulty and mining](/posts/bc-proof-of-work-mining/) | proof of work, retarget, chainwork |
| [P2P networking and gossip](/posts/bc-p2p-gossip/) | TCP framing, gossip, sync |
| [Forks, reorgs and the heaviest-chain rule](/posts/bc-forks-reorgs/) | block tree, reorgs, undo data |
| [The mempool, fees and transaction selection](/posts/bc-mempool-fees/) | mempool, fee rate, RBF |
| [Bitcoin Script](/posts/bc-bitcoin-script-rust/) | a Script interpreter (in Rust, separate) |
| This post | processes, disk, API, wallet |

## What a real node has that this one lacks

This is not a complete list, but it shows how far a real node is from this one:

- **Faster sync.** A real Bitcoin node syncs headers first and then fetches block bodies from many peers in parallel. Mine fetches whole blocks from a single peer.
- **Defence against {{< term "denial-of-service" "denial of service" >}}:** limits on the number of connections, disconnecting peers that misbehave, and bounded memory per peer.
- **Script.** The outputs here still just name an address; the interpreter from the Script post is not wired into this node.
- **Compact block relay** (BIP-152), so that a new block can be sent using transactions the peer already has in its mempool, instead of sending them all again.
- **More consensus rules:** coinbase maturity, the median-time-past rule, and limits on timestamps in the future.
- **A real database** for the UTXO set, pruning of old blocks, peer discovery, and fee estimation.

## Operational lessons

- **Re-validate what you load.** The disk is input too, just like the network. A node that trusts its own file trusts whoever, or whatever bug, wrote it.
- **`fsync` before you say a block is stored, and cut off torn records on start.** Until `fsync` returns, the data may only be in the operating system's memory, and a power cut would lose it. A crash in the middle of a write leaves half a record, and the node must recognise it and remove it.
- **An API without authentication belongs on loopback.** Even on a home network, an open RPC port means anyone on that network can send commands to your node.
- **Shut down in order: inputs first, storage last.** That is why block 5 in the demo was not lost.

## Exercise

1. Save the mempool on shutdown and add it back on start.
2. Add an `-rpccookie` file containing a random token, and check that token on every call.
3. Kill the miner with `SIGKILL` in a loop, and check that every restart loads a valid chain.

## What's next

Part two of the series goes one level below Solidity, and starts with "Inside the EVM: stack, memory, storage and gas with a tiny Rust interpreter". After a chain that only moves coins, we look at a chain that runs programs.
