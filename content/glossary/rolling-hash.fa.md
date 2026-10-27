+++
title = "Rolling hash"
fa_title = "هش غلتان"
summary = "هشِ یک پنجره‌ی لغزان که با حذف نویسه‌ی قدیمی و افزودن نویسه‌ی جدید در O(1) به‌روز می‌شود."
category = "Algorithms"
related = ["rabin-karp", "hash-collision"]
posts = ["algo-string-algorithms"]
+++

با پایه‌ی b و پیمانه‌ی q به‌روزرسانی چنین است: h = ((h - old * b^(m-1)) * b + new) mod q. پنجره‌های برابر همیشه هش برابر دارند؛ پنجره‌های متفاوت هم ممکن است (برخورد).
