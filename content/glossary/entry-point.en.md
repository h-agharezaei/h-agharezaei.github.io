+++
title = "entry point"
summary = "A named hook in a package's metadata; console_scripts entry points become commands on PATH when the package is installed."
category = "Python"
related = ["wheel", "pyproject-toml"]
posts = ["py-packaging-publishing"]
+++

`[project.scripts]` with `greeter = "greeter:main"` makes the installer create a `greeter` command that calls `greeter.main()`.
