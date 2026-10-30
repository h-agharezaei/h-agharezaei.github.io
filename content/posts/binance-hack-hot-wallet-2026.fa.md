+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = 'هک ۶٫۳ میلیارد دلاری بایننس از دید فنی: کلید لو نرفت، ولی برداشت امضا شد'
seoTitle = 'هک ۶٫۳ میلیارد دلاری بایننس از دید فنی'
description = 'هک بایننس در اکتبر ۲۰۲۶ از دید فنی: لپ‌تاپ آلوده‌ی یک مهندس DevOps، برداشت‌هایی که بدون لو رفتن کلید امضا شدند و قاعده‌هایی که امضاکننده باید اعمال کند.'
categories = ["Security"]
tags = ["security", "binance", "crypto", "hot-wallet", "incident"]
keywords = ["هک بایننس", "بایننس هک شد", "بزرگ‌ترین هک کریپتو", "امنیت کیف پول داغ", "EIP-7702", "TraderTraitor", "Lazarus", "امنیت صرافی رمزارز", "امضای برداشت"]
cover = { image = "/images/covers/binance-hack-hot-wallet-2026.fa.png", alt = "هک ۶٫۳ میلیارد دلاری بایننس از دید فنی: کلید لو نرفت، ولی برداشت امضا شد", hiddenInSingle = true }
+++

عصر ۲۹ اکتبر ۲۰۲۶ (۷ آبان ۱۴۰۵) حدود ۶٫۳ میلیارد دلار از کیف‌پول‌های بایننس خارج شد؛ بزرگ‌ترین سرقت تاریخ کریپتو. اینجا گزارش‌ها، ردپای حمله روی زنجیره و درسش برای سازنده‌ی سیستم‌های جابه‌جایی پول را مرور می‌کنم.

> بر اساس گزارش‌های عمومی تا ۳۰ اکتبر؛ عددها هنوز تغییر می‌کنند و بایننس قول post-mortem فنی داده است. کد Go مثال محلی خودم است، نه طراحی بایننس.

## چه چیزهایی گزارش شده

| | |
|---|---|
| زمان | از ۲۰:۰۵ UTC روز ۲۹ اکتبر، بیشترش در حدود ۲۰ دقیقه (TRM) |
| خسارت | حدود ۶٫۳۶ میلیارد دلار روی ده بلاکچین (TRM)؛ برآورد بایننس حدود ۶٫۳ میلیارد |
| بلوکه‌شده | حدود ۲٫۷ میلیارد دلار: تتر، سیرکل، Ripple، World Liberty Financial و شورای امنیتی Arbitrum (TRM) |
| عامل | TRM: گروه TraderTraitor کره‌ی شمالی، «با اطمینان بالا»؛ بایننس کسی را معرفی نکرده |
| واکنش | توقف برداشت روی چند شبکه؛ جبران خسارت از صندوق SAFU و دارایی خود شرکت |

## جمله‌ای که مهم است

بیانیه‌ی اولیه‌ی بایننس، به نقل از CoinDesk:

> "...may involve a compromised DevOps engineer's laptop, which allowed an attacker to gain access to a service container and submit unauthorized withdrawal transactions. We have found no evidence of any wallet private key leak."

یعنی لپ‌تاپ آلوده‌ی یک مهندس DevOps مهاجم را به یک container سرویس رسانده و او برداشت غیرمجاز ثبت کرده، بی آنکه کلید خصوصی لو برود. مهاجم به کلید نیاز نداشت؛ به سرویسی رسید که *اجازه داشت* درخواست امضا بدهد.

## ردپای روی زنجیره: ۵۰ امضای از پیش آماده

طبق TRM Labs، روی اتریوم مهاجم از {{< term "eip-7702" "EIP-7702" >}} استفاده کرد. این قابلیت به یک کیف‌پول معمولی اجازه می‌دهد با امضای یک authorization رفتارش را به یک قرارداد هوشمند بسپارد. ساعت ۲۰:۲۰ یک تراکنش با **۵۰ authorization** ارسال شد که همه را خود {{< term "hot-wallet" "کیف‌پول داغ" >}} بایننس امضا کرده بود و کیف‌پول را به یک قرارداد sweeper می‌سپرد که فقط از مهاجم دستور می‌گرفت.

چرا ۵۰ تا؟ authorization فقط با nonce فعلی کیف‌پول معتبر است و کیف‌پول داغ مدام برداشت انجام می‌دهد، پس nonce اش جلو می‌رود. مهاجم برای ۵۰ nonce پشت سر هم امضا گرفته بود. سه دقیقه بعد کل موجودی رفت: ۱۶۷٬۴۶۴ ETH و ۱٫۶۱۵ میلیارد USDT. واگذاری باقی ماند و پول‌های تازه تا ۲۳:۵۶ چند بار دیگر جارو شدند.

