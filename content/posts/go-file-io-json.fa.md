+++
date = '2026-12-06T10:00:00+03:30'
draft = false
title = 'کار با فایل، io.Reader/Writer و JSON در Go'
description = 'خواندن و نوشتن فایل با os و bufio، ترکیب‌پذیری io.Reader و io.Writer و encode و decode کردن JSON با encoding/json، همراه با پیام‌های خطای واقعی.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "json", "io"]
cover = { image = "/images/covers/go-file-io-json.fa.png", alt = "کار با فایل، io.Reader/Writer و JSON در Go", hiddenInSingle = true }
+++

فرض کنید تابعی نوشته‌اید که یک گزارش چاپ می‌کند. امروز در ترمینال چاپ می‌شود. فردا کسی می‌خواهد همین گزارش در یک فایل ذخیره شود و پس‌فردا شما می‌خواهید متنش را در یک تست چک کنید، بدون اینکه به دیسک دست بزنید. اگر تابع برای حرف زدن با ترمینال نوشته شده باشد، هر بار باید آن را عوض کنید یا از رویش کپی بگیرید.

Go این مشکل را با یک ایده‌ی خیلی کوچک حل می‌کند. تابع به‌جای «در ترمینال بنویس» یا «در این فایل بنویس» می‌گوید «در هر چیزی که بایت قبول می‌کند بنویس». این «هر چیز» یک interface به نام `io.Writer` است و جفتش برای خواندن `io.Reader` است. وقتی این دو را بشناسید، فایل، بافر داخل حافظه، اتصال شبکه و خروجی استاندارد همه یک شکل پیدا می‌کنند و یک کد روی همه‌شان کار می‌کند.

بعد از [تست و benchmark](/fa/posts/go-testing-basics/)، در این نوشته سراغ دو کاری می‌رویم که برنامه‌های واقعی مدام انجام می‌دهند: خواندن و نوشتن فایل، و حرف زدن با JSON. از فایل کامل شروع می‌کنیم، بعد دو interface را می‌شناسیم و بعد با پکیج `encoding/json` به کار می‌گیریمشان.

> همه‌ی مثال‌ها را با Go 1.27 روی یک مک arm64 اجرا کرده‌ام. فایل‌ها در پوشه‌ای هستند که با `os.MkdirTemp` ساخته شده (در کدها `dir`) و آخر برنامه پاک می‌شود. خروجی‌ها از همان اجرا کپی شده‌اند. کد یک مثال محلی است، نه مخزن منتشرشده.

## خواندن کل فایل و خط‌به‌خط

برای فایل کوچک ساده‌ترین راه این است که با یک فراخوانی بنویسید و با یک فراخوانی بخوانید:

```go
path := filepath.Join(dir, "notes.txt")
os.WriteFile(path, []byte("alpha\nbeta\ngamma\n"), 0o644)
data, err := os.ReadFile(path)
fmt.Printf("ReadFile: %q (%d bytes)\n", data, len(data))
```

```text
ReadFile: "alpha\nbeta\ngamma\n" (17 bytes)
```

`filepath.Join` مسیر را با جداکننده‌ی درست سیستم‌عامل می‌سازد. `0o644` سطح دسترسی فایل است (صاحب فایل می‌تواند بخواند و بنویسد، بقیه فقط بخوانند). خروجی نشان می‌دهد دقیقاً همان چیزی را که نوشتیم پس گرفتیم: سه کلمه که هرکدام یک خط جدید دارند، در مجموع ۱۷ بایت. `%q` رشته را داخل گیومه و با `\n` قابل‌دیدن چاپ می‌کند، که وقتی به کاراکترهای نامرئی اهمیت می‌دهید به کار می‌آید.

خواندن فایلی که وجود ندارد خطا برمی‌گرداند و `os.IsNotExist(err)` در اجرای من `true` بود. (`errors.Is(err, fs.ErrNotExist)` هم کار می‌کند.)

`ReadFile` کل فایل را در حافظه می‌ریزد. برای یک فایل تنظیمات کوچک خوب است، ولی برای یک لاگ بزرگ اتلاف است. برای فایل‌های بزرگ فایل را باز کنید و با `bufio.Scanner` خط‌به‌خط بخوانید. اسم `bufio` از «buffered I/O» می‌آید: به‌جای اینکه برای هر بایت از سیستم‌عامل چیزی بخواهد، یک تکه‌ی بزرگ را یک‌جا می‌خواند و از آن تکه‌تکه به شما می‌دهد. فایل را مثل [توابع، defer و مدیریت خطا در Go](/fa/posts/go-functions-defer-errors/) با `defer` می‌بندیم:

