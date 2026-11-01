+++
title = "Cheatcode"
summary = "A special call in a Foundry test that changes the test EVM: set balances, impersonate senders, expect reverts or events."
category = "Blockchain"
related = ["foundry", "invariant-testing"]
posts = ["bc-foundry-testing-fuzzing"]
+++

Cheatcodes are called on the `vm` object, for example `vm.deal`, `vm.prank`, `vm.expectRevert` and `vm.expectEmit`. They exist only in the test environment of [Foundry](/glossary/foundry/), not on a real chain.
