+++
title = "Key custody"
summary = "Who holds the private keys that move funds, where they live, and who may ask for a signature."
category = "Blockchain"
related = ["hot-wallet", "signing-service", "hsm", "mpc"]
posts = ["bc-capstone"]
+++

Key custody is the part of a wallet system that holds the private keys. A common design keeps keys in as few places as possible, behind a narrow [signing service](/glossary/signing-service/), in hardware such as an [HSM](/glossary/hsm/) or split with [MPC](/glossary/mpc/). Whoever controls custody controls the funds.
