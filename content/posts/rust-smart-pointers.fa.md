+++
date = '2026-12-30T10:00:00+03:30'
draft = false
title = 'Smart Pointerها: Box، Rc و RefCell در Rust'
description = 'Smart pointerها در Rust در عمل: Box برای داده‌ی heap و نوع‌های بازگشتی، Deref و Drop، مالکیت مشترک با Rc، تغییرپذیری درونی با RefCell و شکستن چرخه با Weak.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "smart-pointers", "box", "rc", "refcell", "intermediate"]
cover = { image = "/images/covers/rust-smart-pointers.fa.png", alt = "Smart Pointerها: Box، Rc و RefCell در Rust", hiddenInSingle = true }
+++

قاعده‌ی ownership در Rust ساده است: هر مقدار یک مالک دارد و وقتی مالک از scope بیرون می‌رود، مقدار از بین می‌رود. بیشتر وقت‌ها دقیقاً همین را می‌خواهید. ولی چند موقعیت با این قاعده جور درنمی‌آید. نوعی که خودش را در خود دارد، مثل یک لیست پیوندی، اندازه‌ی ثابتی ندارد. مقداری که دو جای برنامه هر دو باید مالکش باشند، مالک یگانه ندارد. و مقداری که باید تغییرش بدهید در حالی که چند جای کد یک reference مشترک به آن دارند، قاعده‌های borrowing را می‌شکند. برای این موقعیت‌ها کتابخانه‌ی استاندارد سه ابزار کوچک دارد: `Box` و `Rc` و `RefCell`. هر کدام یک {{< term "smart-pointer" "smart pointer" >}} است، و این مقاله می‌گوید این یعنی چه، هر ابزار چه مشکلی را حل می‌کند و چه هزینه‌ای دارد.

این مقاله روی [Ownership در Rust](/fa/posts/rust-ownership/) و [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/) بنا شده، و `Box<dyn Fn>` را توضیح می‌دهد که در [مقاله‌ی قبل](/fa/posts/rust-closures-iterators/) درباره‌ی closure‌ها بدون توضیح به کار بردم.

> همه‌ی کدهای زیر را با Rust نسخه‌ی 1.90 کامپایل و اجرا کرده‌ام (همان نسخه‌ی اجرای اول). خروجی‌ها و پیام‌های کامپایلر از همان اجراها هستند. چند برنامه‌ی کوچک (یک `Rc` که تغییر داده می‌شود، تغییر دادن از پشت reference مشترک، و یک `RefCell` که از پشت reference مشترک استفاده می‌شود) در demo اصلی نبودند؛ آن‌ها را برای همین مقاله نوشتم و جداگانه اجرا کردم. از پیام‌ها خط «For more information…» و چند خط `note:` را حذف کرده‌ام.

## smart pointer یعنی چه

reference معمولی (`&T`) فقط به مقداری اشاره می‌کند که کس دیگری مالکش است. **smart pointer** یک struct است که به یک مقدار اشاره می‌کند و صاحبش هم هست. مثل reference رفتار می‌کند (می‌توانید `*x` بنویسید و به مقدار برسید)، ولی وقتی از بین می‌رود کدی هم اجرا می‌کند. دو تایش را بی‌آنکه اسمش را بدانید قبلاً به کار برده‌اید: `String` صاحب متنی در heap است و وقتی از بین برود آن را آزاد می‌کند، و `Vec<T>` همین کار را برای عنصرهایش می‌کند.

دو واژه که پایین‌تر به کار می‌برم. **stack** جایی است که متغیرهای تابع با اندازه‌ی معلوم و ثابت در آن زندگی می‌کنند و وقتی تابع برگردد خودکار پاک می‌شود. **heap** ناحیه‌ی بزرگ‌تری است که مقدار می‌تواند هر اندازه‌ای داشته باشد و تا وقتی کسی مالکش است بماند. اشاره‌گر به یک مقدار heap چیز کوچکی با اندازه‌ی ثابت است که می‌تواند روی stack بنشیند.

## Box: مقدار را به heap ببر

