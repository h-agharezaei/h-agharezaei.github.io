+++
title = "Path traversal"
summary = "باگی که در آن `../` در ورودی کاربر باعث می‌شود handler فایلی بیرون از پوشه‌ی مجاز را بخواند."
category = "Security"
fa_title = "Path traversal"
related = ["command-injection"]
posts = ["sec-injection-xss"]
+++

چسباندن ورودی کاربر به یک پوشه‌ی پایه کافی نیست، چون مسیر ترکیبی پاک‌سازی می‌شود و می‌تواند از پوشه بالا برود. نتیجه را با پایه مقایسه کنید یا بهتر است از `os.OpenRoot` استفاده کنید که symlinkهای به بیرون را هم می‌بندد.
