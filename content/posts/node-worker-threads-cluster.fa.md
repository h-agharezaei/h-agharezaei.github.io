+++
date = '2027-03-28T10:00:00+03:30'
draft = false
title = 'worker thread و cluster در Node.js'
description = 'worker thread و cluster در Node.js: بلاک‌کردن event loop از عمد و رفعش با worker، Atomics، pool و cluster، همه با اجرای واقعی و خروجی عددی.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "worker-threads", "cluster", "concurrency", "performance"]
cover = { image = "/images/covers/node-worker-threads-cluster.fa.png", alt = "worker thread و cluster در Node.js", hiddenInSingle = true }
+++

یک آزمایش کوچک. یک تایمر راه می‌اندازم که باید هر ۱۰ میلی‌ثانیه tick بزند و بعد یک تابع عمداً کند به اسم `fib(38)` را صدا می‌زنم. تا وقتی این تابع اجرا می‌شود، تایمر صفر بار tick می‌زند. نه «چند بار با تأخیر». صفر. در تمام آن یک ثانیه‌ی تقریبی محاسبه، برنامه نمی‌توانست هیچ کار دیگری بکند و یک سرور وب در چنین حالتی به هیچ درخواستی جواب نمی‌داد.

هرچه تا حالا در Node.js نوشتیم، تا [اعتبارسنجی ورودی با Zod](/fa/posts/node-validation-zod/)، روی یک thread اجرا شد. همان‌طور که [event loop در Node.js](/fa/posts/node-event-loop/) توضیح داد، برای I/O این مشکلی ندارد: وقتی برنامه منتظر دیتابیس یا شبکه است، حلقه کار دیگری را سرویس می‌دهد. ولی یک محاسبه‌ی طولانی منتظر هیچ‌چیز نمی‌ماند. تنها thread را مشغول نگه می‌دارد و هر درخواست دیگری پشت آن صف می‌کشد.

راه‌حل این است که آن محاسبه را جای دیگری اجرا کنیم. Node برای این دو ابزار دارد که راحت با هم اشتباه گرفته می‌شوند:

- {{< term "worker-threads" "worker thread" >}} یک thread دیگر داخل همان برنامه است. event loop و حافظه‌ی خودش را دارد و با thread اصلی با فرستادن پیام حرف می‌زند. برای بردن کار سنگین CPU از thread اصلی به کار می‌رود.
- {{< term "node-cluster" "cluster" >}} چند نسخه از کل برنامه‌ی شما را به‌شکل چند {{< term "process" "process" >}} جدا بالا می‌آورد (process برنامه‌ای در حال اجرا با حافظه‌ی مخصوص خودش است) که یک پورت شنود را بین خودشان تقسیم می‌کنند. برای سرویس‌دادن HTTP روی همه‌ی هسته‌های CPU به کار می‌رود.

`child_process` هم هست که هر برنامه‌ای را به‌صورت process جدا اجرا می‌کند؛ در این مقاله از آن استفاده نمی‌کنم. برای بخش cluster روی [سرور HTTP با node:http](/fa/posts/node-http-server/) بنا می‌کنم.

> همه‌چیز را با Node نسخه‌ی v20.13.1 و به‌صورت اسکریپت‌های محلی روی 127.0.0.1 اجرا کردم. اسکریپت‌های دموی اصلی این مقاله نگه‌داری نشده بودند، پس برای این نسخه دوباره‌شان نوشتم و اجرا کردم؛ کدِ پایین همان است که اجرا کردم. ماشین مشغول بود، پس تعداد گزارش می‌کنم و زمان نه. این‌ها را روی Linux یا Windows اجرا نکرده‌ام.

## event loop بلوکه‌شده

اسکریپت اول یک کار را دو بار اجرا می‌کند. یک `setInterval` ده‌میلی‌ثانیه‌ای یک شمارنده را زیاد می‌کند و من tickهایی را می‌شمارم که در حین کار اتفاق می‌افتند. بار اول کار روی thread اصلی اجرا می‌شود و بار دوم در یک worker:

