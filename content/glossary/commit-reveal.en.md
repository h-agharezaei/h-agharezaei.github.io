+++
title = "Commit-reveal"
summary = "A two-step scheme: first publish a hash of your action, later reveal the action itself, so others cannot react to its content in advance."
category = "Blockchain"
related = ["front-running", "mev"]
posts = ["bc-mev-ordering"]
+++

The commitment usually includes a random salt so the hidden value cannot be guessed. It costs two transactions and a waiting period, and it helps against [front-running](/glossary/front-running/) only when the content is what can be exploited.
