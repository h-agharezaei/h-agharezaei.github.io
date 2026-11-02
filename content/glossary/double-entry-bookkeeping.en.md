+++
title = "Double-entry bookkeeping"
summary = "Recording every movement of money as entries on at least two accounts that sum to zero, so value is never created or lost silently."
category = "Engineering"
related = ["idempotency", "audit-log"]
posts = ["bc-exchange-deposits-withdrawals"]
+++

Instead of updating one balance column, each business event writes a journal whose entries cancel out: a deposit adds to the user's account and subtracts from an `external` account. A balance is the sum of an account's entries, the history is never overwritten, and a non-zero total across all accounts means a bug.
