+++
title = "lockfile"
summary = "A file that records the exact versions, download URLs and hashes of every installed dependency."
category = "Node.js"
related = ["npm", "semver", "transitive-dependency"]
posts = ["node-npm-package-json", "py-environment-uv-venv"]
+++

In npm it is `package-lock.json`. Committing it makes every machine and CI run install the same tree, and `npm ci` refuses to run if it disagrees with `package.json`.
