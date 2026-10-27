+++
title = "Semver"
summary = "A versioning scheme MAJOR.MINOR.PATCH, plus the range syntax (`^`, `~`) npm uses to pick versions."
category = "Node.js"
related = ["npm", "lockfile"]
posts = ["node-npm-package-json", "py-packaging-publishing"]
+++

By convention a patch release fixes bugs, a minor release adds features compatibly, and a major release may break the API. A range such as `^1.2.3` accepts any version from 1.2.3 up to, but not including, 2.0.0.
