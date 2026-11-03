+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = 'هک ۶٫۳ میلیارد دلاری بایننس از دید فنی: نشانه‌ای از لو رفتن کلید نیست، ولی برداشت امضا شد'
seoTitle = 'هک ۶٫۳ میلیارد دلاری بایننس از دید فنی'
description = 'هک بایننس در اکتبر ۲۰۲۶ از دید فنی: بایننس چه گفت، TRM Labs و Chainalysis روی زنجیره چه دیدند و امضاکننده‌ی کیف‌پول داغ چه قاعده‌هایی باید اعمال کند.'
contentType = 'analysis'
categories = ["Security"]
tags = ["security", "binance", "crypto", "hot-wallet", "incident"]
keywords = ["هک بایننس", "بایننس هک شد", "بزرگ‌ترین هک کریپتو", "امنیت کیف پول داغ", "EIP-7702", "TraderTraitor", "Lazarus", "امنیت صرافی رمزارز", "امضای برداشت"]
cover = { image = "/images/covers/binance-hack-hot-wallet-2026.fa.png", alt = "هک ۶٫۳ میلیارد دلاری بایننس از دید فنی: نشانه‌ای از لو رفتن کلید نیست، ولی برداشت امضا شد", hiddenInSingle = true }
+++

عصر ۲۹ اکتبر ۲۰۲۶ (۷ آبان ۱۴۰۵) حدود ۶٫۳ میلیارد دلار از بایننس سرقت شد؛ بزرگ‌ترین سرقت ثبت‌شده‌ی کریپتو. گفته‌های بایننس، گزارش شرکت‌های تحلیل و برداشت خودم را جدا می‌آورم.

> بر اساس گزارش‌های عمومی تا ۳۰ اکتبر ۲۰۲۶؛ post-mortem بایننس هنوز منتشر نشده. کد Go مثال محلی خودم است، نه طراحی بایننس.

## بایننس چه گفته