نکته‌ی مهم‌تر: روی ۹ زنجیره‌ی دیگر، با کلیدها و روش‌های امضای متفاوت، انتقال‌ها امضای **معمولی** داشتند و همه ظرف حدود نیم ساعت. جمع‌بندی TRM این است که مهاجم توانسته سیستم امضای کیف‌پول داغ بایننس را وادار کند هر تراکنشی را که می‌خواهد امضا کند. این با بیانیه‌ی بایننس جور است: کلید لو نرفت، ولی امضاکننده هر چه خواستند امضا کرد. TRM همین الگو را در هک Bybit در ۲۰۲۵ هم دیده است.

## چه چیزهایی هنوز معلوم نیست

- لپ‌تاپ چطور به container پروداکشن رسید. بایننس هنوز root cause منتشر نکرده.
- چرا لایه‌ی امضا بی هیچ سقف یا تأییدی برای ده زنجیره امضا داد. به نظر TRM، دسته‌ی ۵۰تایی یعنی دسترسی احتمالاً زمان‌دار بوده یا امضا از طریق یک سیستم درخواست می‌شد. از {{< term "multisig" "multisig" >}} یا MPC در گزارش‌ها حرفی نیست.

## مسیر پول‌شویی

صادرکننده‌ها می‌توانند {{< term "stablecoin" "استیبل‌کوین" >}} را بلوکه کنند، پس مهاجم با عجله تبدیل کرد. طبق TRM، حدود ۳۲۵ میلیون USDT را با بیش از ۱۰٪ زیان از طریق UniswapX به market makerها فروخت و با ۶۰ میلیون USDT در Aave حدود ۱۹٬۷۶۰ ETH قرض گرفت. الان حدود ۲٫۴ میلیارد دلار ETH و BTC در دست دارد که کسی نمی‌تواند بلوکه‌اش کند.

## امضاکننده باید چه چیزی را اعمال کند

اگر سیستمی دارید که جابه‌جایی پول را امضا می‌کند، **امضاکننده نباید به فراخواننده‌اش اعتماد کند.** سیاست باید کنار کلید باشد، مستقل بررسی شود و در صورت شک بسته شود (fail closed). هسته‌ی یک مثال محلی در Go (تأییدها اینجا رشته‌اند؛ در سیستم واقعی امضاهایی‌اند که امضاکننده بررسی می‌کند):

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

مهاجمی را شبیه‌سازی کردم که سرویس ثبت برداشت را در دست دارد، با سقف ۵۰ میلیون دلار در ساعت. اجرای واقعی با Go 1.27:

```
20:05 w0 $0           REJECTED: EIP-7702 authorization not expected, refusing to sign
20:06 w1 $30000000    REJECTED: need 2 approvals from people other than the requester
20:07 w2 $30000000    REJECTED: need 2 approvals from people other than the requester
20:08 w3 $30000000    REJECTED: destination not on allowlist
20:09 w4 $30000000    SIGNED
20:10 w5 $30000000    REJECTED: window cap exceeded, halting signer
20:11 w6 $1000        REJECTED: signer halted, manual review required
```

`w0` درخواست authorization است و حتی با دو تأیید رد می‌شود. `w1` و `w2`: سرویس نمی‌تواند خودش را تأیید کند؛ `w3`: آدرس ناشناس. `w4` بدترین حالت است: مهاجم تأییدکننده‌ها و یک آدرس مجاز را هم دارد و یک برداشت رد می‌شود. `w5` به سقف می‌خورد و امضاکننده مثل یک {{< term "kill-switch" "کلید اضطراری" >}} همه‌چیز را متوقف می‌کند؛ `w6`، یک انتقال مشروع کوچک، منتظر انسان می‌ماند.

## چند نکته‌ی مهم

- {{< term "least-privilege" "حداقل دسترسی" >}} برای لپ‌تاپ‌ها: سیستم روزمره‌ی یک مهندس نباید مسیر دائمی به سرویسی داشته باشد که می‌تواند امضا بگیرد.
- توصیه‌ی TRM: authorization های EIP-7702 را رد کنید مگر منتظرشان باشید، درخواست چند authorization برای بازه‌ای از nonce ها را نشانه‌ی نفوذ بدانید و روی کیف‌پول‌های خزانه هر delegation را فوراً هشدار دهید.
- زیرساخت امضا را بر اساس زنجیره و سطح کیف‌پول جدا کنید تا {{< term "blast-radius" "شعاع آسیب" >}} یک نفوذ ده زنجیره نباشد.
- {{< term "incident-response" "واکنش به حادثه" >}} را از قبل با صادرکننده‌های استیبل‌کوین آماده کنید. تتر ۳۷ دقیقه بعد از جاروی اصلی، ۹۷۱ میلیون USDT را در کیف‌پول مقصد بلوکه کرد.

## منابع

- [TRM Labs: North Korea Steals USD 6.36 Billion From Binance](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history)
- [CoinDesk: Binance loses over $6 billion in the largest crypto hack to date](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets)
- [Al Jazeera: Binance says $6.3bn stolen](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue)
- [TechCrunch: Binance pauses withdrawals](https://techcrunch.com/2026/10/29/binance-pauses-withdrawals-as-hackers-suspected-of-stealing-billions-in-crypto/)
