+++
date = '2026-11-30T18:00:00+03:30'
draft = false
title = 'Bridges and cross-chain messaging'
description = 'Cross-chain bridge in Go and Solidity: lock-and-mint between two anvil chains, 2-of-3 ecrecover signatures, replay checks, stolen keys, rate limits.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "solidity", "bridge", "foundry", "security"]
cover = { image = "/images/covers/bc-bridges-cross-chain.png", alt = "Bridges and cross-chain messaging", hiddenInSingle = true }
+++

Imagine you walk into a casino with cash. The cashier takes your 1,000, puts it in a safe, and hands you a 1,000 chip that is good only inside this casino. When you bring the chip back, the cashier tears it up and returns the real money. As long as the safe holds as much cash as there are chips in circulation, everything is fine.

A {{< term "bridge" "bridge" >}} does exactly this between two blockchains. But it has a serious problem. Chain B has no idea what happened on chain A unless someone tells it. So the main question of every bridge is: whom does B believe? In [Layer 2 and rollups: optimistic and ZK](/posts/bc-layer2-rollups/) the L1 contract could check the rollup itself, because the data was on L1. Two independent chains cannot do that.

The simplest common design is called {{< term "lock-and-mint" "lock-and-mint" >}}, the casino above. I built it between two local chains. It reuses pieces from earlier posts: replay protection from [The account model, nonces and replay protection](/posts/bc-account-model-nonce/), signatures from [Keys, ECDSA signatures and addresses on secp256k1](/posts/bc-keys-ecdsa-addresses/) and confirmations from [Events and building an indexer](/posts/bc-event-indexer-go/).

> Go 1.27 with go-ethereum v1.17.10, Foundry 1.8.7, solc 0.8.38, macOS (arm64). Two anvils: A on `127.0.0.1:8550` (chain id 31337) and B on `127.0.0.1:8551` (chain id 31338). The Go module is a copy of the last post's, keeping its small go-ethereum helper. Keys are anvil's public test keys, plus toy keys like `0xA1` in the tests. Teaching code, not audited.

## Lock here, mint there

On chain A there is a contract called `BridgeLock` (the safe). Someone gives it DemoToken (the token from the tokens post), and it emits the event `Deposit(nonce, from, recipient, amount)`, meaning "this much was deposited".

On chain B there is a contract called `BridgeMint` (the chip printer). It creates `wDEMO` for each deposit, but only when someone brings proof that the deposit really happened on A. What is the proof? Signatures from 2 of 3 {{< term "relayer" "relayers" >}}. A relayer is a program that watches deposits on A and signs the message for B. The "2 of 3" rule is a {{< term "multisig" "multisig" >}} that the contract itself enforces.

The way back works the same. If someone burns `wDEMO` on B, a `Withdrawal` event is emitted and the same group of relayers signs a release of the original tokens on A.

Every relayer signs a digest (a 32-byte summary of the message). The digest names both ends of the route, so a signature is valid for one route only:

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

The message says: from which chain and contract, to which chain and contract, with which unique number (`nonce`), how much, and for whom.

The contract finds the signer of each signature with {{< term "ecrecover" "ecrecover" >}}. Given the digest and a signature, ecrecover gives back the address that signed. This is the loop body (shortened):

```solidity
if (uint256(s) > HALF_N) revert BadSignature(); // reject the malleable twin
address signer = ecrecover(d, v, r, s);
if (signer == address(0) || signer <= last) revert BadSignature(); // sorted: no double counting
last = signer;
if (isRelayer[signer]) valid++;
// after the loop:
if (valid < threshold) revert NotEnoughSignatures(valid, threshold);
```

Line by line:

- **Line 1:** every ECDSA signature has a "twin" with a different `s` that verifies the same message. The contract accepts only the one with the small `s`, so a signature cannot take two shapes.
- **Lines 2 and 3:** the signer is recovered. Signatures must be sorted by address (`signer <= last` is rejected). That stops the same relayer from being counted twice.
- **Line 4:** only signatures from known relayers are counted.
- **After the loop:** if fewer than the threshold (2 here) valid signatures are present, the transaction reverts.

`mint` also compares the source and destination chain ids and contracts of the message with its own, and marks the deposit nonce as used.

## The relayer

Our relayer is a Go program. It reads `Deposit` events from A's logs, but acts only once the deposit is at least 2 blocks deep. The reason is that recent blocks can be dropped in a reorg ([Forks, reorgs and the heaviest-chain rule](/posts/bc-forks-reorgs/)). If a relayer signs a deposit that later disappears, `wDEMO` exists and nothing is locked.

Another point: the relayer computes the digest itself. A relayer that asked the destination contract what to sign would sign whatever that contract said:

```go
safe := head - w.Confirmations
q.FromBlock, q.ToBlock = new(big.Int).SetUint64(w.next), new(big.Int).SetUint64(safe)
confirmed, err = w.Chain.FilterLogs(ctx, q)
w.next = safe + 1
```

