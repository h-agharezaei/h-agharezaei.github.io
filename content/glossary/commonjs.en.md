+++
title = "CommonJS"
summary = "the original Node.js module system: `require()` loads a file synchronously and `module.exports` is what it hands back."
category = "Node.js"
related = ["esm"]
posts = ["node-modules-esm-cjs"]
+++

The original Node.js module system: `require()` loads a file synchronously and `module.exports` is what it hands back. Each CommonJS module is evaluated once and cached in `require.cache`.
