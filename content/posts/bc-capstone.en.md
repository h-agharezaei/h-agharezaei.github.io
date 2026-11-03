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

Whoever runs code inside the Go backend of [Exchange engineering: deposits, withdrawals, confirmations and reorgs](/posts/bc-exchange-deposits-withdrawals/) can sign anything: it scans deposits, keeps the ledger and signs withdrawals with a key compiled into the binary.

This last post moves {{< term "key-custody" "key custody" >}} into its own process. A small Rust **signer** holds the seed from [HD wallets: BIP-32, BIP-39 and BIP-44 in Rust](/posts/bc-hd-wallets-rust/); the BC31 backend asks it for addresses and signatures and holds no private key. It is the advice of [the Binance hack post](/posts/binance-hack-hot-wallet-2026/) as running code.

> Go 1.27 with go-ethereum v1.17.10, Rust 1.90 with `bip32` 0.5.3, `k256` 0.13.4, `sha3`, `serde_json`, Foundry 1.8.7, macOS (arm64). A fresh anvil on `127.0.0.1:8552` with BC16's token. The seed is BC20's **public BIP-39 test vector**, the other keys anvil's **public test accounts**: never fund them. Local projects; one `demo.sh` runs everything below.

## The split

The signer speaks one JSON object per line on `127.0.0.1:9552`. I skipped the gRPC of [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/) to keep dependencies few. Three operations, nothing else:

```rust
#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Address { index: u32 },     // m/44'/60'/0'/0/index, from the xpub
    HotAddress,                 // m/44'/60'/1'/0/0, a separate hardened account
    SignWithdrawal(Withdrawal), // chain id, nonce, fees, token, to, amount
}
```

Deposit addresses come from the account {{< term "xpub" "xpub" >}}; the {{< term "hot-wallet" "hot wallet" >}} sits under another hardened account, as BC20 advised. Without authentication, the signer refuses non-loopback addresses.

## The policy lives next to the key

