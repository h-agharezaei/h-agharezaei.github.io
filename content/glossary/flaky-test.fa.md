+++
title = "Flaky test"
summary = "تستی که بدون تغییر کد گاهی می‌گذرد و گاهی رد می‌شود."
category = "Engineering"
fa_title = "تست flaky"
related = ["dependency-injection", "test-pyramid"]
posts = ["eng-testing-pyramid-tdd", "eng-property-based-testing"]
+++

علت‌های رایج: زمان واقعی، تصادف، state مشترک و زمان‌بندی بین goroutineها. تست flaky آدم‌ها را به نادیده گرفتن build قرمز عادت می‌دهد؛ پس بهتر است زود درستش کنید، مثلاً با تزریق ساعت.
