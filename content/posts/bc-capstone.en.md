+++
date = '2026-12-03T18:00:00+03:30'
draft = false
title = 'Blockchain capstone with Go and Rust'
description = 'Blockchain capstone with Go and Rust: a Rust signer holds the HD seed and enforces a policy; the Go exchange backend never sees a private key.'
contentType = 'engineering'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "rust", "ethereum", "exchange", "security"]
cover = { image = "/images/covers/bc-capstone.png", alt = "Blockchain capstone with Go and Rust", hiddenInSingle = true }
+++

The Go backend of [Exchange engineering: deposits, withdrawals, confirmations and reorgs](/posts/bc-exchange-deposits-withdrawals/) scans deposits, keeps the ledger and also signs the withdrawals itself, with a key compiled into the binary. So whoever can run code inside that program can sign anything: a bug, a poisoned dependency, a compromised server. The key and the program's logic live in one process, so whoever takes the program has taken the key too.

Picture a cashier who holds both the safe's key and the account book. Anyone who fools the cashier empties the safe. The old fix is to give the key to somebody else who knows only one job: compare each request against its own rules and sign only if it is allowed. The cashier can make requests, but never sees the key.

This last post does exactly that: it moves {{< term "key-custody" "key custody" >}} into its own process. A small Rust **signer** holds the seed from [HD wallets: BIP-32, BIP-39 and BIP-44 in Rust](/posts/bc-hd-wallets-rust/). The backend from the previous post asks the signer for addresses and signatures and holds no private key itself. It is the advice of [the Binance hack post](/posts/binance-hack-hot-wallet-2026/) as running code.

> Go 1.27 with go-ethereum v1.17.10, Rust 1.90 with `bip32` 0.5.3, `k256` 0.13.4, `sha3`, `serde_json`, Foundry 1.8.7, macOS (arm64). A fresh anvil on `127.0.0.1:8552` with the token from the tokens post. The seed is the **public BIP-39 test vector** of the HD wallets post, the other keys anvil's **public test accounts**: never fund them. Local projects; one `demo.sh` script runs everything below.

## The split

The signer talks to the backend on `127.0.0.1:9552`. Each message is one line holding one JSON object. I skipped the gRPC of [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/) to keep dependencies few. The signer knows three operations and nothing else:

```rust
#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Address { index: u32 },     // m/44'/60'/0'/0/index, from the xpub
    HotAddress,                 // m/44'/60'/1'/0/0, a separate hardened account
    SignWithdrawal(Withdrawal), // chain id, nonce, fees, token, to, amount
}
```

Three operations: the deposit address for a user number, the hot wallet's address, and the signature for a withdrawal. None of them is "give me the key" or "sign these bytes". Deposit addresses come from the account {{< term "xpub" "xpub" >}} (an extended public key, which can make addresses but cannot sign). The {{< term "hot-wallet" "hot wallet" >}} sits under another hardened account (it cannot be derived from the deposit account's xpub), as the HD wallets post advised. There is no authentication, so the signer listens on loopback only and refuses any other address.

## The policy lives next to the key

The core of this design is `sign_withdrawal`. Instead of a ready-made transaction, it takes only the *fields* of a withdrawal: chain id, nonce, fees, token, destination and amount. The signer checks the fields and then builds the {{< term "eip-1559" "EIP-1559" >}} transaction and the `transfer` calldata itself (I wrote the RLP by hand with k256, not with alloy from the Rust client post). So a compromised backend cannot hand it an arbitrary transaction, because the signer builds the transaction. Condensed:

```rust
if w.chain_id != p.chain_id { return Err(format!("chain id {} is not {}", ..)); }
if parse_addr(&w.token)? != p.token { return Err(format!("token {} is not the allowed contract", ..)); }
if amount == 0 || amount > p.per_tx { return Err(..); }
// daily total: amounts signed today, rebuilt from the audit log at start;
// a fee bump with the same request id, nonce, destination and amount is not counted twice
Ok(tx::Eip1559 { to: p.token, data: tx::transfer_calldata(&to, amount), .. })
```

The first three checks: the chain must be right, the token must be the one allowed contract, and the amount must be above zero and within the per-transaction cap. Then there is a daily cap. The total signed today is rebuilt from the audit log at start, and a fee bump of one transaction (same request id, nonce, destination and amount) is not counted twice. "Today" means the day by Unix time (UTC).

Every decision, signed or refused, is appended to an {{< term "audit-log" "audit log" >}} and synced to disk before the answer goes out. Two things change on the Go side. `send` still takes the nonce from Postgres, and it verifies the signer's answer (sender, nonce, contract and calldata). And if the signer refuses, the nonce is rolled back and the reserved amount is released:

