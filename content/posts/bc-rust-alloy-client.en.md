+++
date = '2026-11-19T18:00:00+03:30'
draft = false
title = 'Talking to Ethereum from Rust with alloy'
description = 'alloy from Rust: provider and wallet, an EIP-1559 send with receipt, sol! macro token calls, a custom error decoded to an enum, polled Transfer events.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "ethereum", "alloy", "erc20"]
cover = { image = "/images/covers/bc-rust-alloy-client.png", alt = "Talking to Ethereum from Rust with alloy", hiddenInSingle = true }
+++

Send ether from Go and from Rust to the same anvil and the tips differ: go-ethereum suggested 1 gwei, {{< term "alloy" "alloy" >}} picked 1 {{< term "wei" "wei" >}}. This post takes the steps of [the Go post](/posts/bc-go-ethereum-client/) to Rust.

The contract comes from [the tokens post](/posts/bc-erc20-erc721/); the async code runs on tokio, as in [the Tokio post](/posts/rust-async-tokio/), and the macro is a procedural macro like those in [Macros in Rust](/posts/rust-macros/).

> Rust 1.90 on macOS (arm64), `alloy` 1.6.3 (default features off; `std`, `reqwest`, `provider-http`, `signer-local`, `contract`, `rpc-types`), `tokio` 1.54.1, `futures-util` 0.3, Foundry 1.8.7. I chose 1.6.3 because newer alloy releases need a newer Rust than 1.90. A fresh anvil on `127.0.0.1:8545` with the deploy script from the token post. The keys in the code are anvil's public test keys: never use them anywhere real. The demo is a local Cargo project.

## Provider, chain ID, balance

A `Provider` wraps the node's {{< term "json-rpc" "JSON-RPC" >}} API, like `ethclient`:

```rust
let provider = ProviderBuilder::new().connect_http(RPC.parse()?);
let addr0 = KEY0.parse::<PrivateKeySigner>()?.address();
let bal = provider.get_balance(addr0).await?; // U256, in wei
println!("chain id:     {}", provider.get_chain_id().await?);
println!("balance ETH:  {}", format_units(bal, "ether")?);
```

```
$ ./target/debug/alloydemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

Same numbers as the Go run, from the same deploy. The balance in wei is a `U256`, a fixed 256-bit integer, where Go used `*big.Int`. `format_units` ships with alloy.

## Wallet and an EIP-1559 send

Attach a signer to the builder and the provider can send:

```rust
let signer: PrivateKeySigner = KEY0.parse()?;
let provider = ProviderBuilder::new().wallet(signer).connect_http(RPC.parse()?);
let value = U256::from(1_500_000_000_000_000_000u128); // 1.5 ETH
let tx = TransactionRequest::default().with_to(ACCT1).with_value(value);
let rcpt = provider.send_transaction(tx).await?.get_receipt().await?;
```

```
$ ./target/debug/alloydemo send
tx type: 2 hash: 0xa0306b3e8c9b5ef2886dc4d96111769d11e473ff92a28ac0d09d701e9cb3c58b
status: true block: 4 gas used: 21000 effective gas price: 685976108
account 1 gained: 1.500000000000000000 ETH
```

I set no nonce, gas or fees: the builder's default "fillers" did, producing an {{< term "eip-1559" "EIP-1559" >}} (type 2) transaction. `cast tx` shows what they chose: `maxFeePerGas` 1566842331, that is twice block 3's base fee (783421165) plus a tip of **1 wei**. In Go, `SuggestGasTipCap` asked `eth_maxPriorityFeePerGas` and got 1 gwei. alloy 1.6.3's estimator (I read its source) instead takes the median tip from `eth_feeHistory` over the last 10 blocks, and the deploy transactions had tipped 1 wei.

## The sol! macro instead of abigen

In Go I exported the {{< term "contract-abi" "ABI" >}} and ran abigen, which wrote a 648-line `token.go` into the repo. In Rust the {{< term "sol-macro" "sol! macro" >}} reads Solidity declarations at compile time:

```rust
sol! {
    #[sol(rpc)]
    contract DemoToken {
        event Transfer(address indexed from, address indexed to, uint256 value);

        error InsufficientBalance(address from, uint256 balance, uint256 needed);
        error InsufficientAllowance(address spender, uint256 allowance, uint256 needed);
        error ZeroAddress();
        error NotMinter();

        function decimals() external view returns (uint8);
        function balanceOf(address owner) external view returns (uint256);
        function transfer(address to, uint256 value) external returns (bool);
    }
}
```

No generated file is checked in, and the arguments are typed. A deliberately wrong call in `examples/wrong_type.rs` does not compile:

```
$ cargo build -q --example wrong_type
error[E0308]: arguments to this method are incorrect
  --> examples/wrong_type.rs:14:23
   |
