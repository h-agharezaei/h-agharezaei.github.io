+++
title = 'Fixture'
fa_title = 'فیکسچر'
summary = 'تابعی که چیزهای موردنیاز تست را آماده و پس از آن پاک‌سازی می‌کند'
category = 'Python'
related = ["test-double", "context-manager"]
posts = ["py-testing-pytest"]
+++

**fixture** در pytest تابعی است که با `@pytest.fixture` علامت خورده. تست با نوشتن نامش در پارامترها آن را می‌خواهد و pytest اول آن را اجرا و نتیجه را پاس می‌دهد. با `yield`، کد بعد از آن به‌عنوان teardown اجرا می‌شود. scope (function، module، session) تعیین می‌کند هر چند وقت یک‌بار ساخته شود.