```go
f, err := os.Open(path)
if err != nil { /* handle */ }
defer f.Close()
sc := bufio.NewScanner(f)
for n := 1; sc.Scan(); n++ {
	fmt.Printf("line %d: %s\n", n, sc.Text())
}
if err := sc.Err(); err != nil { /* handle */ }
```

```text
line 1: alpha
line 2: beta
line 3: gamma
```

هر بار `sc.Scan()` به خط بعد می‌رود و `true` برمی‌گرداند و `sc.Text()` همان خط را بدون خط جدیدِ آخرش می‌دهد. بعد از حلقه همیشه `sc.Err()` را چک کنید: `Scan` هم در آخر فایل و هم وقتی مشکلی پیش بیاید `false` برمی‌گرداند و فقط `Err` می‌گوید کدام اتفاق افتاده.

دقت کنید که `bufio.NewScanner(f)` یک فایل گرفت، ولی چیزهای دیگر را هم قبول می‌کند. ببینیم چرا.

## io.Reader و io.Writer

هر دو interface دقیقاً یک متد دارند:

```go
type Reader interface { Read(p []byte) (n int, err error) }
type Writer interface { Write(p []byte) (n int, err error) }
```

`Reader` یعنی «چیزی که می‌شود از آن بایت برداشت»: `Read` اسلایس `p` را پر می‌کند و می‌گوید چند بایت گذاشته. `Writer` یعنی «چیزی که می‌شود به آن بایت داد». نوع‌های زیادی در کتاب‌خانه‌ی استاندارد این متدها را دارند: `*os.File` هر دو را دارد و همین‌طور `*bytes.Buffer` (بافر قابل‌رشد داخل حافظه)، مقداری که `strings.NewReader` می‌دهد (از یک رشته می‌خواند) و `os.Stdout`.

پس تابعی که `io.Writer` می‌گیرد اهمیت نمی‌دهد بایت‌ها کجا می‌روند. این هم تابع گزارش از ابتدای بحث:

```go
func report(w io.Writer, name string, n int) error {
	_, err := fmt.Fprintf(w, "report %s: %d items\n", name, n)
	return err
}
```

`fmt.Fprintf` همان `Printf` است با یک مقصد: متن را قالب‌بندی می‌کند و در `w` می‌نویسد. `report` را سه بار صدا زدم، با یک فایل، یک بافر و `os.Stdout`:

```text
file got: "report file: 3 items\n"
buffer got: "report buffer: 3 items\n"
report stdout: 3 items
```

یک تابع، یک کد، سه مقصد. خط اول چیزی است که بعد از نوشتن از فایل پس خواندم، خط دوم محتوای بافر است و خط سوم مستقیم در ترمینال چاپ شد. برای همین هم تست این تابع آسان است: در تست یک `bytes.Buffer` می‌دهید و رشته‌اش را با چیزی که انتظار دارید مقایسه می‌کنید، بدون هیچ فایلی.

کتاب‌خانه‌ی استاندارد `io.Copy(dst, src)` را هم دارد که هر reader را به هر writer وصل می‌کند و همه‌ی بایت‌ها را منتقل می‌کند:

```go
n, _ := io.Copy(os.Stdout, strings.NewReader("copied from a string\n"))
```

```text
copied from a string
io.Copy bytes: 21
```

۲۱ بایت رشته را به ترمینال کپی کرد و گفت چند بایت منتقل کرده. `fmt.Fprintf`، `bufio.NewScanner` و، همان‌طور که الان می‌بینیم، `json.NewEncoder` همه همین interfaceها را می‌گیرند و برای همین مثل تکه‌های یک لوله به هم وصل می‌شوند.

## JSON با struct tag

JSON قالبی است که بیشتر برنامه‌ها برای تبادل داده به کار می‌برند. پکیج `encoding/json` بین مقدارهای Go و متن JSON تبدیل می‌کند. تبدیل مقدار Go به JSON را **marshal** می‌گویند و برعکسش را **unmarshal**.

