+++
title = "Halting problem"
summary = "The proof that no general algorithm can decide, for every program and input, whether that program eventually stops."
category = "Blockchain"
related = ["turing-complete", "gas"]
posts = ["bc-evm-internals-rust"]
+++

So a node cannot look at arbitrary [Turing-complete](/glossary/turing-complete/) code and know in advance that it ends. Systems either forbid loops or meter execution, as Ethereum does with [gas](/glossary/gas/).
