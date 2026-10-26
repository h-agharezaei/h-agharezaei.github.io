+++
title = "Tombstone"
summary = "A marker left in an open-addressing table when an entry is deleted, so lookups keep probing past it."
category = "Algorithms"
related = ["hash-table", "linear-probing"]
posts = ["algo-hash-tables"]
+++

If a deleted slot were simply emptied, a key that was placed after it by probing would become unreachable. A tombstone keeps the chain intact; a later insert may reuse it, and a rehash drops them all.
