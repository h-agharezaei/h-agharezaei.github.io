+++
date = '2027-07-10T10:00:00+03:30'
draft = false
title = 'Layer 2 and rollups: optimistic and ZK'
description = 'Rollups in Go and Solidity: a toy optimistic rollup with a Merkle state root, a fraud proof that slashes a lying sequencer, and measured L1 gas.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "solidity", "layer-2", "rollup", "foundry"]
cover = { image = "/images/covers/bc-layer2-rollups.png", alt = "Layer 2 and rollups: optimistic and ZK", hiddenInSingle = true }
+++

The previous post, [Proof of stake, BFT and finality](/posts/bc-proof-of-stake-bft/), made blocks final, not bigger. Every node re-executes every transaction and a block has a gas limit, so an L1 like Ethereum has limited throughput however fast your server is.

A {{< term "layer-2" "Layer 2" >}} moves execution elsewhere and keeps L1 as judge. The common design is a {{< term "rollup" "rollup" >}}: execute transactions off-chain, then post the transaction data and the resulting state commitment to an L1 contract. I built a toy one from earlier pieces: the tree from [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/), the token from [Tokens: ERC-20 and ERC-721](/posts/bc-erc20-erc721/), logs as in [Events and building an indexer](/posts/bc-event-indexer-go/).

> Go 1.27 with go-ethereum v1.17.10, Foundry 1.8.7, solc 0.8.38, macOS (arm64), anvil on `127.0.0.1:8550` with its default hardfork. Local example code. Keys are anvil's public test keys. The Merkle code is copied read-only from the BC3 demo. A **teaching model**, not a production rollup.

## The toy rollup

L2 state: 8 accounts with `uint64` balances. A transaction is 10 bytes: `from`, `to`, an 8-byte amount. Invalid ones are skipped, never reverted. The {{< term "state-root" "state root" >}} is BC3's Merkle root over 8 leaves `index || balance`.

The {{< term "sequencer" "sequencer" >}}, a Go program, executes a batch and posts it to `RollupInbox` on L1. The batch travels as {{< term "calldata" "calldata" >}}; the contract stores only its hash and the claimed root:

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

Nobody checks the root here: an {{< term "optimistic-rollup" "optimistic rollup" >}} assumes it correct unless someone proves otherwise within a challenge window (1 hour here).

## Catching a lying sequencer

A {{< term "fraud-proof" "fraud proof" >}} in its simplest form: the challenger sends the batch bytes and the full pre-state; the contract checks both against what it stored, re-executes the whole batch, and compares:

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

The sequencer posted a 1 ETH bond. The Go verifier knows only the genesis state and L1: it reads `BatchAppended` logs, fetches each transaction, decodes the calldata and re-executes. `go run ./cmd/rollup run`, where the second batch gives account 7 a million coins:

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

Go and Solidity agree on the tree: otherwise the honest pre-state would have failed `WrongPreState`. Forge tests cover the rest: honest batches, late challenges and fake pre-states all fail.

This works only because of {{< term "data-availability" "data availability" >}}: with only roots on L1, nobody could re-execute.

**Real fraud proofs differ**, as I understand the published designs (I ran none): a whole batch and state on L1 does not scale. Systems such as Arbitrum and the OP Stack bisect the disputed execution interactively until the sides disagree on one instruction; L1 executes only that step, with Merkle proofs for the state it touches.

## Gas: N transfers on L1 vs one batch

`go run ./cmd/rollup gas` sends N `DemoToken` transfers on L1 (recipients already hold DEMO), then posts one batch of N L2 transfers. `gasUsed` from the receipts:

```
    N L1 transfers gas     per tx one batch post gas     per tx
    1            35223      35223              99306      99306
   10           352206      35220             100101      10010
  100          3522108      35221             107803       1078
  500         17610612      35221             142140        284
```

For one transfer the batch costs more: storing it is fixed overhead. Each extra transfer adds about 86 gas, mostly calldata (according to the Ethereum docs, 16 gas per non-zero byte, 4 per zero byte). Caveats: my L2 transactions carry no signatures (65 more bytes each), off-chain execution is not counted, and real rollups, as far as I know, mostly post compressed data as EIP-4844 blobs. I used plain calldata.

## ZK rollups

A {{< term "zk-rollup" "ZK rollup" >}} posts a {{< term "validity-proof" "validity proof" >}} with each batch: a proof that the new root really follows from the old one. L1 verifies it before accepting the root: no challenge window, but proving is expensive. [Zero-knowledge proof basics in Rust](/posts/bc-zero-knowledge-rust/) builds a small proof by hand; I wrote no ZK rollup code here.

## Withdrawals

Leaving a rollup means proving your L2 balance on L1 against a root. In an optimistic rollup that root must survive the window first; as far as I know, major ones use about seven days. In a ZK rollup you wait for the next verified proof.

## A few things to watch

- My transactions are unsigned, so an honest re-execution cannot stop a sequencer inventing transfers. Real rollups verify user signatures during execution.
- Optimistic security needs at least one honest verifier online during every window.
- One sequencer can still censor or reorder.

## Exercise

1. Add `deposit()` on L1 and a withdrawal that pays out only against a final root, with a Merkle proof of the balance.
2. Make the sequencer withhold calldata (post only the root). What can the verifier still do?

## What's next

Next post: **Bridges and cross-chain messaging**.
