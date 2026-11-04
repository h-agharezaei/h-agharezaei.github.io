+++
title = "wasm-bindgen"
summary = "A crate and a command-line tool that generate the JavaScript glue needed to pass strings and objects between Rust compiled to wasm and JavaScript."
category = "Rust"
related = ["webassembly"]
posts = ["rust-wasm"]
+++

Raw wasm can only pass numbers. You mark a Rust function with `#[wasm_bindgen]`, build for `wasm32-unknown-unknown`, and run the `wasm-bindgen` command on the result; it writes a `.wasm` file, a JavaScript wrapper and a TypeScript declaration file. The wrapper handles copying strings in and out of the module's memory. According to its docs, the command-line tool and the crate must be the same version.
