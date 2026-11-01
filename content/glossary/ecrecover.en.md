+++
title = "ecrecover"
summary = "The EVM precompile that returns the address that produced an ECDSA signature over a 32-byte hash."
category = "Blockchain"
related = ["ecdsa", "digital-signature", "signature-malleability"]
posts = ["bc-bridges-cross-chain"]
+++

It returns the zero address for an invalid signature instead of failing, so callers must check for it. Contracts usually also reject the high-`s` twin of a signature (see [signature malleability](/glossary/signature-malleability/)).
