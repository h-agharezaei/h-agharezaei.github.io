+++
date = '2026-12-30T10:00:00+03:30'
draft = false
title = 'Smart Pointerها: Box، Rc و RefCell در Rust'
description = 'Smart pointerها در Rust در عمل: Box برای داده‌ی heap و نوع‌های بازگشتی، Deref و Drop، مالکیت مشترک با Rc، تغییرپذیری درونی با RefCell و شکستن چرخه با Weak.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "smart-pointers", "box", "rc", "refcell", "intermediate"]
cover = { image = "/images/covers/rust-smart-pointers.fa.png", alt = "Smart Pointerها: Box، Rc و RefCell در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-closures-iterators/) یک `Box<dyn Fn>` برگرداندیم و قول دادیم توضیحش بدهیم. **Smart pointer** ساختاری است که مثل pointer رفتار می‌کند، ولی مالک داده هم هست و وقتی از بین می‌رود کدی اجرا می‌کند. یکی‌اش را از قبل می‌شناسید: `String` و `Vec` مالک حافظه‌ی heap هستند. این مقاله سه تا از پرکاربردترین‌ها را پوشش می‌دهد: `Box`، `Rc` و `RefCell`. روی [ownership](/fa/posts/rust-ownership/) بنا شده است: هر کدام برای جایی وجود دارد که مالکیت و borrow ساده کافی نیست.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها و پیام‌های کامپایلر از همان اجراها کپی شده‌اند.

## Box: یک مالک، داده روی heap

`Box<T>` مقدار را روی heap می‌گذارد و فقط یک pointer روی stack نگه می‌دارد. کاربرد کلاسیکش نوع‌های بازگشتی است. بدون `Box` یک cons list کامپایل نمی‌شود:

```rust
enum List {
    Cons(i32, List),
    Nil,
}
```

```text
error[E0072]: recursive type `List` has infinite size
2 |     Cons(i32, List),
  |               ---- recursive without indirection
help: insert some indirection (e.g., a `Box`, `Rc`, or `&`) to break the cycle
```

کامپایلر باید اندازه‌ی `List` را بداند و `List`ی که داخلش `List` دارد پایان ندارد. اندازه‌ی `Box` ثابت است (یک pointer)، پس این نسخه کار می‌کند:

```rust
enum List {
    Cons(i32, Box<List>),
    Nil,
}
// list = Cons(1, Box::new(Cons(2, Box::new(Cons(3, Box::new(Nil))))))
// a recursive sum over it prints: sum = 6
```

کاربرد رایج دیگر `Box<dyn Trait>` است: مقدارهایی با نوع‌های مختلف پشت یک trait، مثل مثال closure مقاله‌ی قبل. اگر trait به نام `Shape` را `Square` و `Circle` پیاده کرده باشند، `Vec<Box<dyn Shape>>` هر دو را نگه می‌دارد و صدا زدن `area()` روی هرکدام `4` و `3.14` چاپ کرد. فراخوانی متد در زمان اجرا از طریق vtable انجام می‌شود، شبیه interface در Go.

## Deref و Drop

`Box<T>` ویژگی **Deref** را پیاده کرده است، پس `*b` مقدار داخلی را می‌دهد. کامپایلر **deref coercion** هم اعمال می‌کند: برای هماهنگ کردن نوع‌ها خودکار `Deref` را دنبال می‌کند. `&Box<String>` به `&String` و بعد `&str` تبدیل می‌شود:

```rust
fn shout(s: &str) { println!("{}!", s.to_uppercase()); }

let b = Box::new(String::from("hello"));
shout(&b); // &Box<String> -> &String -> &str
```

برای نوع‌های خودتان هم کار می‌کند: `Deref` را با `type Target = String` پیاده کنید تا `shout(&w)` و `w.len()` هر دو کامپایل شوند. **Drop** نیمه‌ی دیگر است: متد `drop` آن در پایان scope و به ترتیب معکوس تعریف اجرا می‌شود. من `wrapped` بعد `a` و بعد `b` را ساختم و هرکدام در `drop` چیزی چاپ می‌کرد:

```text
end of main
drop b
drop a
drop wrapped
```

## Rc: مالکیت مشترک

گاهی یک مقدار واقعاً چند مالک دارد، مثل گرهی که دو list مشترکاً دارند. `Rc<T>` (reference counted) این را ممکن می‌کند و مقدار وقتی آخرین مالک برود آزاد می‌شود. `Rc::clone` فقط یک شمارنده را زیاد می‌کند و داده را کپی نمی‌کند:

```rust
let a = Rc::new(String::from("shared"));
println!("after new: {}", Rc::strong_count(&a));
let b = Rc::clone(&a);
println!("after clone b: {}", Rc::strong_count(&a));
{
    let c = Rc::clone(&a);
    println!("in scope: {}", Rc::strong_count(&a));
}
println!("after scope: {}", Rc::strong_count(&a));
drop(b);
println!("after drop(b): {}", Rc::strong_count(&a));
```

```text
after new: 1
after clone b: 2
in scope: 3
after scope: 2
after drop(b): 1
```

`Rc` فقط دسترسی مشترک (`&`) می‌دهد. و thread-safe نیست، چون شمارنده‌اش atomic نیست. کامپایلر این را اعمال می‌کند:

```text
error[E0277]: `Rc<i32>` cannot be sent between threads safely
  = help: within `{closure@src/bin/rc_thread.rs:6:27: 6:34}`, the trait `Send` is not implemented for `Rc<i32>`
note: required by a bound in `spawn`
```

برای thread، کتاب‌خانه‌ی استاندارد `Arc` را دارد که نسخه‌ی atomic است. اینجا از آن استفاده نمی‌کنیم.

## RefCell: تغییرپذیری درونی

قانون‌های borrowing معمولاً در زمان کامپایل چک می‌شوند. **RefCell** این چک را به زمان اجرا می‌برد تا بتوانید از طریق یک reference مشترک مقدار را تغییر دهید. به این **interior mutability** می‌گویند. `borrow()` و `borrow_mut()` همان قانون را دارند (چند خواننده یا یک نویسنده)، ولی تخلف به جای خطای کامپایل یک panic است:

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

(در آموزش‌های قدیمی‌تر `already borrowed: BorrowMutError` را می‌بینید؛ در نسخه‌ی 1.90 متن همین است که بالا آمد.) `try_borrow_mut` یک `Result` برمی‌گرداند، پس می‌توانید به جای crash کردن تعارض را مدیریت کنید.

## ترکیب Rc و RefCell

`Rc` چند مالک می‌دهد ولی فقط دسترسی خواندنی؛ `RefCell` امکان تغییر می‌دهد. ترکیب `Rc<RefCell<T>>` در کد تک‌threadی همان state مشترکِ قابل تغییر است:

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

## چرخه‌ی reference و Weak

اگر دو `Rc` به هم اشاره کنند، هیچ‌کدام از شمارنده‌ها صفر نمی‌شود. در demo به نام `cycle`، `a` و `b` هرکدام دیگری را نگه می‌داشتند، در پایان `main` هر دو شمارنده `2` بود و هیچ خط `drop` چاپ نشد. این یک memory leak است و Rust آن را کد safe حساب می‌کند.

راه‌حل **Weak** است: pointer‌ای که مالک نیست. `Rc::downgrade` آن را می‌سازد و `upgrade()` یک `Option<Rc<T>>` برمی‌گرداند که وقتی مقدار رفته باشد `None` است. در یک درخت، والد با `Rc` مالک فرزندهاست و فرزند با `Weak` به والد برمی‌گردد:

```rust
struct Node {
    name: &'static str,
    parent: RefCell<Weak<Node>>,
    children: RefCell<Vec<Rc<Node>>>,
}
```

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

وقتی `root` از scope خارج می‌شود حذف می‌شود، با اینکه `leaf` هنوز به آن اشاره دارد، چون فقط یک `Weak` است. بعدش `upgrade()` مقدار `None` می‌دهد.

## چند نکته‌ی مهم

- اول مالکیت و borrow ساده را امتحان کنید. این نوع‌ها برای جاهایی‌اند که borrow checker نمی‌تواند ثابت کند، نه راهی برای دور زدنش.
- `RefCell` خطاها را از زمان کامپایل به زمان اجرا می‌برد. guardهای `borrow_mut` را کوتاه‌عمر نگه دارید یا از `try_borrow_mut` استفاده کنید.
- `Rc::clone(&a)` ارزان است و مالکیت را آشکار می‌کند؛ من آن را به `a.clone()` ترجیح می‌دهم.
- `Rc` و `RefCell` تک‌threadی‌اند. برای thread از `Arc` و `Mutex` استفاده کنید.
- در Go، garbage collector اشاره‌گرهای مشترک را ضمنی می‌کند و لازم نیست مالک‌ها را بشمارید. Rust انتخاب را به عهده‌ی شما می‌گذارد و هزینه‌ی GC ندارد.

## تمرین

1. یک variant از `Cons` بنویسید که `Rc<List>` نگه دارد تا دو list یک دُم مشترک داشته باشند، و `Rc::strong_count` آن دُم را چاپ کنید.
2. یک log از نوع `Rc<RefCell<Vec<String>>>` بسازید که دو closure مشترکاً در آن بنویسند و در پایان چاپش کنید.
3. عمداً panic مربوط به `RefCell` را ایجاد کنید و بعد آن را با `try_borrow_mut` جایگزین کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ تست‌نویسی و مستندسازی در Rust می‌رویم.
