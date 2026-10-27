+++
title = "Daemon thread"
summary = "threadی که برنامه را زنده نگه نمی‌دارد: وقتی فقط thread‌های daemon مانده باشند process تمام می‌شود."
category = "Python"
fa_title = "ترد daemon"
related = ["thread"]
posts = ["py-gil-threading"]
+++

در Python، `Thread(daemon=True)` هنگام خروج interpreter ناگهان متوقف می‌شود و `finally` و cleanup آن ممکن است هرگز اجرا نشود. برای توقف مؤدبانه از `Event` استفاده کنید.
