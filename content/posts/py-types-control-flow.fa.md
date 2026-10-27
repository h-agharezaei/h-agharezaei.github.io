+++
date = '2027-01-18T10:00:00+03:30'
draft = false
title = 'نوع‌ها و کنترل جریان در Python'
description = 'نوع‌ها و کنترل جریان در Python برای برنامه‌نویس‌های Go و Node.js: تایپ پویا اما قوی، int، float، str، reference، for-else و match روی 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/py-types-control-flow.fa.png", alt = "نوع‌ها و کنترل جریان در Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-environment-uv-venv/) محیط Python را با venv و uv آماده کردیم. حالا سراغ اجزای پایه می‌رویم: نوع‌ها، نام‌ها و کنترل جریان. اگر مثل من از Go آمده‌اید، بزرگ‌ترین تغییر این است که نوع روی مقدار است، نه روی متغیر. مقایسه با [نوع‌ها و کنترل جریان در Go](/fa/posts/go-types-control-flow/) را فقط جایی آورده‌ام که از واقعیتش مطمئنم.

> همه‌ی مثال‌ها با Python 3.14.0 روی macOS اجرا شده‌اند (`python3 --version` همین را چاپ می‌کند). فایل‌های دمو اسکریپت‌های محلی `basics.py` و `flow.py` هستند. برای خطاهای syntax فقط خط آخر خروجی را آورده‌ام.

## پویا، اما قوی

یک نام می‌تواند به هر مقداری اشاره کند، ولی Python بین نوع‌های نامرتبط خودش تبدیل نمی‌کند:

```python
try:
    1 + '1'
except TypeError as e:
    print("TypeError:", e)
```

```text
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

این بررسی موقع اجرا انجام می‌شود، نه موقع کامپایل. تفاوتش با Go همین است که همین اشتباه در Go خطای کامپایل است.

## عددها

`int` عدد صحیح با دقت دلخواه ({{< term "arbitrary-precision" "arbitrary precision" >}}) است: `2**200` بدون مشکل کار می‌کند، در حالی که `int` در Go عرض ثابت دارد.

```text
>>> 2**200
1606938044258990275541962092341162602522202993782792835301376
>>> 0.1 + 0.2
0.30000000000000004
>>> 0.1 + 0.2 == 0.3
False
>>> Decimal('0.1') + Decimal('0.2')
Decimal('0.3')
>>> Fraction(1, 10) + Fraction(2, 10)
Fraction(3, 10)
```

`float` همان ممیز شناور دودویی معمول است، پس `0.1 + 0.2` دقیق نیست. برای پول از `decimal.Decimal` استفاده کنید (از رشته بسازید، نه از float) و برای نسبت‌های دقیق از `fractions.Fraction`.

## رشته و bytes

`str` دنباله‌ی تغییرناپذیر از کاراکترهای Unicode است. `bytes` نوع جداگانه‌ای است و هیچ‌وقت با `str` برابر نمی‌شود:

```python
s = 'سلام'
print(len(s), len(s.encode()), s.encode())
print(s[1:3], s[::-1])
s[0] = 'x'
print(b'abc'[0], 'abc'.encode() == b'abc', 'abc' == b'abc')
```

```text
4 8 b'\xd8\xb3\xd9\x84\xd8\xa7\xd9\x85'
لا مالس
TypeError: 'str' object does not support item assignment
97 True False
```

چهار کاراکتر، هشت بایت UTF-8. برخلاف Go، اندیس‌گذاری روی `str` کاراکتر برمی‌گرداند، پس `len` و slice مستقیم روی متن کار می‌کنند. `s[1:3]` و `s[::-1]` روی کاراکترها عمل می‌کنند و متن برعکس فقط همان کاراکترها با ترتیب معکوس است.

f-string بعد از دونقطه format spec می‌گیرد:

```python
name, price = 'Roham', 1234.5678
print(f'{name:>8}|{price:,.2f}|{42:05d}|{255:#x}|{0.256:.1%}')
```

```text
   Roham|1,234.57|00042|0xff|25.6%
```

## Truthiness و None

هر شیء یک {{< term "truthiness" "truthiness" >}} دارد. روی چند مقدار `bool()` را اجرا کردم:

```text
     0 -> False
    '' -> False
    [] -> False
    {} -> False
  None -> False
   0.0 -> False
   'a' -> True
   [0] -> True
   0.1 -> True
```

صفر و container خالی false هستند. `[0]` true است چون لیست خالی نیست. با `None` باید با `is` مقایسه کنید، نه `==`: `x is None` درباره‌ی identity می‌پرسد و `__eq__` سفارشی نمی‌تواند گولش بزند.

## نام‌ها reference هستند

نام یک برچسب روی شیء است، نه جعبه‌ای که مقدار را نگه دارد:

```python
a = [1, 2, 3]
b = a
b.append(4)
print(a, a is b, id(a) == id(b))

