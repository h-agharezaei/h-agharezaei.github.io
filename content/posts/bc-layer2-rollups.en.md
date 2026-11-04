+++
date = '2026-11-29T18:00:00+03:30'
draft = false
title = 'Layer 2 and rollups: optimistic and ZK'
description = 'Rollups in Go and Solidity: a toy optimistic rollup with a Merkle state root, a fraud proof that slashes a lying sequencer, and measured L1 gas.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "solidity", "layer-2", "rollup", "foundry"]
cover = { image = "/images/covers/bc-layer2-rollups.png", alt = "Layer 2 and rollups: optimistic and ZK", hiddenInSingle = true }
+++

Imagine a shop with a single till and one rule: every receipt must also be added up from scratch by a thousand other people. However fast the cashier is, the shop runs at the speed of the slowest of those thousand. Ethereum works much like this. Every node re-executes every transaction, and each block has a gas limit. So the capacity of the main chain (people call it L1) is limited, however fast your own server is. [Proof of stake, BFT and finality](/posts/bc-proof-of-stake-bft/) made blocks final, but not bigger.

The common answer today is to move most of the work off the main chain. A {{< term "layer-2" "Layer 2" >}} is a layer that does the work elsewhere. The most common design is a {{< term "rollup" "rollup" >}}. Picture an accountant who adds up the transactions of hundreds of people in his own ledger. Then he pins two things on L1's public board: the list of the transactions, and the final number of his ledger. L1 adds nothing up itself. It is only the board and the judge. If the accountant pinned a wrong number, anyone who has the list can prove it.

In this post I build a toy version of this design from earlier pieces: the tree from [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/), the token from [Tokens: ERC-20 and ERC-721](/posts/bc-erc20-erc721/), and reading logs as in [Events and building an indexer](/posts/bc-event-indexer-go/).

> Go 1.27 with go-ethereum v1.17.10, Foundry 1.8.7, solc 0.8.38, macOS (arm64), anvil on `127.0.0.1:8550` with its default hardfork. Local example code. Keys are anvil's public test keys. The Merkle code is copied unchanged from the Merkle post's demo. A **teaching model**, not a production rollup.

## The toy rollup

First, what is the "ledger"? In my model the layer-2 state is 8 accounts, each with a balance (a `uint64`). At the start account 0 holds 1000 units and account 1 holds 500; the rest hold zero.

A transaction is just a transfer, and it takes exactly 10 bytes: one byte for the sender (`from`), one for the receiver (`to`) and 8 bytes for the amount. An invalid transaction (for example, the sender has too little balance) is skipped and does not spoil the whole batch.

To describe the whole ledger with one short number, I reuse the Merkle tree from the earlier post. Each leaf is one account (`index || balance`), and its root, the {{< term "state-root" "state root" >}}, is a 32-byte fingerprint of all 8 balances. Move a single coin and the root changes.

Our accountant is called the {{< term "sequencer" "sequencer" >}}. It is a Go program that collects transactions into a **batch**, executes them itself, and sends the batch to a contract called `RollupInbox` on L1. The batch bytes travel as {{< term "calldata" "calldata" >}}. Calldata is the input part of every transaction: it stays in the chain's history and anyone can read it, but it is not saved in the contract's storage. The contract keeps only the hash of the batch and the root the sequencer claims:

```solidity
function appendBatch(bytes calldata txs, bytes32 stateRoot) external {
    if (msg.sender != sequencer) revert NotSequencer();
    if (slashed) revert SequencerSlashed();
    if (txs.length == 0 || txs.length % TX_SIZE != 0) revert BadLength();
    bytes32 dataHash = keccak256(txs);
    batches.push(Batch(dataHash, stateRoot, uint64(block.timestamp)));
    emit BatchAppended(batches.length - 1, stateRoot, dataHash);
}
```

Notice one thing: the contract does not check the root. Nothing is executed. This is what makes it an {{< term "optimistic-rollup" "optimistic rollup" >}}. The contract assumes the root is right unless someone proves otherwise within a **challenge window**. Ours is one hour.

## Catching a lying sequencer

What if the sequencer lies? Say the accountant adds a million coins to account 7 in the final number, with no transaction to justify it. There must be a way for an honest observer to prove this to L1.

That proof is called a {{< term "fraud-proof" "fraud proof" >}}. In its simplest form the challenger sends two things: the bytes of that batch, and the balances of all 8 accounts before the batch. The contract first checks that both are real: the hash of the bytes must match what it stored, and the root of the balances must match the root of the previous batch. Then it executes the whole batch itself and compares the correct root with the claimed one:

```solidity
if (keccak256(txs) != b.dataHash) revert WrongData();
uint64[ACCOUNTS] memory bal = pre;
if (stateRoot(bal) != prevRoot) revert WrongPreState();
execute(bal, txs);
bytes32 correct = stateRoot(bal);
if (correct == b.stateRoot) revert RootIsCorrect();
while (batches.length > i) batches.pop(); // roll back
slashed = true;
// half the bond is sent to the challenger (trimmed)
```

If the roots differ, that batch (and every batch after it) is removed from the list and the sequencer is punished. The punishment comes out of the **bond**: the sequencer put 1 ETH down as a deposit when the contract was created. By the code, half of the bond goes to the challenger and the other half stays locked in the contract, which means it is effectively burned.

Let me run it. `go run ./cmd/rollup run` shows a sequencer and a verifier one after the other. The sequencer posts two batches. The first is honest. In the second the transactions are fine, but before computing the root the sequencer adds a million coins to account 7. The verifier is another Go program that knows only two things: the initial state and what is on L1. It reads the `BatchAppended` logs, fetches each transaction, decodes the calldata, executes the batch itself and compares the result with the claimed root.

