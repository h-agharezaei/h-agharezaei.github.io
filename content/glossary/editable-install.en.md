+++
title = "editable install"
summary = "Installing a project so the environment points at your working copy instead of a copied snapshot, so edits apply immediately."
category = "Python"
related = ["wheel", "virtual-environment", "uv"]
posts = ["py-packaging-publishing"]
+++

Done with `uv pip install -e .` (or `pip install -e .`). Imported modules then resolve to the files under your `src/` directory.
