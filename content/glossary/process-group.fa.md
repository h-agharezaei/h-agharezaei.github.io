+++
title = 'Process group'
summary = 'مجموعه‌ای از پروسه‌های مرتبط (مثلاً یک pipeline) که می‌توانند با هم سیگنال بگیرند.'
category = 'Linux'
fa_title = 'گروه پروسه'
related = ["process", "signal"]
posts = ["linux-processes-signals"]
+++

مجموعه‌ای از پروسه‌های مرتبط (مثلاً یک pipeline) که می‌توانند با هم سیگنال بگیرند. با `kill -- -PGID` به کل گروه سیگنال می‌رسد. یک session تازه (`setsid`) گروه تازه می‌سازد.
