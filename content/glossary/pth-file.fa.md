+++
title = "pth file"
summary = "فایل .pth در site-packages: Python هنگام شروع آن را می‌خواند، مسیرهایش را به sys.path اضافه می‌کند و هر خطی را که با import شروع شود اجرا می‌کند."
category = "Python"
fa_title = "فایل pth"
related = ["wheel", "pypi"]
posts = ["agent-framework-pypi-compromise-2026"]
+++

برای این ساخته شده که بسته‌ها مسیر import را گسترش دهند. قاعده‌ی `import` یعنی می‌تواند هر بار که هر مفسر Python در آن محیط شروع به کار کند هم کد دلخواه اجرا کند، بی‌آنکه کسی بسته را import کرده باشد. `python -S` آن را نادیده می‌گیرد.