structهای Go فیلدهایی مثل `Name` دارند، ولی کلیدهای JSON معمولاً با حرف کوچک هستند. **struct tag**، یعنی رشته‌ی بین بک‌کوت بعد از فیلد، به پکیج می‌گوید کدام کلید را به کار ببرد:

```go
type User struct {
	Name     string   `json:"name"`
	Age      int      `json:"age"`
	Email    string   `json:"email,omitempty"`
	Tags     []string `json:"tags,omitempty"`
	password string
}
```

دو نکته‌ی مهم اینجاست. `omitempty` یعنی «اگر فیلد مقدار صفر دارد، کلید را نیاور» (رشته‌ی خالی، `0`، اسلایس خالی یا nil). و `password` با حرف کوچک شروع می‌شود، پس unexported است و `encoding/json` فقط فیلدهای exported را می‌بیند. هیچ‌وقت نوشته نمی‌شود، که برای یک رمز همان چیزی است که می‌خواهیم:

```go
b, _ := json.Marshal(User{Name: "Roham", Age: 30, password: "secret"})
```

```text
{"name":"Roham","age":30}
```

خروجی فقط `name` و `age` دارد. `email` و `tags` به خاطر `omitempty` نیامدند و `password` به خاطر اینکه unexported است. وقتی `Email` و `Tags` مقدار داشته باشند، `json.MarshalIndent(u, "", "  ")` خروجی خوانا با تورفتگی دو فاصله می‌دهد:

```text
{
  "name": "Roham",
  "age": 30,
  "email": "r@example.com",
  "tags": [
    "go",
    "backend"
  ]
}
```

`json.Unmarshal(b, &u2)` برعکس عمل می‌کند. پوینتر لازم دارد، چون باید متغیر شما را پر کند. چاپ نتیجه با `%+v` (که نام فیلدها را نشان می‌دهد) این بود: `{Name:Roham Age:30 Email:r@example.com Tags:[go backend] password:}`. همه‌چیز برگشت و `password` خالی ماند، چون هیچ‌وقت در JSON نبود.

## جریان‌خوانی با Encoder و Decoder

`json.Marshal` یک اسلایس بایت برمی‌گرداند که خودتان باید جایی بنویسیدش. اگر مقصد را از قبل دارید، راه کوتاه‌تری هست. `json.NewEncoder(w)` هر `io.Writer` را می‌گیرد و `json.NewDecoder(r)` هر `io.Reader` را. اینجاست که ایده‌ی interface نتیجه می‌دهد.

هر بار `Encode` یک مقدار را همراه با یک خط جدید می‌نویسد؛ پس چند بار صدا زدنش فایلی می‌دهد که در هر خطش یک مقدار JSON است (معمولاً به این JSON Lines می‌گویند). برای خواندنش، `Decode` را در یک حلقه صدا بزنید تا `io.EOF` برگرداند، یعنی ورودی تمام شده:

```go
enc := json.NewEncoder(jf) // jf is an *os.File
enc.Encode(User{Name: "x", Age: 1})
enc.Encode(User{Name: "y", Age: 2})
// later: reopen and decode until io.EOF
dec := json.NewDecoder(jf)
for {
	var v User
	if err := dec.Decode(&v); err == io.EOF {
		break
	} else if err != nil { /* handle */ }
	fmt.Printf("decoded: %+v\n", v)
}
```

```text
decoded: {Name:x Age:1 Email: Tags:[] password:}
decoded: {Name:y Age:2 Email: Tags:[] password:}
```

هر دو کاربر برگشتند. `Tags:[]` فقط شکل چاپ `%+v` برای اسلایس nil است: کلید نبود، پس فیلد مقدار صفرش را نگه داشت. مزیت این سبک این است که هیچ‌وقت کل فایل در حافظه نیست و هر بار فقط یک مقدار دارید.

## فیلد ناشناس و map[string]any

JSON دنیای واقعی همیشه با struct شما یکی نیست. به‌طور پیش‌فرض، کلیدی که struct ندارد بی‌صدا نادیده گرفته می‌شود. گاهی ترجیح می‌دهید بدانید. decoder را با `DisallowUnknownFields` می‌شود سخت‌گیر کرد:

```go
in := `{"name":"Roham","age":30,"nickname":"r"}`
d := json.NewDecoder(strings.NewReader(in))
d.DisallowUnknownFields()
fmt.Println("strict err:", d.Decode(&u3))
```