- **خسارت و واکنش.** برآورد بایننس حدود ۶٫۳ میلیارد دلار است؛ برداشت را بست و طبق [BleepingComputer](https://www.bleepingcomputer.com/news/security/binance-links-63-billion-crypto-theft-to-compromised-devops-laptop/) گفت خسارت را از صندوق SAFU و دارایی شرکت جبران می‌کند.
- **توضیح اولیه، ۲۹ اکتبر.** به نقل از [CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets):

> "initial investigation suggests that the security incident may involve a compromised DevOps engineer's laptop, which allowed an attacker to gain access to a service container and submit unauthorized withdrawal transactions. We have found no evidence of any wallet private key leak."

- **به‌روزرسانی، ۳۰ اکتبر.** بایننس از «نقاط نفوذ دیگر» خبر داد و ریچارد تنگ، مدیرعامل مشترک، نوشت مهاجم «فقط از دسترسی‌های یک مهندس استفاده نکرد» ([The Next Web](https://thenextweb.com/news/binance-hack-6-3bn-north-korea-tradertraitor)).

پس لپ‌تاپ توضیحی اولیه و ناقص است، نه علت ریشه‌ای قطعی. بایننس عاملی را معرفی نکرده.

## گزارش شرکت‌های تحلیل بلاکچین

یافته‌های شخص ثالث، بیشتر از [گزارش TRM Labs](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history) در ۳۰ اکتبر:

- از ۲۰:۰۵ UTC حدود ۶٫۳۶ میلیارد دلار روی ده بلاکچین خارج شد، بیشترش ظرف ۲۰ دقیقه. به نقل از CoinDesk، رقم اولیه‌ی Chainalysis حدود ۵٫۹ میلیارد بود.
- روی اتریوم یک تراکنش **۵۰ authorization از نوع {{< term "eip-7702" "EIP-7702" >}}** داشت با امضای {{< term "hot-wallet" "کیف‌پول داغ" >}} بایننس که کیف‌پول را به قرارداد sweeper مهاجم می‌سپرد؛ ۱۶۷٬۴۶۴ ETH و ۱٫۶۱۵ میلیارد USDT خارج شد. جاروهای بعدی تا ۲۳:۵۶ ادامه داشت.
- روی زنجیره‌های دیگر انتقال‌ها امضای معمولی داشتند؛ به نظر TRM یعنی زیرساخت امضا نفوذ خورده.
- TRM حمله را «با اطمینان بالا» به گروه TraderTraitor کره‌ی شمالی نسبت می‌دهد و Chainalysis موافق است. طبق [Nextgov](https://www.nextgov.com/cybersecurity/2026/10/fbi-involved-response-63-billion-binance-hack-linked-north-korea/416946/)، FBI کسی را مسئول ندانسته.
- به حساب TRM حدود ۲٫۷ میلیارد دلار را صادرکننده‌ها و شورای امنیتی Arbitrum بلوکه کردند؛ رقم بایننس حدود ۳ میلیارد است ([Al Jazeera](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue)). اولین بلوکه‌ی تتر، ۹۷۱ میلیون USDT، ۳۷ دقیقه بعد از جاروی اصلی بود.
- حدود ۳۲۵ میلیون USDT با بیش از ۱۰٪ تخفیف در UniswapX فروخته شد؛ مهاجم هنوز حدود ۲٫۴ میلیارد دلار ETH و BTC غیرقابل‌بلوکه دارد.

## برداشت من: امضاکننده هر چه خواستند امضا کرد

این بخش تحلیل خودم است، نه گزارش. اگر ادعای لو نرفتن کلید درست بماند، مهاجم به چیزی رسیده که *اجازه داشت* امضا بخواهد. عدد ۵۰ منطقی است: هر authorization فقط با nonce فعلی معتبر است و nonce کیف‌پول داغ مدام جلو می‌رود، پس با امضای یک بازه یکی می‌خورد. به نظرم امضاکننده‌ای که این‌ها و انتقال‌های ده زنجیره را امضا کرد، بررسی سیاست کنار کلید نداشت یا دور زده شد. منبعی ندیدم که بگوید {{< term "multisig" "multisig" >}} یا MPC در کار بوده یا نه.

## امضاکننده چه باید اعمال کند

امضاکننده‌ی جابه‌جایی پول **نباید به فراخواننده‌اش اعتماد کند:** سیاست کنار کلید است، مستقل بررسی می‌شود و در شک بسته می‌ماند (fail closed). هسته‌ی یک مثال محلی در Go (تأییدها رشته‌اند، در عمل امضا):

```go
func (s *Signer) Sign(w Withdrawal, now time.Time) error {
	if s.halted {
		return ErrHalted
	}
	if w.Kind != "transfer" {
		return ErrKind // e.g. an unexpected EIP-7702 authorization
	}
	seen := map[string]bool{}
	for _, a := range w.Approvals {
		if a != w.Requester {
			seen[a] = true
		}
	}
	if len(seen) < 2 {
		return ErrApprovals
	}
	if !s.AllowedTo[w.To] {
		return ErrDest
	}
	// sum what was signed inside the window (trimmed)
	if sum+w.AmountUSD > s.WindowCap {
		s.halted = true // fail closed: stop everything, page a human
		return ErrCap
	}
	s.signed = append(s.signed, entry{now, w.AmountUSD})
	return nil
}
```

مهاجمی را شبیه‌سازی کردم که سرویس ثبت برداشت را دارد، با سقف ساعتی ۵۰ میلیون دلار. اجرای واقعی با Go 1.27:

```
20:05 w0 $0           REJECTED: EIP-7702 authorization not expected, refusing to sign
20:06 w1 $30000000    REJECTED: need 2 approvals from people other than the requester
20:07 w2 $30000000    REJECTED: need 2 approvals from people other than the requester
20:08 w3 $30000000    REJECTED: destination not on allowlist
20:09 w4 $30000000    SIGNED
20:10 w5 $30000000    REJECTED: window cap exceeded, halting signer
20:11 w6 $1000        REJECTED: signer halted, manual review required
```

`w0` (درخواست authorization) حتی با دو تأیید رد می‌شود. در `w1` و `w2` سرویس خودش را تأیید نمی‌تواند؛ `w3` آدرس ناشناس دارد. در `w4` مهاجم تأییدکننده‌ها و یک آدرس مجاز را دارد و برداشت عبور می‌کند. `w5` به سقف می‌خورد و امضاکننده مثل {{< term "kill-switch" "کلید اضطراری" >}} همه‌چیز را متوقف می‌کند؛ `w6`، انتقال مشروع کوچکی، منتظر انسان می‌ماند.

## کنترل‌های لازم برای کیف‌پول داغ

- {{< term "least-privilege" "حداقل دسترسی" >}}: لپ‌تاپ روزمره‌ی مهندس نباید مسیر دائمی به سرویس امضاگیر داشته باشد.
- توصیه‌ی TRM: authorizationهای غیرمنتظره‌ی EIP-7702 را رد کنید، چند authorization برای بازه‌ای از nonceها را نشانه‌ی نفوذ بدانید و برای هر delegation در کیف‌پول خزانه هشدار بدهید.
- پیشنهاد خودم: امضا را بر اساس زنجیره و سطح کیف‌پول جدا کنید تا {{< term "blast-radius" "شعاع آسیب" >}} یک نفوذ ده زنجیره نباشد.
- {{< term "incident-response" "واکنش به حادثه" >}} را از پیش با صادرکننده‌های {{< term "stablecoin" "استیبل‌کوین" >}} هماهنگ کنید.

## منابع

- [گزارش TRM Labs](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history)، ۳۰ اکتبر
- [CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets)، ۲۹ و ۳۰ اکتبر
- [The Next Web](https://thenextweb.com/news/binance-hack-6-3bn-north-korea-tradertraitor)، ۳۰ اکتبر
- [BleepingComputer](https://www.bleepingcomputer.com/news/security/binance-links-63-billion-crypto-theft-to-compromised-devops-laptop/)، ۳۰ اکتبر
- [Nextgov](https://www.nextgov.com/cybersecurity/2026/10/fbi-involved-response-63-billion-binance-hack-linked-north-korea/416946/)، ۳۰ اکتبر
- [Al Jazeera](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue)، ۳۰ اکتبر