14 |     let _call = token.transfer("0x70997970C51812dc3A010C7d01b50e0d17dc79C8", 100);
   |                       ^^^^^^^^ -------------------------------------------- expected `Address`, found `&str`
... (trimmed)
   = note: expected struct `alloy::alloy_primitives::Uint<256, 4>`
                found type `{integer}`
```

The flip side: I typed this interface by hand. `sol!` can also load the ABI JSON from `out/`; I did not try that.

## Call and send

```rust
let token = DemoToken::new(TOKEN, &provider);
let dec = token.decimals().call().await?;   // u8
let b0 = token.balanceOf(me).call().await?; // U256
let rcpt = token.transfer(ACCT1, amount).send().await?.get_receipt().await?;
let ev = rcpt.decoded_log::<DemoToken::Transfer>().ok_or("no Transfer log")?;
```

```
$ ./target/debug/alloydemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO
transfer tx type: 2 status: true gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 1: 100.000000000000000000 DEMO
```

Gas used is 52383, as with `cast send` and Go. `decimals()` returns a plain `u8`.

## Custom error as an enum

Account 2 has no DEMO. At gas estimation the call {{< term "revert" "reverts" >}} and nothing is sent. `sol!` generated a `DemoTokenErrors` enum with one variant per error, so I can `match` on it:

```rust
use DemoToken::DemoTokenErrors as E;
match err.as_decoded_interface_error::<E>() {
    Some(E::InsufficientBalance(e)) => {
        println!("InsufficientBalance: from {} balance {} needed {}", e.from, e.balance, e.needed)
    }
    Some(E::InsufficientAllowance(_)) => println!("InsufficientAllowance"),
    Some(E::ZeroAddress(_)) => println!("ZeroAddress"),
    Some(E::NotMinter(_)) => println!("NotMinter"),
    None => println!("not a DemoToken error"),
}
```

```
$ ./target/debug/alloydemo revert
raw error: server returned an error response: error code 3: execution reverted: custom error 0xdb42144d: 0000...3c44cdddb6a900fa2b585dd299e03d12fa4293bc...0de0b6b3a7640000, data: "0xdb42144d...0de0b6b3a7640000"   (trimmed)
InsufficientBalance: from 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC balance 0 needed 1000000000000000000
account 2 nonce: 0
```

`0xdb42144d` is the error's {{< term "function-selector" "selector" >}}. In Go I unpacked to an `any` and type-asserted; here the `match` is exhaustive, so a new error added to `sol!` should become a compile error at this spot (I did not try it).

## Watching Transfer events

```rust
let poller = token.Transfer_filter().watch().await?;
let mut stream = poller.into_stream().take(2);
for n in [1u64, 2] {
    token.transfer(ACCT1, U256::from(n)).send().await?.watch().await?;
}
while let Some(item) = stream.next().await {
    let (ev, log) = item?;
    println!("block {}: {} -> {} value {}", log.block_number.unwrap_or_default(), ev.from, ev.to, ev.value);
}
```

```
$ ./target/debug/alloydemo events
block 6: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 value 1
block 7: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 value 2
```

Over HTTP there is no push. In the 1.6.3 source, `watch` installs a filter with `eth_newFilter` and polls `eth_getFilterChanges`, every 250 ms for a local node and 7 s otherwise. Each item is a decoded {{< term "event-log" "log" >}} plus its metadata. Filters live on the node and vanish when it restarts.

## Go and Rust, from what I saw

- ABI typing: abigen writes code you regenerate; `sol!` expands at compile time, and wrong argument types are compile errors.
- Errors: Go gave `rpc.DataError` plus a type assertion; alloy gives an `Option` of a generated enum.
- Defaults: alloy filled nonce, gas and fees; in Go I did that by hand or via `bind.Transact`.
- Weight: `Cargo.lock` has 397 packages, and the dev build without debug info was 506 MB of `target/`.

## Defaults that surprise

- Fillers choose fees from fee history. Check the tip on a real network before trusting it.
- In 1.6.3 the default nonce filler caches per address and counts locally, like the nonce manager from the Go post. Two processes with one key still collide.
- A hand-written `sol!` interface can drift from the deployed contract. Generate it from the ABI if the contract changes often.

## Exercise

1. Repeat the Go nonce race with five tokio tasks sharing one provider, then with five providers.
2. Pass the error from calling `mint` from account 1 to the same `match` (add `mint` to `sol!` first).
3. Replace `watch` with `get_logs` over blocks 0 to latest. How many Transfers do you get, and why does the first one come from the zero address?

## What's next

Next post: **Events and building an indexer with Go and Postgres**: events kept beyond a node restart.