`Box<T>` ساده‌ترین smart pointer است. مقدار را به heap می‌برد و یک اشاره‌گر به آن را روی stack نگه می‌دارد. فقط یک مالک دارد، پس قاعده‌های ownership همان می‌ماند: وقتی `Box` از بین برود، مقدار heap آزاد می‌شود.

چرا کسی این را بخواهد؟ دلیل کلاسیک، نوعی است که خودش را در خود دارد. یک لیست پیوندی به سبک «cons list» را در نظر بگیرید: لیست یا یک مقدار است و بعدش یک لیست دیگر، یا پایان:

```rust
enum List {
    Cons(i32, List),
    Nil,
}
```

```text
error[E0072]: recursive type `List` has infinite size
 --> src/bin/cons_bad.rs:1:1
  |
1 | enum List {
  | ^^^^^^^^^
2 |     Cons(i32, List),
  |               ---- recursive without indirection
  |
help: insert some indirection (e.g., a `Box`, `Rc`, or `&`) to break the cycle
  |
2 |     Cons(i32, Box<List>),
  |               ++++    +
```

Rust باید اندازه‌ی هر نوع را در زمان کامپایل بداند. `List` چقدر جا می‌گیرد؟ یک `i32` و یک `List` دیگر را دارد، که آن هم یک `i32` و یک `List` دیگر دارد، و همین‌طور بی‌پایان. پیام می‌گوید «infinite size» و «recursive without indirection». «indirection» یعنی: لیست درونی را اینجا ذخیره نکن، یک اشاره‌گر به آن ذخیره کن. `Box` دقیقاً همین است، و اشاره‌گر اندازه‌ی ثابت دارد، هر چیزی که به آن اشاره کند:

```rust
enum List {
    Cons(i32, Box<List>),
    Nil,
}
```

حالا `Cons(1, Box::new(Cons(2, Box::new(Cons(3, Box::new(Nil))))))` کامپایل می‌شود. در demo یک متد بازگشتی `sum` اضافه کردم که عددها را جمع می‌کند و چاپ می‌کند:

```text
sum = 6
```

کاربرد رایج دوم `Box<dyn Trait>` است. گاهی می‌خواهید یک مجموعه از مقدارهایی با نوع‌های مختلف داشته باشید که یک رفتار مشترک دارند. `Vec` می‌خواهد همه‌ی عنصرهایش هم‌اندازه باشند، و `Square` و `Circle` دو نوع جدا هستند. داخل box گذاشتنشان و صدا زدنشان از طریق trait این را حل می‌کند. در demo یک trait به اسم `Shape` متد `area` دارد و `Square` و `Circle` آن را پیاده می‌کنند:

```rust
let shapes: Vec<Box<dyn Shape>> = vec![Box::new(Square(2.0)), Box::new(Circle(1.0))];
for s in &shapes {
    println!("area = {}", s.area());
}
```

```text
area = 4
area = 3.14
```

`dyn Shape` یعنی «نوعی که `Shape` را پیاده کرده، و کدام نوع بودنش در زمان اجرا مشخص می‌شود». هر box به یاد دارد چه نوعی را نگه داشته، و فراخوانی `area()` هنگام اجرا به متد درست می‌رسد. این همان ایده‌ی مقدار interface در Go است. و `Box<dyn Fn(i32) -> i32>` در مقاله‌ی closure هم همین بود: جعبه‌ای که «یک closure با این امضا» را نگه می‌دارد.

## Deref و Drop: چه چیزی آن را «smart» می‌کند

دو trait باعث می‌شوند یک نوع مثل smart pointer رفتار کند، و هر دو را می‌توانید خودتان پیاده کنید.

**`Deref`** اجازه می‌دهد `*b` بنویسید و مقدار داخل را بگیرید. کاری هم که کامپایلر برایتان انجام می‌دهد به آن بستگی دارد، یعنی **deref coercion**: وقتی تابعی `&str` می‌خواهد و شما `&Box<String>` می‌دهید، کامپایلر قدم‌به‌قدم `Deref` را دنبال می‌کند (`&Box<String>` به `&String` و بعد `&str`) تا نوع‌ها جور شوند. یک تابع کوچک که `&str` می‌گیرد، و یک نوع `Wrapper` که خودم نوشتم و `Deref` را با `type Target = String` پیاده می‌کند:

```rust
fn shout(s: &str) { println!("{}!", s.to_uppercase()); }

let b = Box::new(String::from("hello"));
shout(&b); // &Box<String> -> &String -> &str

let w = Wrapper(String::from("wrapped"));
shout(&w);
println!("len = {}", w.len());
```

```text
HELLO!
WRAPPED!
len = 7
```

هر دو فراخوانی `shout` کامپایل می‌شوند، با اینکه هیچ‌کدام از آرگومان‌ها `&str` نیست. و `w.len()` کار می‌کند چون کامپایلر از `Wrapper` رد می‌شود و به `String` داخلش می‌رسد.

**`Drop`** نیمه‌ی دیگر است. متد `drop` آن وقتی که مقدار از scope بیرون می‌رود خودکار اجرا می‌شود. `Box` همین‌طور حافظه‌ی heap را آزاد می‌کند و یک فایل همین‌طور خودش را می‌بندد. اینجا `Wrapper` هم `Drop` را پیاده کرده و یک خط چاپ می‌کند تا ببینیم کِی. demo ابتدا `w` (همان «wrapped») را می‌سازد، بعد `_a` و بعد `_b`، و `main` تمام می‌شود:

```text
end of main
drop b
drop a
drop wrapped
```

اول «end of main» چاپ می‌شود، و بعد مقدارها به ترتیب عکسِ ساخته‌شدن از بین می‌روند: `b`، بعد `a`، بعد `wrapped`. این ترتیب معکوس قاعده است: آخرین ساخته‌شده اول از بین می‌رود، پس یک مقدار می‌تواند با خیال راحت به مقدارهای قبل از خودش وابسته باشد.

## Rc: چند مالک

`Box` یک مالک دارد. گاهی یک مقدار واقعاً چند مالک دارد: گرهی را در نظر بگیرید که دو لیست مختلف هر دو به آن اشاره می‌کنند. هر کس آخر از همه آن را رها کرد باید آزادش کند، و هیچ‌کس نباید زودتر آزادش کند. `Rc<T>` («reference counted»، یعنی شمارنده‌دار) این کار را می‌کند. تعداد مالک‌ها را می‌شمارد و وقتی شمارنده به صفر برسد مقدار آزاد می‌شود. `Rc::clone` داده را کپی نمی‌کند؛ فقط یکی به شمارنده اضافه می‌کند و یک اشاره‌گر دیگر به همان داده به شما می‌دهد:

```rust
let a = Rc::new(String::from("shared"));
println!("after new: {}", Rc::strong_count(&a));
let b = Rc::clone(&a);
println!("after clone b: {}", Rc::strong_count(&a));
{
    let c = Rc::clone(&a);
    println!("in scope, c = {c}: {}", Rc::strong_count(&a));
}
println!("after scope: {}", Rc::strong_count(&a));
drop(b);
println!("after drop(b): {}", Rc::strong_count(&a));
```

```text
after new: 1
after clone b: 2
in scope, c = shared: 3
after scope: 2
after drop(b): 1
```

شمارنده این‌طور می‌رود: ۱ (فقط `a`)، ۲ (بعد از `b`)، ۳ (داخل آکولاد، با `c`)، دوباره ۲ وقتی `c` از scope بیرون می‌رود، و ۱ وقتی `b` را دستی drop می‌کنیم. وقتی آخرین مالک برود رشته آزاد می‌شود.

`Rc` دو محدودیت دارد. اول، فقط دسترسی مشترک می‌دهد، نه اجازه‌ی تغییر مقدار:

```rust
let a = Rc::new(5);
*a += 1;
```

