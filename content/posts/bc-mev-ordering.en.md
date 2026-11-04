+++
date = '2026-11-27T18:00:00+03:30'
draft = false
title = 'MEV and transaction ordering'
description = 'MEV on a local anvil: a Go searcher sandwiches a pending swap, then a real minAmountOut and a deadline stop it, plus how anvil orders transactions.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "mev", "defi", "go-ethereum"]
cover = { image = "/images/covers/bc-mev-ordering.png", alt = "MEV and transaction ordering", hiddenInSingle = true }
+++

Imagine you are at an auction and want to buy something. A clerk puts the orders on a table and opens them in whatever order he likes. If someone can slip an order of his own onto the table before yours, and another one after yours, he can profit from your order without knowing anything you do not.

On a blockchain the clerk is whoever builds the block. In [AMMs and the constant-product formula](/posts/bc-amm-constant-product/) we saw the same 10,000 USDX swap pay 90.66 or 63.95 DEMO depending on what ran first. The block builder picks that order. The value someone can capture by choosing, inserting or leaving out transactions is called {{< term "mev" "MEV" >}} (maximal extractable value). [Gas optimization and upgradeable proxies](/posts/bc-gas-optimization-proxies/) was about what a transaction costs; this one is about when it runs.

In [The mempool, fees and transaction selection](/posts/bc-mempool-fees/) my own miner sorted by fee rate. Here I read a real node's {{< term "mempool" "pending pool" >}} from Go, with the client code of [Talking to Ethereum from Go with go-ethereum](/posts/bc-go-ethereum-client/). Everything runs against my own contracts on a local anvil, to see why the protections exist.

> Go 1.27, go-ethereum v1.17.10 (abigen v2 bindings), Foundry 1.8.7, macOS (arm64). `SimplePool` and `DemoToken` are copied unchanged from the AMM post, plus a deploy script: 1,000 DEMO / 100,000 USDX in the pool, 20,000 USDX for account 2. The keys are anvil's public test keys (account 1 is the victim). anvil listens on 127.0.0.1 only; `--rpc-url` is left out below. Transaction hashes differ on every run; the rest of the output is deterministic.

## Transactions that wait

A transaction you send does not go into a block at once. First it waits in the pool of pending transactions (the mempool), and anyone connected to a node can see it. The block builder later picks from that pool. That gap is what makes MEV possible.

To see the gap, after the deploy I turn off anvil's automine, so transactions wait until I build a block myself. Then I run the victim:

```
$ cast rpc evm_setAutomine false
$ go run ./cmd/mev victim
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 0.00, deadline +300s
victim: sent 0xf158a547
```

The victim wants to swap 10,000 USDX for DEMO. Before sending, it asked the pool "if I buy now, how many DEMO do I get?" (the quote) and the answer was 90.66. But it set two parameters of the swap carelessly:

- **`minAmountOut`:** the least DEMO the victim will accept. Here it is zero, meaning "whatever I get is fine".
- **`deadline`:** until when the swap is valid. Here 300 seconds after the latest block.

The pending transaction is public: anvil shows it with `txpool_content`, and on a real network it is gossiped between nodes.

## A searcher in Go

A {{< term "searcher" "searcher" >}} is a program that scans pending transactions for profit. Mine first reads the pending transactions. It ABI-decodes each transaction's calldata (the first 4 bytes are the function id, the rest are the arguments), and if it is a `swap` on my pool, it simulates. The simulation uses the pool's own `getAmountOut` through `eth_call`, so its arithmetic is exactly the contract's. (The code is simplified; the demo works with `*big.Int`.)

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

The idea of the loop: the searcher has 20,000 USDX. For each trial amount `s` (from 1,000 to 20,000) it walks three steps on simulated pool reserves. 1) It buys DEMO with `s`, and the price goes up. 2) The victim's swap runs; because the price is higher the victim gets less DEMO, and the victim's own buy pushes the price up further. 3) The searcher sells the DEMO it bought, at the now higher price. If in step 2 the victim would get less than its own `minAmountOut`, its transaction would revert and the sandwich is pointless, so that amount is skipped. Among the remaining amounts, the one with the most profit wins.

Then the searcher sends two transactions. The first is a {{< term "front-running" "front-run" >}} buy that pays a bigger tip than the victim, so it sits earlier in the block. The second is a back-run sell (with the next nonce) that pays a smaller tip, so it sits after the victim. Each carries its own `minAmountOut`.

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

The searcher's output:

- **First and second line:** it found the victim's transaction, which alone would get 90.66 DEMO.
- **Third line:** the best amount is the searcher's whole budget, 20,000 USDX. With it the victim gets only 63.95 DEMO and the expected profit is 3032.19 USDX.
- **Fourth line:** two transactions were sent. The `tip` is the reward that goes to the block builder, and `cap` is the ceiling on the total fee per unit of gas.

Then a block was mined, and `block` shows it in order. The order is the sandwich: the searcher's buy, the victim's swap, the searcher's sell. The searcher started with 20,000 USDX, bought 166.24 DEMO and sold it for 23,032.19 USDX. The victim got 63.95 DEMO.