```js
const w = new Worker(new URL('./fibworker.mjs', import.meta.url), { workerData: { n: 38 } });
w.on('message', resolve);
w.on('error', reject);
// fibworker.mjs: parentPort.postMessage(fib(workerData.n))
```

`workerData` هنگام شروع به worker کپی می‌شود و worker جوابش را با `postMessage` پس می‌فرستد. خروجی:

```text
block:  fib(38) = 39088169 | ticks counted during the job: 0
worker: fib(38) = 39088169 | ticks counted during the job: 38
```

در خط اول تایمر در تمام مدت کار گرسنه ماند: ۰ tick. در خط دوم همان تابع در worker اجرا شد و thread اصلی به tick زدن ادامه داد. تعداد دقیق tickها به ماشین و بارش بستگی دارد (در اجرای دیگری ۳۵ گرفتم و نسخه‌ی اصلی این مقاله ۵۲ نشان می‌داد). نکته ۰ در برابر غیرصفر است.

## کپی و انتقال

thread اصلی و worker متغیر مشترک ندارند. وقتی `postMessage` را صدا می‌زنید، داده به‌طور پیش‌فرض کپی می‌شود. برای یک `ArrayBuffer` بزرگ این کپی هدر دادن است، پس می‌توانید بافر را تحویل بدهید: آن را در آرگومان دوم (`transferList`) فهرست کنید. آن‌وقت بافر منتقل می‌شود، نه کپی:

```text
copied buffer after postMessage: byteLength = 8
before transfer: byteLength = 1024
after transfer:  byteLength = 0
worker got byteLength 1024 first byte 42
```

بافر کوچکی که بدون فهرست فرستادم `byteLength` برابر ۸ را نگه داشت، چون worker یک نسخه گرفت. بافر بزرگی که منتقل کردم بعدش در فرستنده `byteLength` برابر ۰ دارد («detached» شده)، و worker هر ۱۰۲۴ بایت را گرفت، از جمله بایت اول با مقدار 42 که نوشته بودم. انتقال برای بافر بزرگ سریع است، ولی بعد از فرستادن نباید به آن دست بزنید.

## حافظه‌ی مشترک با Atomics

گاهی واقعاً یک بلوک حافظه می‌خواهید که چند thread ببینند. {{< term "shared-array-buffer" "SharedArrayBuffer" >}} دقیقاً همین است: بدون کپی و قابل‌دیدن برای همه‌ی threadها. این هم مشکل کلاسیک حافظه‌ی مشترک را می‌آورد. برای نشان‌دادنش، چهار worker هرکدام صد هزار بار ۱ به دو شمارنده در یک `Int32Array` مشترک اضافه می‌کنند. یک شمارنده با `Atomics.add` و دیگری با `v[1]++` ساده به‌روز می‌شود:

```js
for (let i = 0; i < N; i++) { Atomics.add(v, 0, 1); v[1]++; }
```

```text
expected      : 400000
Atomics.add   : 400000
plain v[1]++  : 171664 | lost updates: 228336
```

شمارنده‌ی atomic دقیق است. شمارنده‌ی ساده بیش از نصف به‌روزرسانی‌هایش را گم کرد. چرا؟ `v[1]++` در واقع سه قدم است: مقدار را بخوان، یکی اضافه کن، پس بنویس. دو thread می‌توانند یک مقدار را بخوانند، هر دو یکی اضافه کنند و هر دو یک نتیجه را بنویسند، پس یک به‌روزرسانی ناپدید می‌شود. این باگ یک {{< term "race-condition" "race condition" >}} است، از همان خانواده‌ی [sync، select و context در Go](/fa/posts/go-sync-select-context/). `Atomics.add` آن سه قدم را به یک قدم تقسیم‌ناپذیر تبدیل می‌کند. عدد شمارنده‌ی ساده در هر اجرا فرق می‌کند: اجرای دیگری ۱۷۹۰۱۸ داد و نسخه‌ی اصلی این مقاله ۱۹۵۰۴۰ و ۱۵۴۶۹۳ دیده بود. شمارنده‌ی atomic هر بار ۴۰۰۰۰۰ است.

