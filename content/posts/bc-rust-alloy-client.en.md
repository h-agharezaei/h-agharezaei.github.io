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

In [the previous post](/posts/bc-go-ethereum-client/) I connected to an anvil node from Go: read a balance, sent ETH, called the token and decoded a custom error. Now I have a simple question. If I do the same things from Rust, what changes? Only the syntax, or does the library think differently too?

The first sign of a difference showed up when I sent the transaction. From Go, go-ethereum suggested a tip of 1 gwei. From Rust, {{< term "alloy" "alloy" >}} picked a tip of just 1 {{< term "wei" "wei" >}}. Both work, but each library has its own defaults. In this post we take the same steps as the Go post with Rust, and whenever something differs, we look at where it comes from.

The token contract is the one we built in [the tokens post](/posts/bc-erc20-erc721/). The code is async and runs on tokio, as in [the Tokio post](/posts/rust-async-tokio/). The most interesting part comes from a procedural macro, like those in [Macros in Rust](/posts/rust-macros/).

> Run with Rust 1.90 on macOS (arm64), `alloy` 1.6.3 (default features off; `std`, `reqwest`, `provider-http`, `signer-local`, `contract`, `rpc-types`), `tokio` 1.54.1, `futures-util` 0.3 and Foundry 1.8.7. I chose 1.6.3 because newer alloy releases need a newer Rust than 1.90. A fresh anvil on `127.0.0.1:8545` with the deploy script from the tokens post. The keys in the code are anvil's public test keys: never use them anywhere real. The demo is a local Cargo project.

## Provider, chain ID and balance

The simplest job first: connect to the node and read a balance. In alloy this is done by a `Provider`. A provider turns the node's API, the {{< term "json-rpc" "JSON-RPC" >}} over HTTP, into Rust methods. It sits in the program where `ethclient` sits in Go.

```rust
let provider = ProviderBuilder::new().connect_http(RPC.parse()?);
let addr0 = KEY0.parse::<PrivateKeySigner>()?.address();
let bal = provider.get_balance(addr0).await?; // U256, in wei
println!("chain id:     {}", provider.get_chain_id().await?);
println!("balance ETH:  {}", format_units(bal, "ether")?);
```

Read `ProviderBuilder` as a step-by-step constructor: you say where to connect (`connect_http`) and, as the next section shows, you can add other things to it. The second line derives account 0's address from its private key. The rest is two questions to the node. Output of `alloydemo info`:

```
$ ./target/debug/alloydemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

These are the same numbers as in the Go run, because both talk to the same deploy: network 31337 (anvil's default), three blocks made by the deploy script, and a balance slightly below 10,000 ETH because account 0 paid gas for those three transactions.

There is one small difference. The balance in wei is a `U256`, a 256-bit integer of fixed size. In Go we used `*big.Int`, whose size is arbitrary. The `format_units` function, which turns wei into ETH with a decimal point, ships with alloy, so I did not have to write it myself as I did in Go.

## Wallet and an EIP-1559 send

To send a transaction, the provider has to be able to sign. In alloy that means giving the builder a signer:

```rust
let signer: PrivateKeySigner = KEY0.parse()?;
let provider = ProviderBuilder::new().wallet(signer).connect_http(RPC.parse()?);
let value = U256::from(1_500_000_000_000_000_000u128); // 1.5 ETH
let tx = TransactionRequest::default().with_to(ACCT1).with_value(value);
let rcpt = provider.send_transaction(tx).await?.get_receipt().await?;
```

Notice what I did not write. I only gave the recipient and the amount. No nonce, no gas limit, no fees, no chain ID. The builder's default "fillers" supply these: each one asks the node for one empty field of the transaction before signing and fills it in. `send_transaction` sends it, and `get_receipt` waits until it lands in a block and returns the receipt. Output of `alloydemo send`:

```
$ ./target/debug/alloydemo send
tx type: 2 hash: 0xa0306b3e8c9b5ef2886dc4d96111769d11e473ff92a28ac0d09d701e9cb3c58b
status: true block: 4 gas used: 21000 effective gas price: 685976108
account 1 gained: 1.500000000000000000 ETH
```

- **`tx type: 2`:** the transaction is an {{< term "eip-1559" "EIP-1559" >}} one. The fillers chose this type on their own.
- **`status: true`, `block: 4`:** it succeeded and landed in block 4.
- **`gas used: 21000`:** the fixed cost of a plain ETH transfer, the same number as in Go.
- **`effective gas price`:** what was actually paid per unit of gas. It equals block 4's base fee (685976107, which we saw with `cast` in the Go post) plus a tip of 1 wei.
- **Last line:** account 1 received exactly 1.5 ETH.

Back to the tip. With `cast tx` I looked at what the fillers chose: `maxFeePerGas` is 1566842331, that is twice block 3's base fee (783421165) plus a tip of **1 wei**. Why 1 wei and not 1 gwei? In Go, `SuggestGasTipCap` asked the node (`eth_maxPriorityFeePerGas`) and the answer was 1 gwei. alloy 1.6.3's estimator (I read its source) does not ask that. It takes the median tip from `eth_feeHistory` over the last 10 blocks, and the deploy transactions had tipped only 1 wei, so that is what it used. On anvil it makes no difference, but on a real network this default decides how quickly your transaction gets into a block.

## The sol! macro instead of abigen

To call a contract, the program must know its functions: names, argument types and return types. That description is the {{< term "contract-abi" "ABI" >}}. In Go I took the ABI from Foundry's output and ran abigen, which wrote a 648-line `token.go` into the repo, to be regenerated every time the contract changes.

Rust has another way: the {{< term "sol-macro" "sol! macro" >}}. You write the contract's declarations in Solidity syntax inside your Rust code, and the macro turns them into Rust at compile time. No generated file stays in the repo.

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

I wrote only what this post needs: one event, four custom errors and three functions. The `#[sol(rpc)]` attribute tells the macro to generate, besides the types, methods that call the contract through a provider.