This is called a {{< term "sandwich-attack" "sandwich" >}}: the victim's transaction sits between the searcher's two like the filling of a sandwich. The victim received about 26.7 DEMO less than its quote and the searcher took 3,032.19 USDX. Because `minAmountOut` was zero, only the searcher's budget limited its profit.

## See how the node orders

My first run came out the other way round: the victim first, and both searcher transactions reverted on their own minimum output. The cause was the node's ordering. The fee cap of all three transactions was 100 gwei. To test it directly, I sent three plain transfers from three accounts:

| tip | fee cap | position |
|---|---|---|
| 1 gwei | 50 gwei | 0 |
| 3 gwei | 30 gwei | 1 |
| 5 gwei | 10 gwei | 2 |

anvil 1.8.7 with `--order fees` (the default) sorted by `maxFeePerGas` (the cap), not by tip. So a transaction that pays a higher tip but sets a lower cap sat later. That is why the demo sets the cap to 50 gwei plus the tip. As far as I know, geth sorts by effective tip. The point is that the ordering policy belongs to the block builder and is not guaranteed anywhere; test it, do not assume it.

## Protection: a real minAmountOut

Now send the same victim with a real minimum. `-min-bps 50` means a tolerance of half a percent (50 basis points) below the quote:

```
$ go run ./cmd/mev victim -min-bps 50
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 90.20, deadline +300s
$ go run ./cmd/mev searcher
(trimmed)
searcher: no profitable front-run keeps the victim above minAmountOut, skip
```

That tolerance is a half-percent {{< term "slippage" "slippage" >}}. No front-run in 1,000 USDX steps both kept the victim above its minimum and earned back the pool's two 0.3% fees (one for the buy, one for the sell). The searcher skipped the attack.

If the searcher is careless (`-ignore-min`, which ignores the victim's minimum) and takes this block, it gets this:

```
0  searcher nonce 2 tip 3 cap 53 gwei status 1  20000.00 USDX -> 166.24 DEMO
1  victim   nonce 2 tip 2 cap 52 gwei status 0
2  searcher nonce 3 tip 1 cap 51 gwei status 0
searcher USDX change: -20000.00, DEMO held: 166.24
(trimmed)
$ cast run <victim tx hash>
    └─ ← [Revert] SlippageExceeded(63956986828671189740 [6.395e19], 90207783941074838592 [9.02e19])
```

`status 0` means the transaction reverted. The victim's swap reverted because it wanted at least 90.20 DEMO and the pool would give only about 63.96 (`SlippageExceeded(received, minimum)`). The back-run reverted too: the searcher wanted to sell its DEMO for at least 20,000 USDX, but since the victim's swap had not run and had not pushed the price up, the pool would give only 19,900.05 USDX (I computed that number from the pool formula). The result: the searcher paid 20,000 USDX and holds 166.24 DEMO that does not sell for 20,000. The victim only paid gas and kept its USDX.

## Protection: a deadline

A swap that waits may run much later, at a worse moment. A `deadline` prevents it: if the block time is past it, the swap reverts. I sent one with `-deadline 60`, moved anvil's clock forward ten minutes with `evm_increaseTime 600`, and mined a block:

```
0  victim   nonce 2 tip 2 cap 52 gwei status 0
    └─ ← [Revert] Expired()
(trimmed)
```

## Other protections (I did not run these here)

- **Private submission:** send the transaction straight to a block builder instead of the public pool. You trust the recipient.
- **Batch auction:** the orders of one interval settle at a single price, so their order inside the batch does not matter.
- **{{< term "commit-reveal" "Commit-reveal" >}}:** publish a hash of the order first and the content later, so nobody sees anything while it waits.
- **Builder and proposer separation:** as far as I know, on Ethereum many blocks are built by builders and the proposer picks through an auction ({{< term "proposer-builder-separation" "proposer-builder separation" >}}, often via MEV-Boost). That moves the power over ordering; it does not remove it.

## Not all MEV is harmful

If you saw only the bad side of the sandwich, the picture is incomplete. The back-run in the example above brought the pool's price back. {{< term "arbitrage" "Arbitrage" >}} between two pools does the same: if a token is pricier in one, a trader buys from the cheap one and sells in the dear one, which keeps DEX prices aligned. The {{< term "liquidation" "liquidations" >}} of [Lending, collateral and liquidation](/posts/bc-lending-liquidation/) are MEV too: the reward goes to whoever is first, and without them bad debt would grow.

## Before you sign a swap

- **Do not sign a swap with `minAmountOut = 0`.** Compute it from a fresh quote.
- **Set the deadline to a few minutes.**
- **Ordering is the block builder's policy.** Test it, do not assume it.

## Exercise

1. Add a second pool with a different price and write an arbitrage that brings the two prices together.
2. Find the largest front-run that keeps the victim above a tolerance of 1%, 0.5% and 0.1%. When does it pay?
3. Run anvil again with `--order fifo` and repeat the sandwich.

## What's next

**Proof of stake, BFT and finality**: after the order inside a block, who builds the block and when it becomes final.
