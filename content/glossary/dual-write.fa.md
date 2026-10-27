+++
title = "Dual write"
summary = "نوشتن هم‌زمان شکل قدیم و جدید داده."
category = "Distributed"
fa_title = "نوشتن دوگانه"
related = ["expand-contract", "backfill"]
posts = ["ds-deployment-strategies"]
+++

در طول migration کد جدید هم ستون قدیمی و هم ستون جدید را می‌نویسد تا نسخه‌ی قدیم و جدید هر دو ردیف‌ها را بخوانند. نوشتن دوگانه در دو سیستم جدا چیز دیگر و پرخطرتر است، چون تراکنش مشترکی وجود ندارد.