```go
var refused errRefused
if errors.As(err, &refused) {
	tx.Rollback(ctx) // the nonce was not used
	if err := ex.release(ctx, id, refused.reason); err != nil {
		return err
	}
	fmt.Printf("withdrawal #%d refused by the signer: %s\n", id, refused.reason)
	continue
}
```

## End to end

Now we run everything together. `X` is `exchange -pgdir <tmp>/pg`. First the signer starts, and anvil account 0 funds its hot wallet with 1 ETH (for gas) and 500 DEMO:

```
[signer] listening on 127.0.0.1:9552, hot wallet 0x7aBb15A014B82491c56E7fA27C88314Fc303B471, chain 31337, token 0x5FbDB2315678afecb367f032d93F642f64180aa3, per tx 100 DEMO, per day 100 DEMO, 0 signed request(s) in the audit log
$ X user -name alice
user alice created: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
$ X user -name bob
user bob created: index 1, deposit address 0xAbc76C2f6D144fA6Fe17bb6CA0e6D81a38Daa353
$ X user -name alice
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
```

The signer prints the first line. It says which address it listens on, what the hot wallet's address is, which chain and token it works with, and the caps: 100 DEMO per transaction and 100 DEMO per day. `0 signed request(s)` means the audit log is still empty.

The next three lines create the users. Each user gets the next number and asks the signer for its deposit address. alice is number 0 and bob is number 1. Each {{< term "deposit-address" "deposit address" >}} is the `m/44'/60'/0'/0/0` or `/1` of the HD wallets post. Asking for alice again changes nothing: the same user with the same address.

Then 150 DEMO is deposited to alice and the backend waits for three confirmations. (It is block 6 because blocks 1 to 3 were the deployment, and blocks 4 and 5 sent ETH and DEMO to the hot wallet.)

```
head 6, cursor -1, N 3
deposit alice 150 DEMO tx 0x5577c442 block 6: seen
deposit alice 150 DEMO: seen -> pending (1/3)
head 8, cursor 6, N 3
deposit alice 150 DEMO: pending -> credited (3/3), journal posted: true
```

The first scan sees the deposit and makes it `pending (1/3)`. We mine two blocks. The second scan sees `3/3` and credits the account. It is the same state machine as in the previous post.

Now a withdrawal of 60 DEMO. The backend reserves it, the signer signs it, and anvil accepts it:

```
withdrawal #1 created: reserved
withdrawal #1 signed by the signer: nonce 0, tx 0x0cfadb0b
withdrawal #1 sent: 0x0cfadb0b
withdrawal #1: confirmed via 0x0cfadb0b (3/3)
A3 DEMO: 60000000000000000000 [6e19]
```

The last line reads the destination account's (`A3`) token balance from the chain itself: 60 DEMO, written with 18 decimals as `6e19`. So the withdrawal really happened.

## Refusals

Now another withdrawal, of 50 DEMO. The backend's limit is 100 DEMO per request, so it reserves it. But the signer has signed 60 today, and 60 + 50 is above its daily cap of 100:

```
withdrawal #2 created: reserved
withdrawal #2 refused by the signer: daily limit: 60 + 50 DEMO > 100
nothing to send
external             -90 DEMO
user:alice           90 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
```

The signer refused, the nonce was rolled back and the reservation was released: `withdrawals:pending` is zero again and alice has 90 (150 minus 60). `nothing to send` means nothing is left to send. The ledger still adds up to zero.

Now pretend the backend is compromised and the attacker talks to the signer directly instead of through the backend. The `probe` command sends hand-made requests straight to the socket:

```
signer refused: chain id 1 is not 31337
signer refused: token 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512 is not the allowed contract
signer refused: amount 500 DEMO over the per-tx limit 100
{"error":"bad request: unknown variant `export_seed`, expected one of `address`, `hot_address`, `sign_withdrawal` at line 1 column 19"}
```

The first three lines are three forged requests: another chain (chain id 1), another contract (the NFT's address instead of the token's) and an amount of 500, over the cap of 100. All three were refused. The last line is a message I sent with `nc`: `{"op":"export_seed"}`, "give me the seed". The operation is unknown and the result is a plain error, because no such operation exists in `Request`.

No operation returns a key or signs a raw hash. That is the {{< term "blast-radius" "blast radius" >}} point: a stolen backend can still withdraw within the policy, but it cannot drain the wallet. In [Bridges and cross-chain messaging](/posts/bc-bridges-cross-chain/) two stolen relayer keys minted unbacked tokens, and [Contract security](/posts/bc-contract-security/) lists key compromise as its own class of incident. A narrow {{< term "signing-service" "signing service" >}} prevents neither, but it limits what one compromise can do.

