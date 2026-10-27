+++
title = "inline script metadata"
summary = "PEP 723: a comment block at the top of a single-file script that lists its dependencies and Python version."
category = "Python"
related = ["virtual-environment", "pyproject-toml"]
posts = ["py-cli-scripts"]
+++

A `# /// script` comment block holds TOML such as `dependencies = [...]`. Tools like `uv run script.py` read it, build a cached environment and run the script, so one file can carry its own requirements.
