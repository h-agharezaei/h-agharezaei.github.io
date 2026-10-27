+++
title = 'monkeypatch'
fa_title = 'monkeypatch'
summary = 'جایگزینی موقت یک attribute، متغیر محیطی یا کلید دیکشنری در طول تست'
category = 'Python'
related = ["fixture", "test-double"]
posts = ["py-testing-pytest"]
+++

**monkeypatch** یک fixture در pytest است که مواردی مثل متغیر محیطی، attribute یا کلید دیکشنری را فقط در طول یک تست عوض می‌کند و بعد همه‌چیز را برمی‌گرداند. این کار جلوی نشت state بین تست‌ها را می‌گیرد.
