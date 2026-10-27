+++
title = "Seam"
summary = "جایی که می‌توان رفتار را بدون ویرایش کدِ اطرافش عوض کرد."
category = "Engineering"
fa_title = "seam"
related = ["dependency-injection", "legacy-code", "characterization-test"]
posts = ["eng-legacy-code"]
+++

در Go یک seam معمولاً یک متغیر تابعی (`var now = time.Now`)، یک interface کوچک یا یک پارامتر است. تست چیزی را که پشت seam است، مثل ساعت یا دیتابیس، عوض می‌کند.
