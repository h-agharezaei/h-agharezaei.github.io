+++
title = "sdist"
summary = "توزیع سورس یک بسته‌ی Python: آرشیو سورس به‌همراه metadata که در صورت نیاز هنگام نصب به wheel ساخته می‌شود."
category = "Python"
fa_title = "sdist"
related = ["wheel", "pypi", "pyproject-toml"]
posts = ["py-packaging-publishing"]
+++

`uv build` یک sdist با پسوند `.tar.gz` و یک wheel کنار هم می‌سازد. ابزار نصب wheel مناسب را ترجیح می‌دهد و در غیر این صورت به sdist برمی‌گردد.