## Restarting both

One important question remains: what if the processes are restarted? The policy state, such as today's total, has to survive. I restarted the signer and repeated the backend's steps. (I also re-scanned the backend from block zero with `-rewind 0`.)

```
[signer] ... per day 100 DEMO, 1 signed request(s) in the audit log
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
head 11, cursor 0, N 3
withdrawal #1 already exists: confirmed
nothing to send
withdrawal #4 created: reserved
withdrawal #5 created: reserved
withdrawal #4 signed by the signer: nonce 1, tx 0xd86af807
withdrawal #5 refused by the signer: daily limit: 100 + 10 DEMO > 100
withdrawal #4 sent: 0xd86af807
withdrawal #4: confirmed via 0xd86af807 (3/3)
external             -50 DEMO
user:alice           50 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
hot wallet nonce: 2
(signer line shortened)
```

Line by line:

- **First line:** the signer came up and found one signed request in the audit log (the 60 DEMO). It rebuilt today's total from it.
- **alice's address:** the same as before, because the seed is fixed.
- **`head 11, cursor 0`:** the scan started from block zero. It saw the 150 DEMO deposit again, but no deposit line was printed and nothing was credited twice.
- **`#1 already exists: confirmed`:** the same `w-1` request with the same idempotency key returned the old withdrawal, not a new one. `nothing to send` means nothing is left.
- **`#4` and `#5`:** two new withdrawals, of 40 and 10 DEMO. Both were reserved.
- **`#4 signed`:** 60 (from before) + 40 is 100, which does not go over the daily cap. It was signed with nonce 1. That nonce was still unused, because withdrawal #2 was refused and its nonce rolled back.
- **`#5 refused`:** 100 + 10 goes over the cap. It was refused and its reservation released. The daily cap survived the restart.
- **The last lines:** alice has 50 (150 minus 60 minus 40), the ledger adds up to zero, and the hot wallet's nonce is 2: two transactions really went out.

So the result: the re-scan (`-rewind 0`) credited nothing twice, the {{< term "idempotency-key" "idempotency key" >}} returned the earlier withdrawal, and the daily cap survived the restart.

With `--seed random` it is different: the seed lives only in the process's memory, so every start gets a new seed and new addresses. I started it twice with `--seed random` and the hot wallet got two different addresses. Real use needs a stored seed.

The audit log after the whole run holds seven decisions: two signed (withdrawals 1 and 4) and five refused (withdrawal 2, the three `probe` requests and withdrawal 5). Refusals are recorded too.

## What a production version adds

As far as I know, and with no product in mind: the key in an {{< term "hsm" "HSM" >}} or split with {{< term "mpc" "MPC" >}}, not in process memory; authenticated transport; human approvals above a threshold that the signer itself verifies; the audit log shipped off the machine; destination allowlists and delays.

## Signer design rules

- The limit that matters is the signer's. The backend's checks are for users, not attackers.
- Never offer "sign these bytes". The signer builds the transaction.
- Policy state must survive restarts.
- The caller verifies the signer's answer too.

## The course in one table

If you followed the posts from the start, this table sums up the road. Each row is a part, with the post numbers and what we built:

| Part | Posts | What we built |
|---|---|---|
| [Fundamentals](/posts/bc-blockchain-for-programmers/) | 1 to 12 | a Bitcoin-like full node in Go, a Script interpreter in Rust |
| [Ethereum](/posts/bc-evm-internals-rust/) | 13 to 20 | an EVM interpreter, Foundry contracts, Go and Rust clients, an indexer, HD wallets |
| [DeFi and security](/posts/bc-amm-constant-product/) | 21 to 26 | AMM, lending, oracles, attacks and fixes, proxies, MEV |
| [Advanced](/posts/bc-proof-of-stake-bft/) | 27 to 32 | BFT, a rollup, a bridge, ZK, an exchange backend, this signer |

A few things from earlier posts came back in this signer: keys and ECDSA signatures, HD addresses, EIP-1559 transactions and nonces, the ledger and confirmations from the exchange post, and the stolen-key lesson from the bridge.

## Where to go next

The official docs: [ethereum.org developer docs](https://ethereum.org/en/developers/docs/), [Bitcoin developer documentation](https://developer.bitcoin.org/), [Solidity docs](https://docs.soliditylang.org/) and [the Foundry book](https://book.getfoundry.sh/).

That is the end of the series. Thank you for reading; I learned a lot writing it.