Each time the code reads only up to block `head - 2`, and remembers where it stopped (`w.next`).

To keep things simple, one process plays all three relayers (anvil accounts 5 to 7, named r5, r6 and r7). For the deposit, r7 is "offline". I run it with `go run ./cmd/bridge`. The program first deploys the contracts on both chains. Then a user locks 250 DEMO on A, the relayers see it, and 250 `wDEMO` is minted on B. Then it submits the same message again to see it rejected. At the end the user burns 100 `wDEMO` and the original tokens are released on A.

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

Line by line:

- **First three lines:** the two chain ids and the shortened contract addresses.
- **`user locks 250 DEMO on A in block 6`:** the user locked 250 tokens. The block number only shows how many transactions A had before.
- **First `relayer poll A`:** the deposit is in the newest block (`head 6`), so no block sits on top of it yet. `confirmed 0, waiting 1` means there is no confirmed deposit and one is waiting. The relayer waits.
- **`(two more blocks on A)`:** the program mines two empty blocks on A. The head is now 8 and the deposit is two blocks deep.
- **Second poll:** `confirmed 1`. The relayer picks up the deposit. `digest matches contract: true` means the digest it computed itself equals what the `digest` function of the contract on B returns.
- **`r5+r6 signed, mint on B`:** two signed and the mint on B went through (`147740` gas).
- **`user wDEMO on B: 250`:** the chips reached the user.
- **`replay on B: AlreadyProcessed()`:** we gave B the same message and the same signatures again. The contract sees the nonce was already used and rejects it.
- **`same message on A: WrongRoute()`:** we sent the same message to the contract on A. It was built for the route A to B, and A expects a message from B to A, so it is rejected.
- **The rest:** the user burns 100 `wDEMO` on B. The relayers (this time r6 and r7, so any two will do) see the burn after two blocks and sign the release on A.
- **Last line:** the user has 850 DEMO on A (1000 minus 250 plus 100), 150 tokens are still locked, and 150 `wDEMO` exist on B. `backed: true` means those two numbers are equal.

Look at the addresses: DemoToken on A and BridgeMint on B are both `0x5FbDB231...`, because the same deployer used nonce 0 on both chains. A contract address does not identify a chain, which is why the {{< term "chain-id" "chain id" >}} is inside the signed message. The replay on B failed on the nonce, and sending it to A failed on the route. That is the {{< term "replay-attack" "replay" >}} protection from the nonce post, applied across chains.

The key rule (the invariant) is the last line: the tokens locked on A must always equal the `wDEMO` on B.

## When the relayer keys are stolen

Now the bad part. The whole security of this bridge is in the signatures. What if someone steals two of the three keys? A Foundry test plays exactly that: the attacker holds the keys of relayers 1 and 2 and signs a deposit that never happened:

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

The result is in the `Logs` part: 900 `wDEMO` exist and no DEMO is locked behind them. Every check in the contract passed, because from the contract's view the message is valid: two good signatures from two known relayers. As far as I know, several of the largest thefts in crypto were bridges whose validator or relayer keys were compromised. The [Binance hack write-up](/posts/binance-hack-hot-wallet-2026/) has the same lesson from another angle: no leaked key was found there, yet the signing system signed what the attacker asked.

## Limiting the damage

The same test goes on and shows the mitigations I built into the contract:

- **Cap per period:** `BridgeMint` mints at most 1000 per day ({{< term "rate-limiting" "rate limiting" >}}). The attacker had minted 900; the next forged 200 reverts with `RateLimited(1100e18, 1000e18)`, because the total 1100 is over the cap of 1000.
- **Pause:** a guardian can stop minting. The next forged message then reverts with `Paused()`. The guardian key is itself a target.
- **Higher threshold:** with 3 of 5, two stolen keys give `NotEnoughSignatures(2, 3)`. That helps only if the keys sit with independent operators on separate machines.

The stronger model removes the trusted signers. There, B runs a {{< term "light-client" "light client" >}} of A (a program that follows and checks A's block headers) and verifies with a Merkle proof that the deposit really sits in a block of A, or uses a ZK proof of the same fact. I built neither. As I understand it, the cost is gas and complexity, and it is only as safe as the source chain's finality.

## Common bridge traps

- Sign over the source and destination chain ids and contracts, plus a nonce. A contract address alone is not unique across chains.
- Wait for confirmations before signing. A reorged deposit means minted tokens with nothing locked.
- Require sorted, distinct signers and reject high-`s` signatures.
- Check that locked equals minted, and alert when it does not.

## Exercise

1. Add a per-transfer cap in `BridgeLock.release` too.
2. Reorg chain A after a deposit is signed with zero confirmations. What does the invariant say?

## What's next

**Zero-knowledge proof basics in Rust**: proofs are how stronger designs remove trusted signers.
