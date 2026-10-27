+++
title = "virtual environment"
summary = "An isolated folder with its own interpreter link and site-packages, so each project has its own dependencies."
category = "Python"
related = ["site-packages", "pip", "uv"]
posts = ["py-environment-uv-venv"]
+++

Created with `python3 -m venv .venv` or `uv venv`. Inside it, `sys.prefix` differs from `sys.base_prefix`. See also [site-packages](/glossary/site-packages/).
