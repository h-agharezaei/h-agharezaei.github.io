+++
date = '2027-07-11T10:00:00+03:30'
draft = false
title = 'Bridges and cross-chain messaging'
description = 'Cross-chain bridge in Go and Solidity: lock-and-mint between two anvil chains, 2-of-3 ecrecover signatures, replay checks, stolen keys, rate limits.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "solidity", "bridge", "foundry", "security"]
cover = { image = "/images/covers/bc-bridges-cross-chain.png", alt = "Bridges and cross-chain messaging", hiddenInSingle = true }
+++

In [Layer 2 and rollups: optimistic and ZK](/posts/bc-layer2-rollups/) the L1 contract could check the rollup itself: the data was on L1. Two independent chains cannot do that. Chain B has no idea what happened on chain A unless someone tells it, and a {{< term "bridge" "bridge" >}} is mostly the question of whom B believes.

I built the simplest common design, {{< term "lock-and-mint" "lock-and-mint" >}}, between two local chains. It reuses replay protection from [The account model, nonces and replay protection](/posts/bc-account-model-nonce/), signatures from [Keys, ECDSA signatures and addresses on secp256k1](/posts/bc-keys-ecdsa-addresses/) and confirmations from [Events and building an indexer](/posts/bc-event-indexer-go/).

> Go 1.27 with go-ethereum v1.17.10, Foundry 1.8.7, solc 0.8.38, macOS (arm64). Two anvils: A on `127.0.0.1:8550` (chain id 31337) and B on `127.0.0.1:8551` (chain id 31338). The Go module is a copy of last post's, keeping its small go-ethereum helper. Keys are anvil's public test keys, plus toy keys like `0xA1` in the tests. Teaching code, not audited.

## Lock here, mint there

`BridgeLock` on A takes DemoToken (from the tokens post) and emits `Deposit(nonce, from, recipient, amount)`. `BridgeMint` on B mints `wDEMO` for that deposit, but only with signatures from 2 of 3 {{< term "relayer" "relayers" >}}: a {{< term "multisig" "multisig" >}} enforced by the contract. Burning `wDEMO` on B emits `Withdrawal`, and the same set signs a release on A.

Every relayer signs a digest that names both ends:

```solidity
struct Message {
    uint256 srcChainId; address srcContract;
    uint256 dstChainId; address dstContract;
    uint256 nonce; address recipient; uint256 amount;
}

function digest(Message calldata m) public pure returns (bytes32) {
    return keccak256(abi.encode(keccak256("BC29_BRIDGE_V1"), m));
}
```

The contract recovers each signer with {{< term "ecrecover" "ecrecover" >}} (loop body, shortened):

```solidity
if (uint256(s) > HALF_N) revert BadSignature(); // reject the malleable twin
address signer = ecrecover(d, v, r, s);
if (signer == address(0) || signer <= last) revert BadSignature(); // sorted: no double counting
last = signer;
if (isRelayer[signer]) valid++;
// after the loop:
if (valid < threshold) revert NotEnoughSignatures(valid, threshold);
```

`mint` also checks the source and destination chain ids and contracts against its own, and marks the deposit nonce as used.

## The relayer

The Go relayer polls `Deposit` logs and acts only once they are 2 blocks deep. It computes the digest itself; a relayer that asked the destination contract what to sign would sign whatever that contract said:

```go
safe := head - w.Confirmations
q.FromBlock, q.ToBlock = new(big.Int).SetUint64(w.next), new(big.Int).SetUint64(safe)
confirmed, err = w.Chain.FilterLogs(ctx, q)
w.next = safe + 1
```

One process plays all three relayers (anvil accounts 5-7); r7 is "offline" for the deposit. `go run ./cmd/bridge`:

```
chain A id 31337, chain B id 31338
A: DemoToken 0x5FbDB231 BridgeLock 0xe7f1725E
B: BridgeMint 0x5FbDB231 wDEMO 0xa16E02E8
user locks 250 DEMO on A in block 6
relayer poll A: head 6, confirmed 0, waiting 1
(two more blocks on A)
relayer poll A: head 8, confirmed 1, waiting 0
  deposit 31337 -> 31338 nonce 1 amount 250e18 (block 6), digest matches contract: true
  r5+r6 signed, mint on B in block 2, gas 147740
user wDEMO on B: 250
replay on B: AlreadyProcessed()
same message on A: WrongRoute()
user burns 100 wDEMO on B in block 3
relayer poll B (head 5): withdrawal 31338 -> 31337 nonce 1 amount 100e18, r6+r7 signed, release on A in block 9
user DEMO on A: 850, locked on A: 150, wDEMO supply on B: 150, backed: true
```

Look at the addresses: DemoToken on A and BridgeMint on B are both `0x5FbDB231...`, because the same deployer used nonce 0 on both chains. A contract address does not identify a chain, which is why the {{< term "chain-id" "chain id" >}} is in the signed message. The replay of the same signed message on B fails on the nonce; sending it to A fails on the route. That is the {{< term "replay-attack" "replay" >}} protection from the nonce post, applied across chains.

The invariant is the last line: tokens locked on A equal `wDEMO` on B.

## When the relayer keys are stolen

The signatures are the bridge. A Foundry test gives an attacker relayer keys 1 and 2 and signs a deposit that never happened:

```
$ forge test -vv
[PASS] test_BurnAndRelease() (gas: 547423)
[PASS] test_CompromisedThresholdMintsUnbacked() (gas: 428178)
Logs:
  wDEMO supply: 900.000000000000000000
  DEMO locked : 0.000000000000000000
[PASS] test_HigherThresholdStopsTwoKeys() (gas: 253767)
[PASS] test_MintWithTwoOfThree() (gas: 344897)
[PASS] test_OneSignatureOrDuplicateNotEnough() (gas: 270604)
[PASS] test_ReplayRejected() (gas: 365543)
[PASS] test_WrongChainRejected() (gas: 278001)
(trimmed)
```

900 `wDEMO` backed by nothing. Every check passed, because from the contract's view the message is valid. As far as I know, several of the largest thefts in crypto were bridges whose validator or relayer keys were compromised. The [Binance hack write-up](/posts/binance-hack-hot-wallet-2026/) has the same lesson from another angle: no key leaked there, yet the signing system signed what the attacker asked.

## Limiting the damage

The same test continues with the mitigations I built in:

- **Cap per period**: `BridgeMint` mints at most 1000 per day ({{< term "rate-limiting" "rate limiting" >}}). The next forged 200 reverts with `RateLimited(1100e18, 1000e18)`.
- **Pause**: a guardian can stop minting; the forged message then reverts with `Paused()`. The guardian key is itself a target.
- **Higher threshold**: with 3 of 5, two stolen keys give `NotEnoughSignatures(2, 3)`. That helps only if the keys sit with independent operators and machines.

The stronger model removes the trusted signers: B runs a {{< term "light-client" "light client" >}} of A and verifies A's consensus and a Merkle proof of the deposit, or a ZK proof of the same. I did not build either; as I understand it, the cost is gas and complexity, and it is only as safe as the source chain's finality.

## A few things to watch

- Sign over source and destination chain ids and contracts, plus a nonce. A contract address alone is not unique across chains.
- Wait for confirmations before signing; a reorged deposit means minted tokens with nothing locked.
- Require sorted, distinct signers and reject high-`s` signatures.
- Check that locked equals minted, and alert when it does not.

## Exercise

1. Add a per-transfer cap in `BridgeLock.release` too.
2. Reorg chain A after a deposit is signed with zero confirmations. What does the invariant say?

## What's next

Next post: **Zero-knowledge proof basics in Rust**.
