+++
title = "Cancellation by drop"
summary = "In async Rust you cancel a future by dropping it; it simply stops at its current .await and its local values are destroyed."
category = "Rust"
related = ["rust-future", "tokio"]
posts = ["rust-async-tokio"]
+++

`select!` and `timeout` cancel the futures that lose by dropping them. The code after the pending `.await` never runs, so cleanup must live in `Drop` implementations, not in statements after an await.
