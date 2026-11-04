+++
title = "Future (Rust)"
summary = "A value that stands for work that is not finished yet; an async fn returns one, and it does nothing until it is awaited or polled."
category = "Rust"
related = ["rust-async-await", "tokio"]
posts = ["rust-async-tokio"]
+++

Calling an `async fn` does not run its body. It returns a `Future`, and the body runs only when something polls it, usually through `.await` inside another async function or through a runtime such as Tokio. A future you never await simply never runs; the compiler warns about it.
