+++
title = ".gitignore"
fa_title = ".gitignore"
summary = "فایلی از الگوها که به گیت می‌گوید کدام فایل‌های untracked را نادیده بگیرد."
category = "Git"
related = ["staging-area"]
posts = ["git-index-staging"]
+++

ignore فقط روی فایل‌های untracked اثر دارد. فایلی که از قبل tracked است تا `git rm --cached` همچنان tracked می‌ماند. `git check-ignore -v` نشان می‌دهد کدام قانون مطابقت دارد.
