+++
date = '2026-11-21T18:00:00+03:30'
draft = false
title = 'HD wallets: BIP-32, BIP-39 and BIP-44 in Rust'
description = 'HD wallets in Rust: BIP-39 words to seed, BIP-32 checked against test vectors, BIP-44 Ethereum addresses, watch-only xpub servers and the xpub leak.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "hd-wallet", "bip32", "bip39", "ethereum"]
cover = { image = "/images/covers/bc-hd-wallets-rust.png", alt = "HD wallets: BIP-32, BIP-39 and BIP-44 in Rust", hiddenInSingle = true }
+++

An exchange needs a deposit address for every user, the same kind of address that [the previous post's indexer](/posts/bc-event-indexer-go/) watches. The simplest way is to make a random private key per address, as in [the keys post](/posts/bc-keys-ecdsa-addresses/). But that means a new key with every signup, which must be stored and backed up somewhere. After a year you have a server full of private keys, and every backup is one more place for them to leak.

An {{< term "hd-wallet" "HD wallet" >}} (HD stands for hierarchical deterministic) solves both problems with one idea: **start from one secret and build a whole tree of keys with a formula.** Because the formula is deterministic, you can rebuild the same keys whenever you want, so that one secret is all you have to keep. And there is a second property that is gold for an exchange: it has a public half that creates new addresses **without any private key**. The server that hands out deposit addresses no longer needs to hold a private key. This fits the hot/cold split from [the Binance hack post](/posts/binance-hack-hot-wallet-2026/).

This post walks through three standards step by step: BIP-39 (from a few words to a seed), BIP-32 (from the seed to a tree of keys) and BIP-44 (which branch of the tree is for what). I checked every step against the official test data of that standard.

> Every mnemonic, seed and address on this page comes from **public test vectors**, and anyone can compute their keys: never send money to them. Rust 1.90, `bip32` 0.5.3 (iqlusion), `k256` 0.13.4, `pbkdf2` 0.12.2, `hmac` 0.12.1, `sha2` 0.10.9, `sha3` 0.10.9 and `hex` 0.4.3 on macOS (arm64). The demo is a local Cargo project.

## BIP-39: from words to a seed

Our starting secret is some random bytes (called entropy), but raw bytes are not something people can store or write down. {{< term "bip-39" "BIP-39" >}} turns them into 24 English words that you can write on paper. Those 24 words are called a mnemonic. The conversion goes like this:

1. Take random entropy (here 256 bits).
2. Compute its SHA-256 and append the first 8 bits to the end as a checksum (control bits). Now you have 264 bits.
3. Cut the 264 bits into 24 pieces of 11 bits. Each piece is a number from 0 to 2047, the index of a word in a fixed list of 2048 words.

To see it, I took the official vector with all-zero entropy from the crate's test file (copied from Trezor's `vectors.json`). The code I ran:

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

Line 1: the entropy is all zeros, so the first 11-bit pieces are zero too, and word number 0 in the list is `abandon`. Line 2 explains why the last word is different: word 24 is made of the last 3 zero bits of the entropy plus the 8 checksum bits. The checksum byte is `0x66`, which is 102, and word number 102 is `art`.

Line 3 shows what the checksum is for: I changed the last word (`art` to `abandon`) and the library rejected the phrase. The crate returns one generic `Bip39` error, and as far as I saw it supports only 24-word phrases. Because the checksum is only 8 bits, this protection is not complete: I expect about one in 256 mistakes to slip through silently. A typo is usually caught, but it is not guaranteed.

Next step: from the words to a seed. According to BIP-39, the seed is the result of {{< term "pbkdf2" "PBKDF2" >}}-HMAC-SHA512: the phrase itself as the password, the string `"mnemonic" + passphrase` as the salt, and 2048 rounds. The passphrase is an optional extra password you choose. To be sure I understood this, I also computed it by hand and compared it with the library's output:

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

- **`seed matches vector: true`:** the seed (64 bytes, only the first 16 hex characters printed) equals Trezor's published value.
- **`manual PBKDF2 == seed: true`:** my hand computation equals the library.
- **`seed with empty passphrase`:** the same words with an empty passphrase give a completely different seed. A different passphrase means a different wallet.
- **`root xprv matches vector: true`:** the root key of the tree was built from this seed (explained in the next section) and equals the published value.

A note on the passphrase: there is no such thing as a "wrong passphrase". Every passphrase makes a valid wallet, just perhaps an empty one. So if you forget it, your money sits in a wallet you can never find again. The 2048 rounds, as in [storing passwords safely](/posts/sec-password-hashing/), only slow down guessing; the real protection is the entropy.

## BIP-32: master key, chain code and children

Now we build a tree of keys from the seed. {{< term "bip-32" "BIP-32" >}} runs an {{< term "hmac" "HMAC" >}}-SHA512 over the seed (a keyed hash function with 64 bytes of output). The left half of the output (32 bytes) is the master private key and the right half is the **chain code**, a 32-byte value that is not a key but enters every derivation.

