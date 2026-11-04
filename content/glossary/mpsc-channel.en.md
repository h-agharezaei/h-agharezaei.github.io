+++
title = "Channel (mpsc)"
summary = "A queue between threads in std::sync::mpsc: many producers (cloned senders), one consumer."
category = "Rust"
related = ["os-thread", "send-and-sync"]
posts = ["rust-concurrency-threads"]
+++

`mpsc::channel()` returns a sender and a receiver. Sending moves the value to the receiver, so the sender cannot use it afterwards. The receiver's loop ends when every sender, including the original, has been dropped.
