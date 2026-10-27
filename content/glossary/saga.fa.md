+++
title = "Saga"
summary = "یک تراکنش طولانی کسب‌وکاری که به چند تراکنش محلی شکسته می‌شود و هر کدام یک کار جبرانی دارد که اگر قدم بعدی شکست خورد آن را خنثی می‌کند."
category = "Distributed"
fa_title = "saga"
related = ["two-phase-commit", "compensating-transaction", "idempotency"]
posts = ["ds-saga-vs-2pc"]
+++

saga ایزولاسیون را کنار می‌گذارد: دیگران می‌توانند حالت‌های میانی را ببینند. اجرای آن یا با یک orchestrator است که state machine را ذخیره می‌کند، یا با واکنش سرویس‌ها به eventهای هم (choreography).