```text
error[E0594]: cannot assign to data in an `Rc`
 --> src/bin/x_rcmut.rs:5:5
  |
5 |     *a += 1;
  |     ^^^^^^^ cannot assign
  |
  = help: trait `DerefMut` is required to modify through a dereference, but it is not implemented for `Rc<i32>`
```

منطقی است: اگر سه مالک هر وقت دلشان می‌خواست مقدار را عوض می‌کردند، به همان مشکلی برمی‌گشتیم که قاعده‌های borrowing برای جلوگیری از آن هستند. دوم، `Rc` برای به‌اشتراک‌گذاشتن بین thread‌ها امن نیست، چون شمارنده‌اش را بدون هیچ محافظتی در برابر به‌روزرسانی هم‌زمان دو thread تغییر می‌دهد. کامپایلر این را اعمال می‌کند. تلاش برای بردن یک `Rc` به داخل thread:

```rust
let a = Rc::new(5);
let h = thread::spawn(move || println!("{a}"));
```

```text
error[E0277]: `Rc<i32>` cannot be sent between threads safely
   --> src/bin/rc_thread.rs:6:27
    |
  6 |     let h = thread::spawn(move || println!("{a}"));
    |             ------------- -------^^^^^^^^^^^^^^^^
    |             |             |
    |             |             `Rc<i32>` cannot be sent between threads safely
    |             |             within this `{closure@src/bin/rc_thread.rs:6:27: 6:34}`
    |             required by a bound introduced by this call
    |
    = help: within `{closure@src/bin/rc_thread.rs:6:27: 6:34}`, the trait `Send` is not implemented for `Rc<i32>`
```

جمله‌ی کلیدی این است: «the trait `Send` is not implemented for `Rc<i32>`». `Send` یک نشانه است که می‌گوید «این نوع را می‌شود به thread دیگر منتقل کرد»، و `Rc` آن را ندارد. `Send` و نسخه‌ی thread-safe `Rc` را که `Arc` نام دارد در مقاله‌ی [thread‌ها](/fa/posts/rust-concurrency-threads/) توضیح می‌دهم. (خط‌های `note:` را که به کتابخانه‌ی استاندارد اشاره می‌کردند حذف کرده‌ام.)

## RefCell: تغییر دادن از پشت reference مشترک

حالا نیمه‌ی دیگر ماجرا: تغییر دادن. قاعده‌های borrowing می‌گویند از پشت reference مشترک (`&`) فقط می‌توان خواند:

```rust
let v = vec![1];
let r = &v;
r.push(2);
```

```text
error[E0596]: cannot borrow `*r` as mutable, as it is behind a `&` reference
 --> src/bin/x_shared_mut.rs:4:5
  |
4 |     r.push(2);
  |     ^ `r` is a `&` reference, so the data it refers to cannot be borrowed as mutable
```

معمولاً همین را می‌خواهید. ولی گاهی می‌دانید کد درست است و کامپایلر نمی‌تواند ثابتش کند، مخصوصاً وقتی چند مالک `Rc` هر کدام باید بتوانند مقدار را تغییر بدهند. `RefCell<T>` ابزار این کار است. همان قاعده‌های borrowing را از زمان کامپایل به زمان اجرا می‌برد: `borrow()` یک دید مشترک می‌دهد، `borrow_mut()` یک دید تغییرپذیر، و سلول آن‌ها را هنگام اجرای برنامه می‌شمارد. به تغییر دادن مقدار از پشت یک reference مشترک می‌گویند {{< term "interior-mutability" "interior mutability" >}}. همان تکه‌ای که بالا شکست خورد، وقتی وکتور داخل یک `RefCell` باشد کار می‌کند:

```rust
let c = RefCell::new(vec![1]);
let r = &c;
r.borrow_mut().push(2);
println!("{:?}", c.borrow());
```

```text
[1, 2]
```

قاعده هنوز «چند خواننده یا یک نویسنده» است، ولی اگر بشکنیدش خطای کامپایل نمی‌گیرید، panic می‌گیرید. اینجا demo یک قرض تغییرپذیر می‌گیرد و نگه می‌دارد، بعد سعی می‌کند دومی را بگیرد. اول `try_borrow_mut` را استفاده می‌کند که به‌جای panic یک `Result` برمی‌گرداند، و بعد `borrow_mut` را برای نشان دادن panic:

