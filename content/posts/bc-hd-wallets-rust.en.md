+++
date = '2026-11-21T18:00:00+03:30'
draft = false
title = 'HD wallets: BIP-32, BIP-39 and BIP-44 in Rust'
description = 'HD wallets in Rust: BIP-39 words to seed, BIP-32 checked against test vectors, BIP-44 Ethereum addresses, watch-only xpub servers and the xpub leak.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "hd-wallet", "bip32", "bip39", "ethereum"]
cover = { image = "/images/covers/bc-hd-wallets-rust.png", alt = "HD wallets: BIP-32, BIP-39 and BIP-44 in Rust", hiddenInSingle = true }
+++

The previous post, [Events and building an indexer with Go and Postgres](/posts/bc-event-indexer-go/), watched the chain for transfers to known addresses. But where do they come from? In [Keys, ECDSA signatures and addresses on secp256k1](/posts/bc-keys-ecdsa-addresses/) one random key gave one address. An exchange needs an address per user; a random key each means a backup that grows with every signup and a server full of private keys.

An {{< term "hd-wallet" "HD wallet" >}} fixes both: one seed, a tree of keys computed from it, and a public half that creates addresses without any private key. It also fits the hot/cold split from [the Binance hack post](/posts/binance-hack-hot-wallet-2026/).

> Every mnemonic, seed and address below comes from **public test vectors**. Anyone can compute their keys: never fund or use them. Rust 1.90, `bip32` 0.5.3 (iqlusion), `k256` 0.13.4, `pbkdf2` 0.12.2, `hmac` 0.12.1, `sha2` 0.10.9, `sha3` 0.10.9, `hex` 0.4.3, macOS (arm64). The demo is a local Cargo project.

## BIP-39: words to seed

{{< term "bip-39" "BIP-39" >}} takes random entropy (256 bits here), appends the first byte of its SHA-256 as a checksum, and cuts the 264 bits into 24 chunks of 11 bits, each an index into a 2048-word list. I used the all-zero vector from the crate's test file (copied from Trezor's `vectors.json`):

```rust
let m = Mnemonic::from_entropy([0u8; 32], Language::English);
let cs = Sha256::digest([0u8; 32])[0];
let typo = m.phrase().replace(" art", " abandon");
println!("last word changed: {:?}", Mnemonic::new(typo, Language::English).err());
```

```
words: 24, first: abandon, last: art
checksum byte: 0x66 -> last word index 102
last word changed: Some(Bip39)
```

The last word holds 3 zero bits of entropy plus the checksum `0x66` = 102 = "art", so a typo is usually caught. This crate returns one generic `Bip39` error and only handles 24 words.

According to BIP-39, the seed is {{< term "pbkdf2" "PBKDF2" >}}-HMAC-SHA512 with the words as password, `"mnemonic" + passphrase` as salt, 2048 rounds. I recomputed it by hand:

```rust
let seed = m.to_seed("TREZOR");
let mut manual = [0u8; 64];
pbkdf2::pbkdf2_hmac::<Sha512>(m.phrase().as_bytes(), b"mnemonicTREZOR", 2048, &mut manual);
```

```
seed: bda85446c6841370...
seed matches vector: true
manual PBKDF2 == seed: true
seed with empty passphrase: 408b285c12383600...
root xprv matches vector: true
```

Another passphrase is simply another wallet; nothing says "wrong passphrase". As in [Storing passwords safely](/posts/sec-password-hashing/), rounds only slow guessing; the entropy protects you.

## BIP-32: master key, chain code, children

{{< term "bip-32" "BIP-32" >}} takes {{< term "hmac" "HMAC" >}}-SHA512 of the seed: left half is the master private key, right half the **chain code**. A child is again HMAC-SHA512, keyed by the parent's chain code; its left half is added to the parent key mod n. Key plus chain code is an extended key: `xprv`, or {{< term "xpub" "xpub" >}} for the public side. BIP-32 test vector 1 (seed `000102...0f`; expected values from the spec and the crate's tests):

```
chain code: 873dff81c02f525623fd1fe5167eac3a55a049de3d314bb42ee227ffed37d508
m xprv matches: true
m/0'/1 from xpub only matches: true
xpub -> hardened child: Some(ChildNumber)
```

`m/0'/1` came from the xpub of `m/0'` alone. That works for **normal** indexes, where the HMAC input is the parent public key. For {{< term "hardened-derivation" "hardened" >}} ones (`2'`, index 2^31 and up) the input is the parent private key, so the xpub refuses.

## Why hardening matters

Normal derivation is `k_child = IL + k_parent mod n`, and `IL` needs only the parent xpub. So the xpub plus one leaked normal child key gives `k_parent = k_child - IL`:

```rust
let mut mac = Hmac::<Sha512>::new_from_slice(&parent.attrs().chain_code).unwrap();
mac.update(&parent.to_bytes()); // 33-byte compressed public key
mac.update(&index.to_be_bytes());
let i = mac.finalize().into_bytes();
let il = <Scalar as Reduce<U256>>::reduce_bytes(i[..32].into());
let kc = <Scalar as Reduce<U256>>::reduce_bytes(child_priv.into());
(kc - il).to_bytes().into()
```

I leaked the key of `m/44'/60'/0'/0/3` and climbed twice:

```
recovered m/44'/60'/0' private key == real: true
```

One leaked key spends the whole account. The climb stops at hardened `0'`: its `IL` needs the very key we want.

## BIP-44 and Ethereum addresses

{{< term "bip-44" "BIP-44" >}} fixes the layout `m / 44' / coin' / account' / change / index`, with 60 for Ether. The address rule is BC4's: Keccak-256 of the uncompressed key, last 20 bytes, {{< term "eip-55" "EIP-55" >}} casing; it still gives BC4's key-1 address `0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf`. Watch-only versus full derivation:

```
account xpub: xpub6DGfjznv...EajsXn
m/44'/60'/0'/0/0  0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655  same as xprv: true
m/44'/60'/0'/0/1  0xAbc76C2f6D144fA6Fe17bb6CA0e6D81a38Daa353  same as xprv: true
m/44'/60'/0'/0/2  0x7375C7Ea6F22Dd15A36DAC44E906a83991a75701  same as xprv: true
```

I did not cross-check these three addresses against another wallet.

## A watch-only deposit server

The shape I would use for exchange deposits:

- An offline machine creates the seed and exports only the account xpub.
- The deposit service stores `(user_id, index, address)` with `address = xpub/0/index`. No private key there.
- The indexer from the previous post watches those addresses.
- A separate signer moves funds: a small {{< term "hot-wallet" "hot wallet" >}} online, the rest cold.

Never hand out an xpub whose normal children are also signed with online; separate them with hardened accounts.

## A few things to watch

- The mnemonic is every private key at once: no logs, screenshots or cloud notes.
- An xpub reveals every address (privacy) and, with one leaked child key, the parent key.
- A lost passphrase means lost funds; nothing reports it as wrong.
- Use hardened levels as boundaries between accounts and services.
- Test with official vectors, never with a phrase that holds money.

## Exercise

1. Derive 20 deposit addresses from the account xpub into a `HashMap<String, u32>` for the indexer.
2. Remove the `assert!` in `recover_parent` and show that for a hardened child it returns a wrong key.
3. Compute the 24 word indexes from the entropy by hand and compare with `phrase()`.

## What's next

Next post: **AMMs and the constant-product formula**.
