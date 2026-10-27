+++
title = "sdist"
summary = "The source distribution of a Python package: an archive of the sources plus metadata, built into a wheel at install time if needed."
category = "Python"
related = ["wheel", "pypi", "pyproject-toml"]
posts = ["py-packaging-publishing"]
+++

`uv build` produces a `.tar.gz` sdist and a `.whl` wheel side by side. Installers prefer a matching wheel and fall back to the sdist.