A child is made the same way: another HMAC-SHA512, this time with the parent's chain code as the key and data built from the parent's key and the child's number. The output is split in two again. The left half (call it `IL`) is added to the parent's private key (modulo n, the size of the curve's group) and becomes the child's private key. The right half becomes the child's chain code. A key and its chain code together form an "extended key", whose text form starts with `xprv`; on the public side it is called an {{< term "xpub" "xpub" >}}.

Pay attention to one important detail. Child numbers come in two kinds. For **normal** numbers, the HMAC input contains the parent's *public* key. For {{< term "hardened-derivation" "hardened" >}} numbers (written with a `'`, and 2^31 or above), the input is the parent's *private* key. The difference matters later.

To check this I used test vector 1 from BIP-32 itself (seed `000102...0f`; the expected values come from the spec and the crate's tests):

```
chain code: 873dff81c02f525623fd1fe5167eac3a55a049de3d314bb42ee227ffed37d508
m xprv matches: true
m/0'/1 from xpub only matches: true
xpub -> hardened child: Some(ChildNumber)
```

- **First line:** the root's chain code (the root is `m`).
- **`m xprv matches`:** the root key equals the spec.
- **`m/0'/1 from xpub only matches`:** this line is the heart of it. I took the key `m/0'` only as an xpub (no private key) and derived child number 1 from it. The result equals the spec's published value. That is the "public half". Why does it work? A public key is a curve point (private key times the base point, [keys post](/posts/bc-keys-ecdsa-addresses/)), and adding `IL` to a private key corresponds to adding `IL × base point` to the public key. So anyone who holds the xpub can compute the child's public key without seeing a private key.
- **`xpub -> hardened child`:** for a hardened number the same thing fails with an error, because the HMAC input is the parent's private key, which an xpub does not have.

## Why hardened matters

If children can be derived from an xpub, the xpub looks safe: it only gives addresses. But there is a trap. In normal derivation `k_child = IL + k_parent (mod n)`, and `IL` needs only the parent's xpub. So if someone has the parent's xpub and the private key of **one** normal child leaks, one subtraction gives the parent's own private key: `k_parent = k_child - IL`. The code is just that formula:

```rust
let mut mac = Hmac::<Sha512>::new_from_slice(&parent.attrs().chain_code).unwrap();
mac.update(&parent.to_bytes()); // 33-byte compressed public key
mac.update(&index.to_be_bytes());
let i = mac.finalize().into_bytes();
let il = <Scalar as Reduce<U256>>::reduce_bytes(i[..32].into());
let kc = <Scalar as Reduce<U256>>::reduce_bytes(child_priv.into());
(kc - il).to_bytes().into()
```

To try it, I "leaked" the key `m/44'/60'/0'/0/3` and climbed two steps with the xpubs, first to `m/44'/60'/0'/0` and then to `m/44'/60'/0'`:

```
recovered m/44'/60'/0' private key == real: true
```

So from one leaked child key I got the private key of the whole account, and with it every child becomes spendable. The climb stops at `0'`, because `0'` is hardened: there `IL` was built from the parent's private key, which the xpub does not give. That is why hardened levels work like a firewall between branches.

## BIP-44 and the Ethereum address

Now a convention, so that wallets lay out the tree in the same way. {{< term "bip-44" "BIP-44" >}} defines a fixed path: `m / 44' / coin' / account' / change / index`. For Ethereum `coin` is 60. The parts from `44'` to `account'` are hardened, and `change` and `index` are normal. Usually `change` is 0 (external addresses) and `index` is the address number.

From the key at each path, the Ethereum address is made with the same rule as in [the keys post](/posts/bc-keys-ecdsa-addresses/): Keccak-256 of the uncompressed public key, the last 20 bytes, and upper/lower-case letters according to {{< term "eip-55" "EIP-55" >}}. To check the code, I tried private key 1, whose well-known address is `0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf`, and got exactly that.

Now the main experiment: I computed the addresses of the first three users once from the xpub (watch-only derivation) and once from the full private key, and compared:

```
account xpub: xpub6DGfjznv...EajsXn
m/44'/60'/0'/0/0  0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655  same as xprv: true
m/44'/60'/0'/0/1  0xAbc76C2f6D144fA6Fe17bb6CA0e6D81a38Daa353  same as xprv: true
m/44'/60'/0'/0/2  0x7375C7Ea6F22Dd15A36DAC44E906a83991a75701  same as xprv: true
```

(I print the xpub shortened: the first 12 and the last 6 characters.) All three addresses are the same by both routes. I did not compare these three addresses against another wallet.

## A watch-only deposit server

With these pieces, the design I would pick for exchange deposits is:

- An offline machine creates the seed and hands out only the account's xpub.
- The deposit service stores `(user_id, index, address)` with `address = xpub/0/index`. There is no private key on this service.
- The indexer from the previous post watches those same addresses.
- A separate signer moves the money: a small online {{< term "hot-wallet" "hot wallet" >}}, and the rest cold.

Be careful not to mix the two roles. The attack in the previous section needs the parent's xpub and the private key of one of its normal children. So the xpub you put on the deposit server must not be the parent of keys that sign somewhere else, on an online machine. Keep these two jobs in separate accounts; the boundary between accounts is hardened, and the attack cannot cross it.

## How keys leak or get lost

- **A mnemonic is all the keys at once.** Not in logs, not in screenshots, not in cloud notes.
- **An xpub reveals every address of the account** (bad for privacy), and with one leaked normal child key, the parent's key too.
- **A lost passphrase means lost money.** There is no recovery.
- **Make the hardened levels the boundary between accounts and services.**
- **Test with the official vectors, never with a phrase that holds money.**

## Exercise

1. Derive twenty deposit addresses from the xpub and keep them in a `HashMap<String, u32>` for the indexer.
2. Remove the `assert!` from `recover_parent` and show that it returns a wrong key for a hardened child.
3. Compute word 24 by hand from the entropy and compare it with `phrase()`.

## What's next

The next post is "AMMs and the constant-product formula": so far we worked with keys, addresses and transfers, and from there the series enters DeFi, programs that build a market on top of those same transfers.