```rust
let c = RefCell::new(vec![1]);
let _first = c.borrow_mut();
match c.try_borrow_mut() {
    Ok(_) => println!("got it"),
    Err(e) => println!("try_borrow_mut failed: {e}"),
}
let _second = c.borrow_mut();
```

```text
try_borrow_mut failed: RefCell already borrowed

thread 'main' panicked at src/bin/refcell_panic.rs:10:21:
RefCell already borrowed
```

قرض اول `_first` هنوز زنده است، پس `try_borrow_mut` خطا برمی‌گرداند و ما چاپش می‌کنیم، و `borrow_mut` معمولی در خط آخر با همان پیام panic می‌کند. (در آموزش‌های قدیمی‌تر `already borrowed: BorrowMutError` را می‌بینید؛ با Rust 1.90 متن همان است که بالا آمد. خط یادداشت `RUST_BACKTRACE` را حذف کرده‌ام.) هزینه‌ی `RefCell` همین است: اشتباهی که کامپایلر می‌گرفت حالا در زمان اجرا یک crash است.

## Rc و RefCell با هم

`Rc` چند مالک می‌دهد ولی فقط دسترسی خواندنی. `RefCell` امکان تغییر می‌دهد. یکی را داخل دیگری بگذارید تا در کد تک‌threadی داده‌ی مشترکِ تغییرپذیر داشته باشید: `Rc<RefCell<T>>`. در demo دو closure هر کدام یک دسته به یک شمارنده‌ی یکسان دارند:

```rust
let counter = Rc::new(RefCell::new(Counter { hits: 0 }));
let a = Rc::clone(&counter);
let b = Rc::clone(&counter);
let inc_a = move || a.borrow_mut().hits += 1;
let inc_b = move || b.borrow_mut().hits += 10;
inc_a(); inc_b(); inc_a();
println!("hits = {}, owners = {}", counter.borrow().hits, Rc::strong_count(&counter));
```

```text
hits = 12, owners = 3
```

`inc_a` دو بار صدا زده می‌شود (هر بار ۱+) و `inc_b` یک بار (۱۰+)، پس `hits` برابر ۱۲ است. مالک‌ها سه‌تا هستند: خود `counter` و دو closure که هر کدام یک clone دارند.

## چرخه‌ی reference و Weak

شمردن مالک‌ها یک ضعف معروف دارد. اگر `a` به `b` اشاره کند و `b` به `a`، هرکدام مال دیگری است و هیچ‌کدام از شمارنده‌ها هرگز به صفر نمی‌رسد. در demo به اسم `cycle` دو گره به همین شکل همدیگر را نگه می‌دارند و برنامه چاپ می‌کند:

```text
a=2 b=2
```

هر دو شمارنده در پایان `main` برابر ۲ است. وقتی `main` تمام می‌شود، متغیرهای `a` و `b` از بین می‌روند و شمارنده‌ها را به ۱ می‌رسانند، ولی نه به ۰. گره‌ها `Drop` را پیاده کرده‌اند و وقتی آزاد شوند یک خط چاپ می‌کنند، و هیچ خط «drop»ی ظاهر نمی‌شود. حافظه هیچ‌وقت آزاد نمی‌شود. این یک نشت حافظه (memory leak) است و Rust آن را کد امن می‌داند: crash نیست و رفتار تعریف‌نشده نیست، فقط هدررفت است.

درمانش **`Weak`** است: اشاره‌گری که مالک نیست. `Rc::downgrade` از یک `Rc` آن را می‌سازد و به تعداد مالک‌ها اضافه نمی‌کند. برای استفاده `upgrade()` را صدا می‌زنید که `Option<Rc<T>>` برمی‌گرداند: تا وقتی مقدار زنده است `Some`، و وقتی رفت `None`. در یک درخت، والد‌ها فرزندانشان را با `Rc` نگه می‌دارند و فرزندها با `Weak` به والد برمی‌گردند:

```rust
struct Node {
    name: &'static str,
    parent: RefCell<Weak<Node>>,
    children: RefCell<Vec<Rc<Node>>>,
}
```

demo یک `leaf` می‌سازد، بعد داخل یک بلاک `root` را می‌سازد، `leaf` را فرزند `root` می‌کند و یک اشاره‌گر weak از `leaf` به `root` می‌دهد. شمارنده‌ها را چاپ می‌کند، از بلاک بیرون می‌آید و دوباره چاپ می‌کند:

```text
leaf parent = None
root: strong=1 weak=1
leaf: strong=2 weak=0
leaf parent = Some("root")
drop root
leaf parent = None
leaf: strong=1 weak=0
drop leaf
```

- `leaf parent = None`: اول `leaf` والدی ندارد.
- `root: strong=1 weak=1`: `root` یک مالک دارد (متغیر `root`) و یک اشاره‌گر weak (از `leaf`).
- `leaf: strong=2 weak=0`: `leaf` دو مالک دارد (متغیر `leaf` و فهرست `children` در `root`).
- `leaf parent = Some("root")`: `upgrade()` موفق است، چون `root` هنوز زنده است.
- `drop root`: بلاک تمام می‌شود. `root` فقط یک مالک قوی دارد، پس آزاد می‌شود، حتی با اینکه `leaf` هنوز به آن اشاره می‌کند، چون آن اشاره‌گر `Weak` است.
- `leaf parent = None`: حالا `upgrade()` مقدار `None` برمی‌گرداند.
- `leaf: strong=1 weak=0`: فهرست فرزندان `root` رفته، پس فقط متغیر `leaf` مالک `leaf` است. در پایان `main` خط `drop leaf` چاپ می‌شود.

## کِی سراغشان نروید

- **اول ownership و borrowing ساده.** این نوع‌ها برای حالتی هستند که borrow checker نمی‌تواند ثابتش کند، نه راهی برای دور زدنش. اگر یک `&` یا یک move جواب می‌دهد، همان را به کار ببرید.
- **`RefCell` خطای کامپایل را به crash تبدیل می‌کند.** guard‌های `borrow_mut` را کوتاه‌عمر نگه دارید، یا وقتی تداخل ممکن است از `try_borrow_mut` استفاده کنید.
- **به‌جای `a.clone()` بنویسید `Rc::clone(&a)`.** هر دو یک کار می‌کنند، ولی اولی روشن می‌کند که مالک اضافه می‌کنید، نه اینکه داده را کپی کنید. این سلیقه‌ی من است، نه قاعده.
- **`Rc` و `RefCell` برای یک thread هستند.** برای thread‌ها به خویشاوندان thread-safe آن‌ها نیاز دارید: `Arc` و `Mutex`.
- **مراقب چرخه‌ها باشید.** چرخه‌ای از `Rc`‌ها بی‌صدا نشت می‌کند. اگر فرزند باید به والدش اشاره کند، از `Weak` استفاده کنید.
- در Go garbage collector اشتراک‌گذاری را ضمنی می‌کند و هیچ‌وقت مالک نمی‌شمارید. Rust وادارتان می‌کند انتخاب کنید، و در عوض garbage collector‌ای در کار نیست.

## تمرین

۱. یک variant به اسم `Cons` اضافه کنید که `Rc<List>` نگه دارد تا دو لیست یک دُم مشترک داشته باشند، و `Rc::strong_count` آن دُم را چاپ کنید.
۲. یک لاگ `Rc<RefCell<Vec<String>>>` بسازید که بین دو closure مشترک باشد و در پایان چاپش کنید.
۳. عمداً panic مربوط به `RefCell` را تولید کنید و بعد قرض دوم را با `try_borrow_mut` عوض کنید.

## قدم بعدی

حالا که هسته‌ی زبان را دیدیم، کد باید راهی داشته باشد که ثابت کند کار می‌کند. مقاله‌ی بعد «تست و مستندسازی در Rust» است.
