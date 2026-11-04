+++
title = "Multi-stage build"
summary = "A Dockerfile with several FROM stages: the first has the compiler and builds the program, the last contains only the result."
category = "Rust"
related = ["musl", "container"]
posts = ["rust-docker-ci-release"]
+++

The build stage can be a large image with the Rust toolchain. The final stage starts from a small image, for example `distroless/static`, and uses `COPY --from=build` to take only the finished binary. The compiler, the sources and the downloaded crates never reach the image you ship.
