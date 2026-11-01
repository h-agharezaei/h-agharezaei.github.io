+++
title = "Proposer-builder separation"
summary = "Splitting block production so specialized builders assemble and order blocks and the proposing validator picks one, usually by highest bid."
category = "Blockchain"
related = ["mev", "proof-of-stake", "validator"]
posts = ["bc-mev-ordering"]
+++

On Ethereum this is commonly done outside the protocol with software such as MEV-Boost, as I understand it. It moves ordering power to builders; it does not remove it. See [validator](/glossary/validator/).