## یک pool کوچک

شروع یک worker تازه برای هر کار هدر دادن است، چون شروع یک thread هزینه دارد. جواب معمول یک pool از workerهاست: چند worker را یک‌بار بالا بیاورید، یک صف کار و یک فهرست workerهای بیکار نگه دارید و هر کار را به یک worker بیکار بدهید. این یکی کوچک است، با یک promise برای هر کار تا صدازننده‌ها ساده `await` کنند:

```js
class Pool {
  constructor(file, size) {
    this.queue = []; this.idle = [];
    for (let i = 1; i <= size; i++) {
      const w = new Worker(file); w.id = i;
      w.on('message', (r) => { const j = w.job; w.job = null; this.idle.push(w); j.resolve({ value: r, by: w.id }); this.next(); });
      w.on('error', (e) => { const j = w.job; w.job = null; if (j) j.reject(e); });
      this.idle.push(w);
    }
    this.all = [...this.idle];
  }
  run(data) { return new Promise((resolve, reject) => { this.queue.push({ data, resolve, reject }); this.next(); }); }
  next() {
    while (this.idle.length && this.queue.length) {
      const w = this.idle.pop(), job = this.queue.shift();
      w.job = job; w.postMessage(job.data);
    }
  }
  close() { return Promise.all(this.all.map((w) => w.terminate())); }
}
```

`run` یک کار را در صف می‌گذارد؛ `next` کارهای صف را به workerهای بیکار می‌دهد؛ وقتی worker جواب می‌دهد به فهرست بیکارها برمی‌گردد و کار بعدی شروع می‌شود. دو worker را روی شش ورودی، از `fib(30)` تا `fib(35)`، اجرا کردم:

```text
fib(30) = 832040  (done by worker#2)
fib(31) = 1346269  (done by worker#1)
fib(32) = 2178309  (done by worker#2)
fib(33) = 3524578  (done by worker#1)
fib(34) = 5702887  (done by worker#2)
fib(35) = 9227465  (done by worker#1)
results are in input order: true
```

نتیجه‌ها به ترتیب ورودی درمی‌آیند چون اسکریپت همه‌ی promiseها را به ترتیب ورودی `await` می‌کند، نه چون workerها به ترتیب تمام می‌کنند. اینکه کدام worker کدام کار را بگیرد ممکن است از اجرایی به اجرای دیگر فرق کند.

## خطا و خروج

worker می‌تواند به دو شکل شکست بخورد. اسکریپت سه worker کوچک بالا می‌آورد، یکی که throw می‌کند، یکی که `process.exit(3)` را صدا می‌زند و یکی که عادی تمام می‌شود، و به هر دو رویداد گوش می‌دهد:

```text
throw -> error event: boom in worker
throw -> exit event, code 1
exit3 -> exit event, code 3
ok    -> exit event, code 0
```

یک `throw` گرفته‌نشده در worker اول `error` را روی parent منتشر می‌کند و بعد `exit` (کد ۱). `process.exit(3)` در worker فقط `exit` را با همان کد منتشر می‌کند. پس همیشه به هر دو گوش دهید و در pool کار جاری را روی `error` رد کنید. pool کوچک من این کار را می‌کند ولی وقتی یک worker می‌میرد جایش را با worker تازه پر نمی‌کند. یک pool واقعی باید این کار را بکند.

## cluster: یک پورت، چند process

worker threadها برای کار CPU داخل یک برنامه کمک می‌کنند. برای استفاده از هسته‌های بیشتر در یک سرور HTTP، `cluster` چند process فرزند بالا می‌آورد که همه روی یک پورت گوش می‌دهند. process اول، یعنی primary، اتصال‌ها را می‌پذیرد و به workerها می‌دهد. طبق مستندات Node.js پیش‌فرض روی همه‌ی پلتفرم‌ها جز Windows round-robin است: اتصال ۱ به worker اول، اتصال ۲ به worker دوم و همین‌طور ادامه.

