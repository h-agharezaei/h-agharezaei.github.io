+++
title = "rebase"
fa_title = "rebase"
summary = "commitهای شما را روی یک پایه‌ی دیگر دوباره اجرا می‌کند و commitهای جدید با hash جدید می‌سازد."
category = "Git"
related = ["merge", "force-push", "fast-forward"]
posts = ["git-merge-vs-rebase", "git-resolve-conflicts"]
+++

rebase commitهای branch شما را یکی‌یکی روی commit دیگری دوباره اعمال می‌کند. نتیجه یک خط مستقیم است، ولی هر commit بازپخش‌شده یک شیء جدید است و hash آن عوض می‌شود. برای همین rebase کردن commitهایی که دیگران دارند خطرناک است.
