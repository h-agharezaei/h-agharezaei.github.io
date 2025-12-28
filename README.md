# وبسایت شخصی من | My Personal Website

این وبسایت شخصی من است که با Hugo ساخته شده و روی GitHub Pages منتشر می‌شود.

**✨ ویژگی‌ها:**
- 🌐 دوزبانه (انگلیسی و فارسی)
- 📱 Responsive
- 🎨 تم مدرن PaperMod
- 🚀 Deploy خودکار با GitHub Actions

## 🚀 شروع سریع

### پیش‌نیازها

- [Hugo Extended](https://gohugo.io/installation/) نسخه 0.128.0 یا بالاتر

### اجرای محلی

```bash
# نصب وابستگی‌ها (اگر تم را به‌روز کرده‌اید)
git submodule update --init --recursive

# اجرای سرور محلی
hugo server -D

# سایت روی http://localhost:1313 در دسترس خواهد بود
# نسخه فارسی: http://localhost:1313/fa/
```

## 📝 نوشتن مقاله جدید

### مقاله انگلیسی:
```bash
hugo new content posts/my-new-post.en.md
```

### مقاله فارسی:
```bash
hugo new content posts/my-new-post.fa.md
```

سپس فایل ایجاد شده در `content/posts/` را ویرایش کنید و `draft = false` کنید تا منتشر شود.

## 📂 ساختار پروژه

```
.
├── content/          # محتوای سایت (مقالات و صفحات)
│   ├── posts/       # مقالات
│   ├── about.md     # صفحه درباره من
│   └── _index.md    # صفحه اصلی
├── themes/          # تم‌های Hugo
│   └── PaperMod/    # تم PaperMod
├── hugo.toml        # فایل پیکربندی اصلی
└── .github/
    └── workflows/   # GitHub Actions برای deploy خودکار
```

## 🚀 Deploy روی GitHub Pages

1. این repository را روی GitHub push کنید
2. در تنظیمات repository، به **Settings > Pages** بروید
3. در بخش **Build and deployment**، گزینه **GitHub Actions** را انتخاب کنید
4. هر بار که commit جدیدی push می‌کنید، سایت به‌طور خودکار build و deploy می‌شود

## 🎨 سفارشی‌سازی

برای تغییر تنظیمات سایت، فایل `hugo.toml` را ویرایش کنید:

- تغییر عنوان سایت
- اضافه کردن لینک‌های social media
- تنظیم منو
- و غیره...

## 📖 مستندات بیشتر

- [مستندات Hugo](https://gohugo.io/documentation/)
- [مستندات تم PaperMod](https://github.com/adityatelange/hugo-PaperMod/wiki)

## 📄 لایسنس

این پروژه برای استفاده شخصی است.
