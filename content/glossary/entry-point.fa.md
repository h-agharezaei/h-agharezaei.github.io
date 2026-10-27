+++
title = "entry point"
summary = "یک اتصال نام‌دار در metadata بسته؛ entry point های console_scripts هنگام نصب به دستور در PATH تبدیل می‌شوند."
category = "Python"
fa_title = "entry point"
related = ["wheel", "pyproject-toml"]
posts = ["py-packaging-publishing"]
+++

`[project.scripts]` با `greeter = "greeter:main"` باعث می‌شود نصب‌کننده دستور `greeter` را بسازد که `greeter.main()` را صدا می‌زند.
