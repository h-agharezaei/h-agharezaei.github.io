+++
title = "State machine"
summary = "A model where an entity is always in one of a fixed set of states and may only move along explicitly allowed transitions."
category = "Engineering"
related = ["idempotency"]
posts = ["bc-exchange-deposits-withdrawals"]
+++

Writing the allowed transitions down (for example `pending -> credited`, but never `credited -> pending`) turns many bugs into loud errors. In a database, guard each update with the expected current state: `UPDATE ... SET status = 'credited' WHERE status = 'pending'`.
