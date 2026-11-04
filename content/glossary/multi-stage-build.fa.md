+++
title = "Multi-stage build"
fa_title = "build چندمرحله‌ای"
summary = "Dockerfile با چند مرحله‌ی FROM: مرحله‌ی اول کامپایلر دارد و برنامه را می‌سازد و مرحله‌ی آخر فقط نتیجه را در خود دارد."
category = "Rust"
related = ["musl", "container"]
posts = ["rust-docker-ci-release"]
+++

مرحله‌ی build می‌تواند یک image بزرگ با toolchain ‏Rust باشد. مرحله‌ی آخر از یک image کوچک شروع می‌شود، مثلاً `distroless/static`، و با `COPY --from=build` فقط باینری تمام‌شده را برمی‌دارد. کامپایلر و کد منبع و crateهای دانلودشده هیچ‌وقت به imageای که منتشر می‌کنید نمی‌رسند.