The main benefit is that the arguments are typed. To see it, I wrote a deliberately wrong call in `examples/wrong_type.rs`: the address is a string and the amount is a plain number. The compiler refuses:

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

There are two type errors: I passed a `&str` where an `Address` is expected, and a plain integer where a `U256` is expected. This mistake is caught before the program runs; the code does not compile at all. (I trimmed the compiler output.)

The flip side: I wrote this interface by hand, so it can drift from the deployed contract. `sol!` can also load the ABI JSON from `out/`; I did not try that.

## Call and send

With this interface, calling the contract looks like calling an ordinary function:

```rust
let token = DemoToken::new(TOKEN, &provider);
let dec = token.decimals().call().await?;   // u8
let b0 = token.balanceOf(me).call().await?; // U256
let rcpt = token.transfer(ACCT1, amount).send().await?.get_receipt().await?;
let ev = rcpt.decoded_log::<DemoToken::Transfer>().ok_or("no Transfer log")?;
```

`.call()` only reads and changes nothing on the network (like `cast call`). `.send()` sends a real transaction (like `cast send`). At the end, `decoded_log` opens the log the contract emitted, using the event declared above. Output of `alloydemo token`:

```
$ ./target/debug/alloydemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO
transfer tx type: 2 status: true gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 1: 100.000000000000000000 DEMO
```

- **Line 1:** `decimals()` returns a plain `u8` (18), and account 0 holds the whole 1,000,000 DEMO.
- **Line 2:** the transfer is also a type 2 transaction and it succeeded. Gas used is 52383, the same number we saw with `cast send` and in Go, and there is exactly one log.
- **Line 3:** the `Transfer` event, from account 0 to account 1. The value is 10^20 units, because I sent 100 DEMO and each DEMO is 10^18 units.
- **Line 4:** account 1 now holds 100 DEMO.

## Custom error as an enum

Now a failure. Account 2 has no DEMO and tries to send 1 DEMO. During gas estimation the simulated call {{< term "revert" "reverts" >}} and nothing is sent. What reaches us is an error that carries the raw revert data.

Here `sol!` helps again: for the errors we declared it generated an enum called `DemoTokenErrors`, with one variant per error. So we can `match` on it:

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

- **`raw error`:** what the node returned, shortened (the real hex string is longer). `0xdb42144d` is the error's {{< term "function-selector" "selector" >}}: the first four bytes, which say which error happened. The error's arguments follow.
- **Second line:** the `match` turned those bytes into `InsufficientBalance`: account 2 (address `0x3C44…`) has a balance of 0 and needed 10^18 units, which is 1 DEMO.
- **`account 2 nonce: 0`:** the transaction was never sent, so the account's nonce did not move.

Compared with Go: there I unpacked into an `any` and did a type assertion. Here the `match` has to be exhaustive, so if I add a new error to `sol!`, I should get a compile error at this spot. I did not try that last part.

## Watching Transfer events

The last step: listening for events. We install a filter on the node that says "show me every new Transfer", then send two transfers and print the two events that come back:

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

Each line is one transfer: the first moved 1 unit in block 6, the second moved 2 units in block 7 (block 5 was the transfer from the previous example).

The important point is that over HTTP the node pushes nothing. In the 1.6.3 source, `watch` creates a filter on the node with `eth_newFilter` and then keeps calling `eth_getFilterChanges`, that is, it polls: every 250 ms for a local node and every 7 s otherwise. Each item is a decoded {{< term "event-log" "log" >}} with its metadata (such as the block number) next to it. Because the filter lives on the node itself, it vanishes when the node restarts. That is why, later, we need another way to keep events.

## Go and Rust, from what I saw

- **Typing the ABI:** abigen writes code you must regenerate; `sol!` expands at compile time, and wrong argument types are compile errors.
- **Errors:** Go gave `rpc.DataError` plus a type assertion; alloy gives an `Option` of a generated enum.
- **Defaults:** alloy filled nonce, gas and fees; in Go I either did that by hand or let `bind.Transact` do it.
- **Weight:** `Cargo.lock` has 397 packages, and the dev build without debug info was 506 MB of `target/`.

## Defaults that surprise

- **The fillers choose fees from fee history.** As we saw, the tip was 1 wei because earlier blocks had paid that little. Check the tip on a real network.
- **In 1.6.3 the default nonce filler caches per address and counts locally,** like the nonce manager from the Go post. Two processes with one key still collide.
- **A hand-written `sol!` interface can drift from the deployed contract.** Generate it from the ABI if the contract changes often.

## Exercise

1. Repeat the Go nonce race with five tokio tasks sharing one provider, then with five providers.
2. Pass the error from calling `mint` from account 1 to the same `match` (add `mint` to `sol!` first).
3. Replace `watch` with `get_logs` over blocks 0 to latest. How many Transfers do you get, and why does the first one come from the zero address?

## What's next

The next post is "Events and building an indexer with Go and Postgres": a filter on the node vanishes when the node restarts, so the events have to be stored somewhere that survives.
