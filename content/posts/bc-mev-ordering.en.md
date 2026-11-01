+++
date = '2027-07-08T10:00:00+03:30'
draft = false
title = 'MEV and transaction ordering'
description = 'MEV on a local anvil: a Go searcher sandwiches a pending swap, then a real minAmountOut and a deadline stop it, plus how anvil orders transactions.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "mev", "defi", "go-ethereum"]
cover = { image = "/images/covers/bc-mev-ordering.png", alt = "MEV and transaction ordering", hiddenInSingle = true }
+++

[Gas optimization and upgradeable proxies](/posts/bc-gas-optimization-proxies/) was about what a transaction costs. This one is about when it runs. Whoever builds a block picks the order, and order changes results: in [AMMs and the constant-product formula](/posts/bc-amm-constant-product/) the same 10,000 USDX swap paid 90.66 or 63.95 DEMO depending on what ran first. The value someone can capture by choosing, inserting or leaving out transactions is called {{< term "mev" "MEV" >}} (maximal extractable value).

In [The mempool, fees and transaction selection](/posts/bc-mempool-fees/) my own miner sorted by fee rate. Here I read a real node's {{< term "mempool" "pending pool" >}} from Go, with the client code of [Talking to Ethereum from Go with go-ethereum](/posts/bc-go-ethereum-client/). Everything runs against my own contracts on a local anvil, to see why the protections exist.

> Go 1.27, go-ethereum v1.17.10 (abigen v2 bindings), Foundry 1.8.7, macOS (arm64). `SimplePool` and `DemoToken` are copied unchanged from the AMM post, plus a deploy script: 1,000 DEMO / 100,000 USDX in the pool, 20,000 USDX for account 2. The keys are anvil's public test keys (account 1 is the victim). anvil listens on 127.0.0.1 only; `--rpc-url` is left out below.

## Transactions that wait

After the deploy I turn off anvil's automine, so transactions wait until I mine:

```
$ cast rpc evm_setAutomine false
$ go run ./cmd/mev victim
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 0.00, deadline +300s
victim: sent 0xf158a547
```

The victim quotes 90.66 DEMO, then accepts anything. The pending transaction is public: anvil serves it via `txpool_content`; real networks gossip it between nodes.

## A searcher in Go

A {{< term "searcher" "searcher" >}} scans pending transactions for profit. Mine decodes the calldata with the ABI and simulates with the pool's own `getAmountOut` via `eth_call`, so the math is exactly the contract's (simplified; the demo uses `*big.Int`):

```go
var content struct {
	Pending map[common.Address]map[string]*types.Transaction `json:"pending"`
}
rc.CallContext(ctx, &content, "txpool_content")
args, _ := swapM.Inputs.Unpack(tx.Data()[4:]) // tokenIn, amountIn, minAmountOut, to, deadline

for s := step; s <= budget; s += step { // 1,000 USDX steps
	got := amountOut(s, rU, rD)                // 1) our buy
	v := amountOut(vIn, rU+s, rD-got)          // 2) the victim's buy
	if v < vMin { continue }                   // the victim would revert
	back := amountOut(got, rD-got-v, rU+s+vIn) // 3) our sell
	profit := back - s
}
```

Then it sends a {{< term "front-running" "front-run" >}} buy paying more than the victim and a back-run sell (next nonce) paying less, each with its own `minAmountOut`.

```
$ go run ./cmd/mev searcher
searcher: pending swap from victim: 10000.00 USDX in, minAmountOut 0.00, tip 2 gwei
searcher: victim alone would get 90.66 DEMO
searcher: best front-run 20000.00 USDX, victim would get 63.95 DEMO, expected profit 3032.19 USDX
searcher: sent front-run 0x4e0a3314 (tip 3, cap 53 gwei), back-run 0x0e111db4 (tip 1, cap 51 gwei)
$ cast rpc anvil_mine
$ go run ./cmd/mev block
block 13, base fee 208805657 wei, 3 txs
0  searcher nonce 2 tip 3 cap 53 gwei status 1  20000.00 USDX -> 166.24 DEMO
1  victim   nonce 2 tip 2 cap 52 gwei status 1  10000.00 USDX -> 63.95 DEMO
2  searcher nonce 3 tip 1 cap 51 gwei status 1  166.24 DEMO -> 23032.19 USDX
victim DEMO balance:   63.95
searcher USDX change: 3032.19, DEMO held: 0.00
```

