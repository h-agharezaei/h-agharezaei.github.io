+++
title = "Subpath imports"
summary = "The `imports` field of package.json: private aliases that start with `#` and map to files."
category = "Node.js"
related = ["esm"]
posts = ["node-project-structure-config"]
+++

The `imports` field of package.json: private aliases that start with `#` and map to files. `import x from '#config'` resolves through package.json, so you avoid long `../../` paths. Aliases only work inside your own package.