اسکریپت دو worker بالا می‌آورد. هرکدام به هر درخواست با `process.pid` خودش جواب می‌دهد. بعد primary ۴۰ درخواست می‌فرستد، یکی پس از دیگری و هرکدام روی یک اتصال تازه (`connection: close`)، و می‌شمارد کدام worker جواب داده. pidهای واقعی را با نام عوض کردم:

```text
40 requests, distinct responders: 2 -> worker#1: 20, worker#2: 20
```

۲۰ و ۲۰ مساوی، همان‌طور که round-robin پیش‌بینی می‌کند. بعد worker#1 را با `SIGKILL` کشتم و نگاه کردم primary چه دید:

```text
worker#1 exited (signal SIGKILL)
alive workers now: 1
40 requests after restart, distinct responders: 2 -> worker#2: 20, worker#3: 20
```

primary رویداد `exit` را گرفت و فقط یک worker زنده مانده بود. cluster خودش workerها را دوباره راه نمی‌اندازد: اسکریپت خودش worker#3 را بالا آورد و بعد تقسیم دوباره مساوی شد. زنده نگه‌داشتن workerها کار شماست (یا کار process manager‌تان).

یک مشاهده‌ی دیگر. وقتی ۴۰ درخواست دور دوم را به‌جای یکی‌یکی همه را با هم فرستادم، تقسیم در اجراهای من ۳۷ و ۳ بود، نه ۲۰ و ۲۰ (دور اول، که همین‌طور فرستاده شد، باز ۲۰ و ۲۰ بود). دلیلش را بررسی نکردم. روی تقسیم دقیقاً مساوی حساب نکنید.

## کدام را به کار ببریم

- **کار CPU-bound داخل یک process:** worker thread.
- **سرویس‌دادن HTTP روی همه‌ی هسته‌ها:** cluster، یا یک process manager یا orchestrator که چند نسخه از برنامه را اجرا کند.
- **بیشتر I/O (دیتابیس، شبکه):** هیچ‌کدام. event loop از قبل از پسش برمی‌آید.

## مقایسه با Go

در Go یک {{< term "goroutine" "goroutine" >}} را runtime روی هسته‌ها پخش می‌کند، پس کار CPU به API اضافه نیاز ندارد ([goroutine و channel در Go](/fa/posts/go-goroutines-channels/)، [scheduler و garbage collector در Go](/fa/posts/go-scheduler-gc-internals/)). در Node خودتان thread یا process را انتخاب می‌کنید و هر worker حافظه‌ی خودش را دارد.

## جاهایی که thread و process گاز می‌گیرند

- **workerها متغیرهای شما را نمی‌بینند.** worker event loop و heap خودش را دارد؛ فقط بافرهای مشترک مشترک‌اند و بقیه‌چیز با پیام کپی می‌شود.
- **worker بیش از حد.** بیشتر از تعداد هسته worker از نوع CPU-bound بالا نیاورید؛ فقط با هم رقابت می‌کنند.
- **شکست worker که کسی نمی‌بیند.** همیشه `error` و `exit` را مدیریت کنید، وگرنه یک worker مرده کاری را برای همیشه منتظر می‌گذارد.
- **به‌روزرسانی ساده روی حافظه‌ی مشترک.** `v[1]++` روی `SharedArrayBuffer` به‌روزرسانی گم می‌کند. از `Atomics` استفاده کنید.
- **state در workerهای cluster.** workerهای cluster هیچ حافظه‌ای را به اشتراک نمی‌گذارند. session و cache را بیرون نگه دارید، در یک دیتابیس یا سرویس دیگر.

## تمرین

pool را طوری تغییر دهید که بعد از `error` یک worker جایگزین بالا بیاورد، و با کاری که روی یک ورودی انتخابی throw می‌کند تستش کنید.

## قدم بعدی

مقاله‌ی بعد «پروفایل، حافظه و خاموشی تمیز در Node.js» است. پیش از اضافه‌کردن worker باید بدانید زمان و حافظه واقعاً کجا می‌روند، و آن مقاله نشان می‌دهد چطور بفهمید.