```text
lenient err: <nil> Roham
strict err: json: unknown field "nickname"
```

خط اول رفتار پیش‌فرض است: خطا نیست، `name` خوانده شد و `nickname` دور ریخته شد. خط دوم decoder سخت‌گیر است که همان ورودی را رد می‌کند و کلید اضافه را اسم می‌برد.

وقتی شکل JSON را اصلاً نمی‌دانید می‌شود در `map[string]any` decode کرد. کار می‌کند، ولی ببینید عددها چه می‌شوند:

```go
var m map[string]any
json.Unmarshal([]byte(`{"id":7,"name":"x","ok":true,"list":[1,2]}`), &m)
fmt.Printf("%T %v | %T\n", m["id"], m["id"], m["list"])
```

```text
float64 7 | []interface {}
```

`id` در JSON برابر `7` بود، ولی در Go یک `float64` است، چون JSON فقط یک نوع عدد دارد. آرایه‌ها به `[]any` تبدیل می‌شوند (که `[]interface {}` چاپ می‌شود). `float64` همه‌ی عددهای صحیح بزرگ را دقیق نگه نمی‌دارد؛ پس شناسه‌های خیلی بزرگ می‌توانند از این راه دقتشان را از دست بدهند. اگر شکل داده را می‌دانید، struct را ترجیح بدهید.

## خطاها چه شکلی‌اند

JSON‌ای که از بیرون می‌آید اغلب خراب است؛ پس دیدن پیام خطاها کمک می‌کند. این‌ها برای سه ورودی بد هستند:

```text
syntax: invalid character '}' looking for beginning of object key string
truncated: unexpected end of JSON input
type: json: cannot unmarshal string into Go struct field User.age of type int
```

اولی از `{"name": "x",}` می‌آید که ویرگول آخرش در JSON مجاز نیست. دومی از `{"name": "x"` است که پیش از آکولاد بسته قطع شده. سومی از `"age":"thirty"` است: JSON معتبر است، ولی رشته در فیلد `int` نمی‌نشیند و پیام اسم فیلد را می‌گوید. در اجرای من بعد از این خطای سوم، فیلد `Name` هنوز پر شده بود (`x`) و `Age` صفر مانده بود: `Unmarshal` ادامه داد و ناهماهنگی نوع را آخر سر گزارش کرد.

## جاهایی که خطا بی‌صدا می‌شود

- بلافاصله بعد از چک کردن خطای `os.Open`، `defer f.Close()` بزنید و بعد از حلقه‌ی scan هم `sc.Err()` را چک کنید. وگرنه خواندنِ شکست‌خورده مثل پایان عادی فایل به نظر می‌رسد.
- `Scanner` به‌طور پیش‌فرض برای هر خط حداکثر ۶۴ کیلوبایت (KiB) جا دارد. خط بلندتر باعث می‌شود scan با خطا متوقف شود؛ برای چنین ورودی‌ای با `sc.Buffer` بافر بزرگ‌تری بدهید.
- `encoding/json` فیلدهای با حرف کوچک (unexported) را بدون هیچ خطایی رد می‌کند. اگر فیلدی همیشه مرموزانه خالی است، حرف اولش را نگاه کنید.
- `Unmarshal` پوینتر می‌خواهد. و یادتان باشد عددها در `map[string]any` به `float64` تبدیل می‌شوند.
- فیلدهای ناشناس نادیده گرفته می‌شوند، مگر اینکه `DisallowUnknownFields` را صدا بزنید. غلط املایی در یک کلید فایل تنظیمات ممکن است ناپیدا بماند.

## تمرین

۱. تابع `countLines(r io.Reader) (int, error)` را با `bufio.Scanner` بنویسید و با `strings.NewReader` تستش کنید.
۲. یک slice از `User` را با `json.NewEncoder` در فایل ذخیره کنید و با `json.NewDecoder` دوباره بخوانید.
۳. فیلد `Nickname` را با تگ `json:"-"` اضافه کنید و ببینید چه می‌شود.

## قدم بعدی

«ساخت ابزار خط فرمان با Go»: فایل، `io.Reader`، `io.Writer` و JSON دقیقاً تکه‌هایی هستند که آن نوشته کنار هم می‌گذارد و یک ابزار خط فرمان می‌سازد.
