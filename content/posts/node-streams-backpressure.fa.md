+++
date = '2026-12-17T10:00:00+03:30'
draft = false
title = 'stream و backpressure در Node.js'
description = 'stream و backpressure در Node.js با اجرای واقعی: حافظه‌ی readFileSync در برابر stream، pipeline با gzip، برگشتن false از write()، drain و مدیریت خطا.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "streams", "backpressure", "pipeline", "javascript"]
cover = { image = "/images/covers/node-streams-backpressure.fa.png", alt = "stream و backpressure در Node.js", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [خطا و unhandled rejection در Node.js](/fa/posts/node-errors-unhandled-rejections/)، شکست‌ها را دیدنی کردیم. حالا مسئله‌ای دیگر: داده‌ای که بزرگ‌تر از آن است که بخواهیم کامل در حافظه نگهش داریم. جواب، **{{< term "stream" "stream" >}}** است. این مقاله روی [event loop](/fa/posts/node-event-loop/) و [Promise و async/await](/fa/posts/node-promises-async-await/) بنا شده. اگر از Go می‌آیید، معادلش [کار با فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/) است.

> همه‌چیز با Node نسخه‌ی v20.13.1 روی یک ماشین اجرا شده است. اسکریپت‌ها مثال‌های محلی هستند و خروجی‌ها از اجرای واقعی کپی شده‌اند.

## چهار نوع stream

- **Readable**: منبعی که از آن chunk می‌گیرید (خواندن فایل، بدنه‌ی درخواست HTTP).
- **Writable**: مقصدی که به آن chunk می‌دهید (فایل، socket).
- **Duplex**: هر دو جهت، مستقل از هم (سوکت TCP).
- **Transform**: یک Duplex که خروجی‌اش از ورودی محاسبه می‌شود (gzip، تبدیل به حروف بزرگ).

## حافظه: readFileSync در برابر stream

یک فایل متنی ۵۲٬۴۲۸٬۸۰۵ بایتی ساختم و بایت‌هایش را به دو روش شمردم و `process.memoryUsage().rss` را چاپ کردم:

```js
// sync mode: const buf = fs.readFileSync('big.txt'); bytes = buf.length;
// stream mode:
for await (const chunk of fs.createReadStream('big.txt')) {
  bytes += chunk.length;
  peak = Math.max(peak, process.memoryUsage().rss);
}
```

```text
sync bytes: 52428805 rss before MB: 35 peak rss MB: 85
stream bytes: 52428805 rss before MB: 35 peak rss MB: 62
```

`for await` روی Readable کار می‌کند چون streamها async iterable هستند. رشد حافظه برای `readFileSync` حدود ۵۰ مگابایت و برای stream حدود ۲۷ مگابایت بود، یعنی تقریباً نصف. این عدد را تقریبی بگیرید: RSS شامل زباله‌ی هنوز جمع‌نشده است و به ماشین بستگی دارد. stream فقط چند chunk را هم‌زمان نگه می‌دارد، اما اینکه این فاصله با بزرگ‌تر شدن فایل چطور تغییر می‌کند را اندازه نگرفتم.

## pipeline

`pipeline` از `node:stream/promises` streamها را وصل می‌کند و پاک‌سازی را خودش انجام می‌دهد:

```js
const upper = new Transform({
  transform(chunk, enc, cb) { cb(null, chunk.toString().toUpperCase()); },
});
await pipeline(createReadStream('big.txt'), upper, zlib.createGzip(), createWriteStream('big.txt.gz'));
```

```text
original: 52428805 gzip: 152664
```

(ورودی یک خط تکراری است و به همین دلیل فوق‌العاده خوب فشرده می‌شود.) `Readable.from(asyncGenerator)` یک generator را به stream تبدیل می‌کند و به‌طور پیش‌فرض در **{{< term "object-mode" "object mode" >}}** است، پس chunkها می‌توانند شیء باشند:

```js
async function* nums() { for (let i = 1; i <= 5; i++) yield { id: i, sq: i * i }; }
for await (const o of Readable.from(nums())) console.log(o);
```

```text
{ id: 1, sq: 1 }
{ id: 2, sq: 4 }
...
{ id: 5, sq: 25 }
```

## Backpressure

یک Writable هرچه را هنوز نتوانسته پردازش کند بافر می‌کند. **{{< term "backpressure" "Backpressure" >}}** قاعده‌ای است که می‌گوید وقتی بافر پر شد، `write()` مقدار `false` برمی‌گرداند و تولیدکننده باید تا رویداد `'drain'` صبر کند. آستانه‌اش **{{< term "high-water-mark" "highWaterMark" >}}** است. ۱۰۰ chunk یک‌کیلوبایتی را در یک Writable عمداً کند (هر بار یک chunk در هر دور event loop) نوشتم؛ یک بار با نادیده گرفتن مقدار برگشتی و یک بار با انتظار برای `'drain'`:

```js
const ok = slow.write(chunk);
maxBuffered = Math.max(maxBuffered, slow.writableLength);
if (!ok) {
  falseCount++;
  if (respect) await new Promise((r) => slow.once('drain', r));
}
```

```text
highWaterMark: 16384
ignoring { written: 100, falseCount: 85, drains: 0, maxBufferedBytes: 102400 }
respecting { written: 100, falseCount: 6, drains: 6, maxBufferedBytes: 16384 }
```

با نادیده گرفتن سیگنال، کل ۱۰۰ کیلوبایت بافر شد. با رعایتش هرگز بیش از ۱۶ کیلوبایت نگه داشته نشد. شمارش‌ها قطعی‌اند و زمانی گزارش نمی‌کنم. با `pipeline` یا `.pipe()` این کار خودکار انجام می‌شود، و همین دلیل اصلی استفاده از آن‌هاست.

## خطا: pipeline در برابر .pipe()

Transform را طوری ساختم که در chunk دوم خطا بدهد. با `pipeline`:

```text
pipeline transform closed, destroyed = true
pipeline writable closed, destroyed = true
pipeline rejected: bad chunk
pipeline readable closed, destroyed = true
```

همه‌ی streamها destroy شدند و promise رد شد، پس `try/catch` کار می‌کند. با `readable.pipe(transform).pipe(writable)`:

```text
transform error event: bad chunk
pipe transform closed, destroyed = true
readable destroyed: false writable destroyed: false writable ended: false
```

فقط stream خطادار بسته شد. منبع و مقصد باز ماندند: یک leak، و writable هرگز تمام نمی‌شود. `.pipe()` خطا را منتقل نمی‌کند.

## چند نکته‌ی مهم

- `pipeline` را به `.pipe()` ترجیح بدهید و rejection آن را حتماً مدیریت کنید.
- اگر خودتان `write()` را صدا می‌زنید، مقدار برگشتی را بررسی کنید و منتظر `'drain'` بمانید.
- `highWaterMark` آستانه است، نه سقف: اگر به نوشتن ادامه دهید بافر از آن بزرگ‌تر می‌شود.
- `readFileSync` را روی فایلی که اندازه‌اش دست شما نیست استفاده نکنید.
- در Go، `io.Copy` بین Reader و Writer این را رایگان دارد چون `Write` بلاک می‌شود؛ در Node همه‌چیز غیربلاکی است و باید صریح سیگنال داد.

## تمرین

اسکریپتی بنویسید که `big.txt` را خط‌به‌خط بخواند، فقط خطوط شامل `fox` را نگه دارد و با `pipeline` در فایل جدیدی بنویسد. بعد Transform را طوری تغییر دهید که در chunk هزارم خطا بدهد و ببینید promise رد می‌شود و stream خروجی destroy شده است.

## قدم بعدی

مقاله‌ی بعد «سرور HTTP با node:http» است، جایی که خود درخواست و پاسخ هم stream هستند.
