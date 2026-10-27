+++
title = "lockfile"
summary = "فایلی که نسخه‌ی دقیق، آدرس دانلود و hash همه‌ی وابستگی‌های نصب‌شده را ثبت می‌کند."
category = "Node.js"
fa_title = "lockfile"
related = ["npm", "semver", "transitive-dependency"]
posts = ["node-npm-package-json", "py-environment-uv-venv", "py-packaging-publishing", "sec-supply-chain-vulns", "linux-scripting-cron-safely"]
+++

در npm همان `package-lock.json` است. با commit کردنش همه‌ی ماشین‌ها و CI یک درخت وابستگی یکسان نصب می‌کنند و `npm ci` اگر با `package.json` هم‌خوان نباشد اجرا نمی‌شود.