nested = [[1], [2]]
sh = nested.copy()          # shallow
dp = copy.deepcopy(nested)  # deep
nested[0].append(99)
print(sh, dp)
```

```text
[1, 2, 3, 4] True True
[[1, 99], [2]] [[1], [2]]
```

`b = a` چیزی را کپی نمی‌کند. {{< term "shallow-copy" "کپی سطحی (shallow copy)" >}} فقط لیست بیرونی را کپی می‌کند و لیست‌های داخلی هنوز مشترکند. `copy.deepcopy` همه‌چیز را کپی می‌کند.

یک دام identity هم هست: `int('1000') is int('1000')` در اجرای من `False` چاپ کرد و `int('100') is int('100')` چاپ کرد `True`. این جزئیات پیاده‌سازی CPython است (عددهای کوچک دوباره استفاده می‌شوند)، پس هیچ‌وقت عددها را با `is` مقایسه نکنید.

## کنترل جریان

بلوک‌ها با indentation ساخته می‌شوند و سرِ بلوک با دونقطه تمام می‌شود. هر دو اشتباه موقع parse خطا می‌دهند:

```text
IndentationError: expected an indented block after 'if' statement on line 1
SyntaxError: expected ':'
IndentationError: unindent does not match any outer indentation level
```

`if/elif/else`، عبارت شرطی و `for` روی iterableها:

```python
label = 'adult' if age >= 18 else 'minor'
for i in range(10, 0, -3): print(i, end=' ')      # 10 7 4 1
for name, score in zip(['a', 'b', 'c'], [90, 80]):
    print(name, score)                              # a 90, b 80
```

`zip` با کوتاه‌ترین ورودی تمام می‌شود، پس `c` حذف می‌شود. `enumerate` اندیس و مقدار را می‌دهد.

حلقه می‌تواند `else` داشته باشد که فقط وقتی اجرا می‌شود که `break` اتفاق نیفتاده باشد:

```python
for i, v in enumerate([3, 5, 7]):
    if v == 9:
        print('found at', i)
        break
else:
    print('not found')       # چاپ شد
```

عملگر {{< term "walrus-operator" "walrus" >}} (`:=`) داخل یک عبارت مقدار می‌دهد و {{< term "list-comprehension" "list comprehension" >}} یک لیست را در یک خط می‌سازد (درباره‌ی comprehension بیشتر از این نمی‌گویم):

```python
if (k := len(data)) > 5:
    print('long list of', k)             # long list of 6
print([x * x for x in data if x % 2 == 0])   # [4, 16, 36]
```

## match

{{< term "structural-pattern-matching" "Structural pattern matching" >}} مقدار را باز می‌کند: literal، دنباله، mapping، کلاس و guard. این بدنه‌ی تابع `describe(v)` با یک dataclass به نام `Point` است:

```python
match v:
    case 0: return 'zero'
    case int(n) if n < 0: return f'negative {n}'
    case [first, *rest]: return f'list starting {first}, {len(rest)} more'
    case {'status': 'ok', 'items': items}: return f'ok with {len(items)} items'
    case Point(x=0, y=0): return 'origin'
    case Point(x=x, y=y): return f'point {x},{y}'
    case str() | bytes(): return 'text'
    case _: return 'other'
```

```text
0 -> zero
-5 -> negative -5
[1, 2, 3] -> list starting 1, 2 more
{'status': 'ok', 'items': [1]} -> ok with 1 items
Point(x=0, y=0) -> origin
Point(x=1, y=2) -> point 1,2
'hi' -> text
3.5 -> other
```

caseها از بالا به پایین امتحان می‌شوند. guard (`if n < 0`) مربوط به `-5` است، `Point(x=0, y=0)` یک class pattern است و `case _` حالت پیش‌فرض.

## چند نکته‌ی مهم

- من یک اسکریپت را `types.py` نام‌گذاری کردم و همه‌ی importها با `cannot import name 'GenericAlias' from 'types'` خراب شدند. فایل‌هایتان را هم‌نام ماژول‌های کتابخانه‌ی استاندارد نکنید.
- `float` برای پول باگ است. از `Decimal` ساخته‌شده از رشته استفاده کنید.
- `is` برای `None` (و singletonهای دیگر) است، `==` برای مقدار.
- انتساب شیء را به اشتراک می‌گذارد. وقتی استقلال می‌خواهید صریح کپی کنید و یادتان باشد `copy()` سطحی است.
- `for ... else` عجیب خوانده می‌شود: «else یعنی break نشد».

## تمرین

1. طول `'é'` را یک بار به‌صورت یک کاراکتر و یک بار به‌صورت `'e'` به‌علاوه‌ی accent ترکیبی (`'é'`) چاپ کنید و نتیجه را توضیح دهید.
2. تابع `classify(v)` را با `match` برای intها، لیست خالی و dictهایی با کلید `"type"` بنویسید.
3. با `for ... else` اولین عدد بخش‌پذیر بر ۷ را در یک لیست پیدا کنید و اگر نبود پیام بدهید.

## قدم بعدی

مقاله‌ی بعدی «توابع، closure و generator در Python» است.
