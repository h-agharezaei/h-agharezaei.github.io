+++
title = "Invariant testing"
summary = "Calling random sequences of functions and checking after each call that a property of the whole system still holds."
category = "Blockchain"
related = ["fuzzing", "invariant", "shrinking", "property-based-testing"]
posts = ["bc-foundry-testing-fuzzing", "bc-erc20-erc721"]
+++

A stateful form of [fuzzing](/glossary/fuzzing/). Example: a token's total supply equals the sum of all balances. A handler contract usually turns random input into valid calls; a failing sequence is shrunk to a short counterexample.