```
RollupInbox 0x5FbDB2315678afecb367f032d93F642f64180aa3, genesis root 4c5dbac8, bond 1 ETH
sequencer: batch of 4 txs (3 valid), 40 bytes, root fb844e73, block 2, gas 116627
sequencer: next batch lies: account 7 gets 1000000 out of thin air
sequencer: batch of 2 txs (2 valid), 20 bytes, root 090abc11, block 3, gas 99330
verifier: batch 0 claimed fb844e73, re-executed fb844e73 ok
verifier: batch 1 claimed 090abc11, re-executed 0ff4589b MISMATCH -> challenge
verifier: challenge accepted, block 4, gas 134540
batchCount=1 slashed=true bond=0 
sequencer posts again: SequencerSlashed()
after +0s: batch 0 final = false
after +3600s: batch 0 final = true
```

(Each hash is printed as its first 4 bytes only. The contract address is the one a fresh anvil gives to the first deployment from account 0.)

Line by line:

- **Line 1:** the contract is deployed. `genesis root` is the root of the ledger at the start and `bond 1 ETH` is the sequencer's deposit.
- **Line 2:** the first batch has four transactions but only three are valid. The fourth is from account 5, which has no balance, so it was skipped. Four 10-byte transactions make 40 bytes. Posting it cost 116,627 gas.
- **Lines 3 and 4:** the sequencer lies on purpose. The second batch has two valid transactions, but the root it sends (`090abc11`) includes the made-up million coins.
- **Line 5:** the verifier re-executed batch 0 and got the claimed root: `ok`.
- **Line 6:** for batch 1 it got `0ff4589b`, not `090abc11`. `MISMATCH` means the roots disagree, and the verifier challenges.
- **Line 7:** the contract accepted the challenge.
- **Line 8:** `batchCount=1` means the false batch was removed and only batch 0 is left. `slashed=true` and `bond=0` mean the bond was taken.
- **Line 9:** the punished sequencer tries to post again, and the contract refuses with `SequencerSlashed()`.
- **Last two lines:** batch 0 was fine, but right after posting it is not final yet. I moved anvil's clock forward by 3600 seconds so the challenge window passed, and now it is final.

A note on line 6: Go and Solidity both compute the root. If their trees differed, the contract would have rejected even the honest balances (`WrongPreState`). The challenge being accepted means both build the same tree. The forge tests cover the other cases: challenging an honest batch, challenging too late and a fake pre-state all fail.

All of this leans on one hidden condition, called {{< term "data-availability" "data availability" >}}. The verifier could re-execute the batch because its bytes were on L1. If only roots stayed on L1, nobody could re-execute anything and the fraud would go unseen.

**Real fraud proofs differ**, as I understand the published designs (I ran none of them): sending a whole batch and the whole state to L1 does not scale. Systems such as Arbitrum and the OP Stack bisect the disputed execution interactively, again and again, until the two sides disagree on a single instruction. L1 executes only that one step, with Merkle proofs for the state it touches.

## The gas cost

Now the main question: is this really cheaper? `go run ./cmd/rollup gas` measures it. First it sends N `DemoToken` transfers directly on L1 (the recipients already hold DEMO). Then it posts one batch of N L2 transfers to `RollupInbox`. The numbers are `gasUsed` from the receipts:

```
    N L1 transfers gas     per tx one batch post gas     per tx
    1            35223      35223              99306      99306
   10           352206      35220             100101      10010
  100          3522108      35221             107803       1078
  500         17610612      35221             142140        284
```

Let me read the columns. The two in the middle are N separate transfers on L1: each costs about 35,220 gas, so the total climbs in a straight line. The last two are one batch: the total is nearly flat and grows only a little, so the share per transaction drops fast as N grows.

For N=1 the batch costs more (99,306 against 35,223), because storing a batch has a fixed overhead. But each extra transfer adds only about 86 gas to the batch. Most of that is the price of calldata. According to the Ethereum docs, a non-zero byte costs 16 gas and a zero byte costs 4. At N=500 each transaction costs 284 gas, against 35,221.

Read these numbers with some care:

- My L2 transactions carry no signatures. With signatures each would be 65 bytes larger.
- The cost of executing off-chain is not counted.
- As far as I know, real rollups mostly post compressed data as EIP-4844 blobs. I used plain calldata.

## ZK rollups

In an optimistic rollup we assume everything is right and wait for a challenger. A {{< term "zk-rollup" "ZK rollup" >}} takes the other road: with each batch the sequencer posts a {{< term "validity-proof" "validity proof" >}}, a mathematical proof that the new root really follows from the old one. L1 verifies the proof before accepting the root, so no challenge window is needed. The price is that producing the proof is expensive. [Zero-knowledge proof basics in Rust](/posts/bc-zero-knowledge-rust/) builds a small proof by hand. I wrote no ZK rollup code here.

## Withdrawals

To take money out of a rollup back to L1, you must prove your balance on L1 against a root (with a Merkle proof). In an optimistic rollup that root must first survive the challenge window. As far as I know, major ones use about seven days, which is why their withdrawals are slow. In a ZK rollup you wait for the next verified proof.

## Where the toy model breaks

- My transactions are unsigned. So re-execution cannot stop a sequencer that invents transfers, because nobody can show that the account owner did not ask for them. Real rollups verify user signatures during execution.
- Optimistic security needs at least one honest verifier who is online during every window and re-executes the batches.
- A single sequencer can still censor a transaction or order them in its own favour.

## Exercise

1. Add `deposit()` on L1 and a withdrawal that pays out only against a final root, with a Merkle proof of the balance.
2. Change the sequencer so it withholds the calldata (posts only the root). What can the verifier still do?

## What's next

**Bridges and cross-chain messaging**: L1 can judge a rollup because it holds the data; two independent chains cannot.
