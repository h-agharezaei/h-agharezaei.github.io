+++
date = '2026-12-06T10:00:00+03:30'
draft = false
title = 'کار با فایل، io.Reader/Writer و JSON در Go'
description = 'خواندن و نوشتن فایل با os و bufio، ترکیب‌پذیری io.Reader و io.Writer و encode و decode کردن JSON با encoding/json، همراه با پیام‌های خطای واقعی.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "json", "io"]
cover = { image = "/images/covers/go-file-io-json.fa.png", alt = "کار با فایل، io.Reader/Writer و JSON در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-testing-basics/) تست و benchmark نوشتیم. برنامه‌های واقعی فایل می‌خوانند و با JSON کار می‌کنند؛ این مقاله هر دو را پوشش می‌دهد. ایده‌ی اصلی دو interface خیلی کوچک است، `io.Reader` و `io.Writer`: وقتی آن‌ها را بشناسید، فایل، buffer، اتصال شبکه و خروجی استاندارد همه یک شکل پیدا می‌کنند.

> همه‌ی مثال‌ها را با Go 1.26 روی یک مک arm64 اجرا کرده‌ام. فایل‌ها در پوشه‌ای هستند که با `os.MkdirTemp` ساخته شده (در کدها `dir`) و آخر برنامه پاک می‌شود. خروجی‌ها از همان اجرا کپی شده‌اند.

## خواندن کل فایل و خط‌به‌خط

برای فایل‌های کوچک دو تابع کافی است:

```go
path := filepath.Join(dir, "notes.txt")
os.WriteFile(path, []byte("alpha\nbeta\ngamma\n"), 0o644)
data, err := os.ReadFile(path)
fmt.Printf("ReadFile: %q (%d bytes)\n", data, len(data))
```
```text
ReadFile: "alpha\nbeta\ngamma\n" (17 bytes)
```

مقدار `0o644` سطح دسترسی است. خواندن فایل ناموجود خطا برمی‌گرداند و در اجرای من `os.IsNotExist(err)` برابر `true` بود. (`errors.Is(err, fs.ErrNotExist)` هم کار می‌کند.)

`ReadFile` همه‌چیز را در حافظه می‌آورد. برای فایل‌های بزرگ، فایل را باز کنید و با **bufio.Scanner** خط‌به‌خط بخوانید. فایل را مثل [مقاله‌ی defer](/fa/posts/go-functions-defer-errors/) با `defer` ببندید:

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

بعد از حلقه حتماً `sc.Err()` را چک کنید: `Scan` هم در انتهای فایل و هم هنگام خطا `false` برمی‌گرداند.

## io.Reader و io.Writer

هر کدام از این دو interface فقط یک متد دارد:

```go
type Reader interface { Read(p []byte) (n int, err error) }
type Writer interface { Write(p []byte) (n int, err error) }
```

`*os.File` هر دو را پیاده‌سازی می‌کند؛ `*bytes.Buffer`، مقدار برگشتیِ `strings.NewReader` و `os.Stdout` هم همین‌طور. تابعی که `io.Writer` می‌گیرد اهمیتی نمی‌دهد بایت‌ها کجا می‌روند:

```go
func report(w io.Writer, name string, n int) error {
	_, err := fmt.Fprintf(w, "report %s: %d items\n", name, n)
	return err
}
```

آن را با یک فایل، یک buffer و stdout صدا زدم:

```text
file got: "report file: 3 items\n"
buffer got: "report buffer: 3 items\n"
report stdout: 3 items
```

برای همین تست کردن این تابع آسان است: یک `bytes.Buffer` بدهید و رشته را مقایسه کنید. `io.Copy(dst, src)` هر reader را به هر writer وصل می‌کند:

```go
n, _ := io.Copy(os.Stdout, strings.NewReader("copied from a string\n"))
```
```text
copied from a string
io.Copy bytes: 21
```

`fmt.Fprintf`، `bufio.NewScanner` و، همان‌طور که می‌بینیم، `json.NewEncoder` همه همین interfaceها را می‌گیرند و برای همین به هم وصل می‌شوند.

## JSON با struct tag

```go
type User struct {
	Name     string   `json:"name"`
	Age      int      `json:"age"`
	Email    string   `json:"email,omitempty"`
	Tags     []string `json:"tags,omitempty"`
	password string
}
```

**struct tag** کلید JSON را تعیین می‌کند. `omitempty` فیلدی را که zero value دارد حذف می‌کند. فیلد unexported یعنی `password` هرگز encode نمی‌شود، چون `encoding/json` فقط فیلدهای exported را می‌بیند:

```go
b, _ := json.Marshal(User{Name: "Roham", Age: 30, password: "secret"})
```
```text
{"name":"Roham","age":30}
```

اگر `Email` و `Tags` پر باشند، `json.MarshalIndent(u, "", "  ")` خروجی خوانا می‌دهد:

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

`json.Unmarshal(b, &u2)` مسیر برعکس است و pointer می‌خواهد. نتیجه این چاپ شد: `{Name:Roham Age:30 Email:r@example.com Tags:[go backend] password:}`؛ یعنی `password` خالی ماند.

## استریم با Encoder و Decoder

`json.NewEncoder(w)` روی هر `io.Writer` می‌نویسد و `json.NewDecoder(r)` از هر `io.Reader` می‌خواند. هر `Encode` یک مقدار و بعدش یک خط جدید می‌نویسد، یعنی فایلی به فرمت JSON Lines:

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

## فیلد ناشناخته و map[string]any

به‌طور پیش‌فرض کلیدهای اضافه بی‌صدا نادیده گرفته می‌شوند. می‌شود decoder را سخت‌گیر کرد:

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

وقتی شکل داده را نمی‌دانید، داخل `map[string]any` decode کنید. حواستان به عددها باشد:

```go
var m map[string]any
json.Unmarshal([]byte(`{"id":7,"name":"x","ok":true,"list":[1,2]}`), &m)
fmt.Printf("%T %v | %T\n", m["id"], m["id"], m["list"])
```
```text
float64 7 | []interface {}
```

`id` از نوع `float64` است و آرایه‌ها به `[]any` تبدیل می‌شوند. اگر می‌توانید، struct را ترجیح بدهید.

## پیام‌های خطا

```text
syntax: invalid character '}' looking for beginning of object key string
truncated: unexpected end of JSON input
type: json: cannot unmarshal string into Go struct field User.age of type int
```

این‌ها به ترتیب از `{"name": "x",}` (کامای اضافه)، `{"name": "x"` (ناقص) و `"age":"thirty"` آمده‌اند. آخری ناسازگاری نوع است و نام فیلد را هم می‌گوید.

## چند نکته که باید حواستان باشد

- بلافاصله بعد از چک خطای `os.Open`، `defer f.Close()` بنویسید و `sc.Err()` را چک کنید.
- `Scanner` به‌طور پیش‌فرض حداکثر ۶۴ کیبی‌بایت برای هر خط می‌خواند؛ برای خط‌های بلندتر از `sc.Buffer` استفاده کنید.
- فیلدهای با حرف کوچک بدون هیچ خطایی توسط `encoding/json` نادیده گرفته می‌شوند.
- `Unmarshal` pointer می‌خواهد و عددهای بزرگ در `map[string]any` به `float64` تبدیل می‌شوند.
- فیلد ناشناخته نادیده گرفته می‌شود، مگر اینکه `DisallowUnknownFields` را صدا بزنید.

## تمرین

۱. تابع `countLines(r io.Reader) (int, error)` را با `bufio.Scanner` بنویسید و با `strings.NewReader` تستش کنید.
۲. یک slice از `User` را با `json.NewEncoder` در فایل ذخیره کنید و با `json.NewDecoder` دوباره بخوانید.
۳. فیلد `Nickname` را با تگ `json:"-"` اضافه کنید و ببینید چه می‌شود.

## قدم بعدی

در مقاله‌ی بعد این قطعه‌ها را کنار هم می‌گذاریم و یک ابزار خط فرمان در Go می‌سازیم.
