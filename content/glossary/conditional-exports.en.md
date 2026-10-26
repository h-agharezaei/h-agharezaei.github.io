+++
title = "Conditional exports"
summary = "the `exports` field of `package.json`, which maps import paths to files and can pick a different file for `import` and `require`."
category = "Node.js"
related = ["esm", "commonjs"]
posts = ["node-modules-esm-cjs"]
+++

The `exports` field of `package.json`, which maps import paths to files and can pick a different file for `import` and `require`. Paths not listed in `exports` cannot be imported from outside the package.
