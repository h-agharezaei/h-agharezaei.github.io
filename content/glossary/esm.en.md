+++
title = "ESM"
summary = "the standard JavaScript module system (`import`/`export`), loaded asynchronously and analysed statically before any code runs."
category = "Node.js"
related = ["commonjs", "live-binding"]
posts = ["node-modules-esm-cjs"]
+++

The standard JavaScript module system (`import`/`export`), loaded asynchronously and analysed statically before any code runs. In Node.js a file is treated as ESM if it ends in `.mjs`, or ends in `.js` and the nearest `package.json` has `"type": "module"`.
