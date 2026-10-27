+++
title = 'Parametrized test'
fa_title = 'تست پارامتری'
summary = 'یک بدنه‌ی تست که روی چند ردیف ورودی اجرا می‌شود'
category = 'Python'
related = ["fixture"]
posts = ["py-testing-pytest"]
+++

**تست پارامتری** یک تابع تست را برای هر ردیف از ورودی و خروجی مورد انتظار یک‌بار اجرا می‌کند و هر ردیف را تست جدا گزارش می‌دهد. در pytest با `@pytest.mark.parametrize` انجام می‌شود و معادل table-driven test در Go است.
