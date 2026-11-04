+++
title = "Span (tracing)"
summary = "A period of time with named fields, created with the tracing crate; every event logged inside it carries its fields automatically."
category = "Rust"
related = ["tracing-subscriber", "rust-future"]
posts = ["rust-tracing-observability"]
+++

A span is like a label you put on a stretch of work, for example `request{request_id="req-7"}`. While the span is active, every log event inside it is printed together with the span's fields. In async code the span follows its task across `.await` points, so lines from different tasks can be told apart even when they are interleaved. Spans can be nested: a `charge` span inside a `handle` span.
