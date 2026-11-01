+++
title = "EIP-55"
summary = "A checksum for Ethereum addresses encoded in the letter case of the hex string."
category = "Blockchain"
related = ["keccak-256"]
posts = ["bc-keys-ecdsa-addresses"]
+++

Hash the lowercase hex address with [Keccak-256](/glossary/keccak-256/); a letter is uppercase when the matching hash nibble is 8 or more. A typo then usually breaks the case pattern and is caught.
