+++
title = "pth file"
summary = "A .pth file in site-packages: Python reads it at startup, adds its paths to sys.path and runs any line that starts with import."
category = "Python"
related = ["wheel", "pypi"]
posts = ["agent-framework-pypi-compromise-2026"]
+++

It exists so packages can extend the import path. The `import` rule means it can also run arbitrary code every time any Python interpreter starts in that environment, without anyone importing the package. `python -S` skips it.