A {{< term "sandwich-attack" "sandwich" >}}: the victim got 26.70 DEMO less and the searcher kept 3,032.19 USDX. With `minAmountOut = 0` only the budget limited the profit.

## Check how the node orders

My first run came out the other way: victim first, both searcher legs reverted on their own minimums. All three had a 100 gwei fee cap. Three plain transfers:

| tip | fee cap | position |
|---|---|---|
| 1 gwei | 50 gwei | 0 |
| 3 gwei | 30 gwei | 1 |
| 5 gwei | 10 gwei | 2 |

With the default `--order fees`, anvil 1.8.7 sorted by `maxFeePerGas`, not by the tip, so the demo sets cap = 50 gwei + tip. As I understand it, geth orders by effective tip instead. The ordering policy belongs to whoever builds the block.

## Protection: a real minAmountOut

```
$ go run ./cmd/mev victim -min-bps 50
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 90.20, deadline +300s
$ go run ./cmd/mev searcher
(trimmed)
searcher: no profitable front-run keeps the victim above minAmountOut, skip
```

With 0.5% {{< term "slippage" "slippage" >}} tolerance, no front-run in the 1,000 USDX steps both keeps the victim above its minimum and pays for the two 0.3% fees. A careless searcher (`-ignore-min`) gets this block:

```
0  searcher nonce 2 tip 3 cap 53 gwei status 1  20000.00 USDX -> 166.24 DEMO
1  victim   nonce 2 tip 2 cap 52 gwei status 0
2  searcher nonce 3 tip 1 cap 51 gwei status 0
searcher USDX change: -20000.00, DEMO held: 166.24
(trimmed)
$ cast run <victim tx hash>
    └─ ← [Revert] SlippageExceeded(63956986828671189740 [6.395e19], 90207783941074838592 [9.02e19])
```

The victim paid gas and kept its USDX. The searcher holds DEMO that would now sell for 19,900.05 USDX.

## Protection: a deadline

A swap that waits can run later, at a worse moment. I sent one with `-deadline 60`, moved anvil's clock with `evm_increaseTime 600` and mined:

```
0  victim   nonce 2 tip 2 cap 52 gwei status 0
    └─ ← [Revert] Expired()
(trimmed)
```

## Other protections (not run here)

- Private submission: send the transaction to a block builder, not the public pool. You trust the receiver.
- Batch auctions: orders collected over a period settle at one price, so order inside the batch does not matter.
- {{< term "commit-reveal" "Commit-reveal" >}}: publish a hash first, the content later.
- On Ethereum, as I understand it, many blocks come from builders that proposers pick by auction ({{< term "proposer-builder-separation" "proposer-builder separation" >}}, often through MEV-Boost). That moves ordering power; it does not remove it.

## Not all MEV hurts

The back-run moved the price back. {{< term "arbitrage" "Arbitrage" >}} between two pools does the same and keeps DEX prices in line. {{< term "liquidation" "Liquidations" >}} from [Lending, collateral and liquidation](/posts/bc-lending-liquidation/) are MEV too: the bonus goes to whoever is first, and without them bad debt grows.

## A few things to watch

- Never sign a swap with `minAmountOut = 0`; derive it from a fresh quote.
- Keep deadlines in minutes, not hours.
- Ordering is the block builder's policy. Test it, do not assume.

## Exercise

1. Add a second pool at another price and write the arbitrage that brings them together.
2. Find the largest front-run that keeps the victim above 1%, 0.5% and 0.1% tolerance. When does it pay?
3. Restart anvil with `--order fifo` and rerun the sandwich.

## What's next

Next post: **Proof of stake, BFT and finality**.
