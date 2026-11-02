+++
title = "P2PKH"
summary = "Pay to public key hash: a Bitcoin lock that requires a public key matching a stored HASH160 and a valid signature from that key."
category = "Blockchain"
related = ["bitcoin-script", "ecdsa", "digital-signature"]
posts = ["bc-bitcoin-script-rust"]
+++

The locking script is `OP_DUP OP_HASH160 <pubkey hash> OP_EQUALVERIFY OP_CHECKSIG` and the spender provides `<sig> <pubkey>`. HASH160 is RIPEMD-160 of SHA-256. See [Bitcoin Script](/glossary/bitcoin-script/).