`sign_withdrawal` takes the *fields* of a withdrawal, not a transaction, checks them, and builds the {{< term "eip-1559" "EIP-1559" >}} transaction and `transfer` calldata itself (RLP by hand with k256, not BC18's alloy). Condensed:

```rust
if w.chain_id != p.chain_id { return Err(format!("chain id {} is not {}", ..)); }
if parse_addr(&w.token)? != p.token { return Err(format!("token {} is not the allowed contract", ..)); }
if amount == 0 || amount > p.per_tx { return Err(..); }
// daily total: amounts signed today, rebuilt from the audit log at start;
// a fee bump with the same request id, nonce, destination and amount is not counted twice
Ok(tx::Eip1559 { to: p.token, data: tx::transfer_calldata(&to, amount), .. })
```

Each decision is appended to an {{< term "audit-log" "audit log" >}} and synced before answering. In Go, `send` still takes the nonce from Postgres, then checks the signer's answer (sender, nonce, contract, calldata). A refusal rolls the nonce back and releases the reservation:

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

`X` is `exchange -pgdir <tmp>/pg`. The signer starts; anvil account 0 funds its hot wallet with 1 ETH and 500 DEMO:

```
[signer] listening on 127.0.0.1:9552, hot wallet 0x7aBb15A014B82491c56E7fA27C88314Fc303B471, chain 31337, token 0x5FbDB2315678afecb367f032d93F642f64180aa3, per tx 100 DEMO, per day 100 DEMO, 0 signed request(s) in the audit log
$ X user -name alice
user alice created: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
$ X user -name bob
user bob created: index 1, deposit address 0xAbc76C2f6D144fA6Fe17bb6CA0e6D81a38Daa353
$ X user -name alice
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
```

Each {{< term "deposit-address" "deposit address" >}} is BC20's `m/44'/60'/0'/0/0` or `/1`, and asking again changes nothing. Then 150 DEMO to alice and three confirmations:

```
deposit alice 150 DEMO tx 0x5577c442 block 6: seen
deposit alice 150 DEMO: seen -> pending (1/3)
deposit alice 150 DEMO: pending -> credited (3/3), journal posted: true
(scan headers trimmed)
```

A withdrawal of 60 DEMO, signed in Rust, accepted by anvil:

```
withdrawal #1 created: reserved
withdrawal #1 signed by the signer: nonce 0, tx 0x0cfadb0b
withdrawal #1 sent: 0x0cfadb0b
withdrawal #1: confirmed via 0x0cfadb0b (3/3)
A3 DEMO: 60000000000000000000 [6e19]
```

## Refusals

The backend's limit is 100 DEMO per request, so it reserves 50 more. The signer's daily limit refuses:

```
withdrawal #2 created: reserved
withdrawal #2 refused by the signer: daily limit: 60 + 50 DEMO > 100
user:alice           90 DEMO
withdrawals:pending  0 DEMO
(other balance lines trimmed)
```

Now pretend the backend is compromised: `probe` sends hand-made requests straight to the socket:

```
signer refused: chain id 1 is not 31337
signer refused: token 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512 is not the allowed contract
signer refused: amount 500 DEMO over the per-tx limit 100
{"error":"bad request: unknown variant `export_seed`, expected one of `address`, `hot_address`, `sign_withdrawal` at line 1 column 19"}
```

No operation returns a key or signs a raw hash. That is the {{< term "blast-radius" "blast radius" >}} point: a stolen backend can still withdraw within the policy, but cannot drain the wallet. In [Bridges and cross-chain messaging](/posts/bc-bridges-cross-chain/) two stolen relayer keys minted unbacked tokens, and [Contract security](/posts/bc-contract-security/) lists key compromise as its own class of incident; a narrow {{< term "signing-service" "signing service" >}} prevents neither, but limits what one compromise can do.

## Restarting both

I restarted the signer, then repeated the backend's steps:

```
[signer] ... per day 100 DEMO, 1 signed request(s) in the audit log
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
head 11, cursor 0, N 3
withdrawal #1 already exists: confirmed
nothing to send
withdrawal #4 signed by the signer: nonce 1, tx 0xd86af807
withdrawal #5 refused by the signer: daily limit: 100 + 10 DEMO > 100
withdrawal #4: confirmed via 0xd86af807 (3/3)
user:alice           50 DEMO
sum of all accounts: 0
hot wallet nonce: 2
(signer line shortened, other lines trimmed)
```

The rescan credited nothing twice, the {{< term "idempotency-key" "idempotency key" >}} returned the old withdrawal, and the daily limit survived. With `--seed random` the seed lives only in memory, so two starts gave two different addresses for index 0; real use needs stored seeds.

## What a production version adds

As far as I know, and with no product in mind: the key in an {{< term "hsm" "HSM" >}} or split with {{< term "mpc" "MPC" >}}, not in process memory; authenticated transport; human approvals above a threshold, verified by the signer; the audit log shipped off the machine; destination allowlists and delays.

## Signer design rules

- The limit that matters is the signer's; the backend's checks are for users, not attackers.
- Never offer "sign these bytes". The signer builds the transaction.
- Policy state must survive restarts.
- The caller verifies the answer too.

## The course in one table

| Part | Posts | What we built |
|---|---|---|
| [Fundamentals](/posts/bc-blockchain-for-programmers/) | BC1-BC12 | a Bitcoin-like full node in Go, a Script interpreter in Rust |
| [Ethereum](/posts/bc-evm-internals-rust/) | BC13-BC20 | an EVM interpreter, Foundry contracts, Go and Rust clients, an indexer, HD wallets |
| [DeFi and security](/posts/bc-amm-constant-product/) | BC21-BC26 | AMM, lending, oracles, attacks and fixes, proxies, MEV |
| [Advanced](/posts/bc-proof-of-stake-bft/) | BC27-BC32 | BFT, a rollup, a bridge, ZK, an exchange backend, this signer |

## Where to go next

The official docs: [ethereum.org developer docs](https://ethereum.org/en/developers/docs/), [Bitcoin developer documentation](https://developer.bitcoin.org/), [Solidity docs](https://docs.soliditylang.org/) and [the Foundry book](https://book.getfoundry.sh/).

That is the end of the series. Thank you for reading; I learned a lot writing it.
