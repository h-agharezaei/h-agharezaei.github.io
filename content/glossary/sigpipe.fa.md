+++
title = 'SIGPIPE'
summary = 'سیگنالی که پروسه هنگام نوشتن در pipeی با خواننده‌ی بسته می‌گیرد (سیگنال ۱۳).'
category = 'Linux'
fa_title = 'SIGPIPE'
related = ["pipe", "signal"]
posts = ["linux-processes-signals"]
+++

سیگنالی که پروسه هنگام نوشتن در pipeی با خواننده‌ی بسته می‌گیرد (سیگنال ۱۳). به همین دلیل `yes | head -1` می‌ایستد: `yes` با SIGPIPE تمام می‌شود و وضعیت ۱۴۱ دیده می‌شود.
