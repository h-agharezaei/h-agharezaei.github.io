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

Until now every node lived in one demo process and forgot everything on exit. The Go code continues from [the mempool post](/posts/bc-mempool-fees/); [the Script interpreter](/posts/bc-bitcoin-script-rust/) was a side trip.

This post closes part one by fixing that: a {{< term "full-node" "full node" >}} binary `toynode`, blocks on disk, an API and a wallet CLI. The pieces come from [a CLI tool](/posts/go-cli-tool/), [an API with net/http](/posts/go-http-api-stdlib/) and [graceful shutdown](/posts/go-graceful-shutdown-workers/).

> Go 1.27 on macOS (arm64). Local example code, loopback only. The keys are derived from words like "miner": public, demo only. Temp paths are shown as `<tmp>`.

## One process per node

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

A goroutine re-dials every configured peer once a second, so a restarted peer is found again.

## Blocks on disk

Every block the node adds to its tree, side branches included, is appended to `blocks.dat`: a 4-byte length, the block as JSON, then `fsync`. Parents always come before children. On start, a torn last record from a crash is cut off, and every block goes through `AddBlock` again: headers and proof of work for all, transactions and signatures for the active chain, fork choice by chainwork:

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

Re-validating is slow for a big chain, but nothing on disk is trusted. A test cuts 5 bytes off the file and checks that the earlier blocks load. The mempool is not saved; as far as I know, Bitcoin Core writes its mempool to disk on shutdown.

## A JSON-RPC API on loopback

The API is {{< term "json-rpc" "JSON-RPC" >}} 2.0 over HTTP: `getblockcount`, `getblock`, `getbalance`, `listunspent`, `sendtx`, `getmempoolinfo`. It has no authentication, so the node refuses any non-loopback address:

```
$ toynode -data <tmp>/x -rpc 0.0.0.0:18109
rpc address 0.0.0.0:18109 is not a loopback IP
```

As far as I know, bitcoind protects its RPC with a cookie file or configured credentials.

`toywallet` holds the key. `send` asks the node for confirmed outputs, takes the largest until they cover amount plus fee, adds change, signs and calls `sendtx`. The node never sees the private key.

## Three nodes, one restart

`demo.sh` starts three processes: n1 mines every 2 seconds, n2 dials n1, n3 dials both. Then a payment, a `SIGTERM` to n2, a restart:

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

The wallet went through n3, the miner was n1, and n2 answered. n2's log:

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

Block 5 arrived after the signal and was still stored, because {{< term "graceful-shutdown" "graceful shutdown" >}} goes in order: stop the HTTP server (in-flight calls finish), stop the miner and dialer, close the node and wait for its goroutines, then sync and close the file. The restart is a tiny {{< term "initial-block-download" "initial block download" >}}: the handshake shows n1 has more work, n2 sends its locator and gets blocks 6 and 7.

## Part one in one table

| Post | What the node gained |
|---|---|
| [BC2](/posts/bc-hashes-blocks-chain/) | SHA-256, canonical header, linked blocks |
| [BC3](/posts/bc-merkle-trees-proofs/) | Merkle root, inclusion proofs |
| [BC4](/posts/bc-keys-ecdsa-addresses/) | secp256k1 keys, low-S signatures |
| [BC5](/posts/bc-transactions-utxo/) | UTXO transactions, fees, coinbase |
| [BC6](/posts/bc-account-model-nonce/) | account model comparison |
| [BC7](/posts/bc-proof-of-work-mining/) | proof of work, retarget, chainwork |
| [BC8](/posts/bc-p2p-gossip/) | TCP framing, gossip, sync |
| [BC9](/posts/bc-forks-reorgs/) | block tree, reorgs, undo data |
| [BC10](/posts/bc-mempool-fees/) | mempool, fee rate, RBF |
| [BC11](/posts/bc-bitcoin-script-rust/) | Script interpreter (Rust, separate) |
| BC12 | processes, disk, API, wallet |

## What a real node has that this one lacks

Without claiming a complete list:

- Headers-first sync from many peers in parallel; mine fetches whole blocks from one.
- Protection against {{< term "denial-of-service" "denial of service" >}}: connection limits, disconnecting misbehaving peers, bounded memory per peer.
- Script: outputs here name an address; BC11's interpreter is not wired in.
- Compact block relay (BIP-152), so a block reuses transactions peers already have.
- Coinbase maturity, median-time-past and future-timestamp rules.
- A real database for the UTXO set, pruning, peer discovery, fee estimation.

## Operational lessons

- Re-validate what you load; the disk is input too.
- `fsync` before saying a block is stored, and cut torn records on start.
- Unauthenticated RPC belongs on loopback.
- Shut down in order: inputs first, storage last.

## Exercise

1. Save the mempool on shutdown and re-add it on start.
2. Add an `-rpccookie` file with a random token and check it on every call.
3. Kill the miner with `SIGKILL` in a loop and check that every restart loads a valid chain.

## What's next

Part two starts below Solidity: **Inside the EVM: stack, memory, storage and gas with a tiny Rust interpreter**.
