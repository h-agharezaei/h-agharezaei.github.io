+++
title = "Tolerant reader"
summary = "کلاینتی که فیلدهای ناشناخته را نادیده می‌گیرد، پس تغییر افزایشی API آن را نمی‌شکند."
category = "Engineering"
fa_title = "خواننده‌ی بردبار"
related = ["semver"]
posts = ["eng-api-design-versioning-pagination"]
+++

tolerant reader فقط فیلدهای لازم را برمی‌دارد و بقیه را نادیده می‌گیرد؛ پس اضافه‌کردن فیلد به پاسخ تغییری ایمن و غیرشکننده است. decoder سخت‌گیر که فیلد ناشناخته را رد می‌کند همان تغییر را به قطعی تبدیل می‌کند.
