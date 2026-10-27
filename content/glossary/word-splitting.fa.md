+++
title = "Word splitting"
summary = "مرحله‌ای در shell که یک expansion بدون quote را به چند کلمه‌ی جدا می‌شکند."
category = "Linux"
fa_title = "word splitting"
related = ["xargs", "exit-status"]
posts = ["linux-scripting-cron-safely"]
+++

بعد از expand شدن متغیر، shell نتیجه را روی space، tab و newline (همان IFS) می‌شکند و بعد globbing را اعمال می‌کند. نوشتن "$var" هر دو را متوقف می‌کند.
