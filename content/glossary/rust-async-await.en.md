+++
title = "async/await (Rust)"
summary = "Syntax for writing code that waits without blocking a thread: async fn makes a future, .await pauses until it is ready."
category = "Rust"
related = ["rust-future", "tokio"]
posts = ["rust-async-tokio"]
+++

Inside an `async fn`, `.await` is the point where the task may pause so the thread can run another task. Code between two `.await`s runs without interruption. Rust has no built-in executor, so async code needs a runtime crate to run it.
