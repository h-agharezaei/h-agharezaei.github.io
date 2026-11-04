+++
date = '2027-05-20T10:00:00+03:30'
draft = false
title = 'SSH و کلیدها'
description = 'SSH و کلیدها در یک پوشه‌ی موقت: ed25519 و RSA، اثرانگشت، قانون 0600، authorized_keys، known_hosts، ssh_config، agent و گواهی‌ها.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "ssh", "openssh", "keys", "security", "sshd", "macos"]
cover = { image = "/images/covers/linux-ssh-keys.fa.png", alt = "SSH و کلیدها", hiddenInSingle = true }
+++

ماه‌هاست با کلیدتان به یک سرور وارد می‌شوید. یک صبح ناگهان رمز عبور می‌خواهد. تا جایی که می‌دانید چیزی عوض نشده. در بیشتر موارد این‌طوری، SSH بی‌صدا تصمیم گرفته از کلید شما استفاده نکند، معمولاً به‌خاطر مجوز یک فایل، و خطای بلندی هم نداده است. برای اشکال‌یابی باید تصویر روشنی داشته باشید از اینکه کلید چه می‌کند، کدام فایل‌ها درگیرند و هر طرف چه چیزی را بررسی می‌کند.

این پست آن تصویر را در یک پوشه‌ی موقت می‌سازد، پس هیچ چیز واقعی در خطر نیست. ادامه‌ی [شبکه در Linux: ip، ss و nftables](/fa/posts/linux-networking-ip-ss-nftables/) است که هشدار داد قانون غلط فایروال روی SSH شما را بیرون می‌اندازد: SSH راهی است که بیشتر ما اصلاً با آن به سرورهای Linux می‌رسیم و ارزش دارد بدانیم چه چیزی را بررسی می‌کند.

این‌طور کار کردم و چه چیزی چیست. دستورهای کلید و config و گواهی را برای این بازنویسی روی یک مک با `OpenSSH_10.5p1, LibreSSL 3.3.6` (خروجی `ssh -V`) اجرا کردم، نه روی Linux. فقط در یک پوشه‌ی موقت کار کردم که در متن `<tmp>` نوشته‌ام، با مسیر صریح برای هر کلید، و هرگز به کلیدهای واقعی‌ام دست نزدم و به هیچ ماشین دوری وصل نشدم. ورود به `sshd` محلی و demo مربوط به agent از اجرای اصلی این پست روی OpenSSH 10.3 است؛ تکرارشان نکردم و پایین‌تر برچسب زده‌ام. جاهایی که Linux ممکن است فرق داشته باشد با عبارت «طبق man page» گفته‌ام. کلید خصوصی یک راز است؛ [مدیریت راز و کلید](/fa/posts/sec-secrets-management/) را ببینید.

## کلید چطور هویت شما را ثابت می‌کند

ایده‌ی اصلی ساده است. رمز عبور رازی است که برای سرور می‌فرستید، پس هر کس آن را ببیند یا نسخه‌ی سرور را بخواند می‌تواند دوباره استفاده‌اش کند. جفت‌کلید این را دور می‌زند: **کلید خصوصی** را نگه می‌دارید که هرگز از ماشین شما بیرون نمی‌رود و **کلید عمومی** متناظرش را به سرور می‌دهید. هنگام ورود سرور باید دلیلی بگیرد که کلید خصوصی دست شماست، و کلاینت این دلیل را می‌دهد بی‌آنکه خود کلید را بفرستد. طبق man page برنامه‌ی ssh، کلاینت «ثابت می‌کند به کلید خصوصی دسترسی دارد» و سرور بررسی می‌کند کلید عمومی متناظر مجاز است. در طرح کلی، دلیل یک امضا است که فقط کلید خصوصی می‌تواند بسازد و کلید عمومی می‌تواند راستی‌آزمایی‌اش کند.

دو فایل این را می‌برند. روی ماشین شما کلید خصوصی است (و کلید عمومی کنارش). روی سرور فایل `authorized_keys` در حساب شما کلیدهای عمومی مجاز به ورود را فهرست می‌کند. یک جفت جدا هم در جهت مخالف هست: سرور **host key** خودش را دارد تا بتوانید ببینید با سرور درست حرف می‌زنید. هر دو را می‌بینیم.

## جفت‌کلید

یک {< term "ssh-key-pair" "جفت‌کلید SSH" >} یک فایل خصوصی است که نزد شما می‌ماند و یک خط عمومی که به اشتراک می‌گذارید. سه جفت با `ssh-keygen -t ... -N '' -C demo@example` ساختم (بدون passphrase، چون موقت‌اند):

```
$ ls -l id_*    (mode, bytes, name)
-rw-------  505 id_ecdsa
-rw-r--r--  174 id_ecdsa.pub
-rw-------  399 id_ed25519
-rw-r--r--   94 id_ed25519.pub
-rw-------  2602 id_rsa
-rw-r--r--  566 id_rsa.pub
$ ssh-keygen -lf id_ed25519.pub
256 SHA256:BzSjfCOBGiFN6UNphueQRIsUkRuaehQIOE4B4H7eLOA demo@example (ED25519)
$ ssh-keygen -lf id_rsa.pub
3072 SHA256:bJ4zqQZTFCOTwftUw0tVUWUqeD7xkcMF+Pi13jHxpzs demo@example (RSA)
```

فهرست mode و اندازه‌ی بایتی را نشان می‌دهد. هر دو فایل خصوصی `-rw-------` هستند (فقط من می‌توانم بخوانم) و فایل‌های عمومی `-rw-r--r--`. فایل `.pub` برای ed25519 ‏۹۴ بایت است و برای RSA ‏۵۶۶: ed25519 به‌عنوان خط عمومی حدود شش برابر کوچک‌تر است، یکی از دلیل‌های اینکه امروز انتخاب معمول است. اثر انگشت (fingerprint) hash کلید عمومی است، یک برچسب کوتاه برای آن. `ssh-keygen -lf` اندازه، hash، توضیح و نوع را چاپ می‌کند.

فایل عمومی یک خط است: نوع، داده‌ی base64، توضیح. این کل خط برای کلید ed25519 موقت من است و نشان‌دادنش بی‌خطر است چون عمومی است:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGhhy5BvlctXsN8LdQo5qCL07JV2OHuoLIJw1H9nFyzz demo@example
```

فایل خصوصی با `-----BEGIN OPENSSH PRIVATE KEY-----` شروع می‌شود؛ فقط همین یک خط را چاپ می‌کنم و هرگز چیزی بیشتر از آن را. `ssh-keygen -lvf` یک تصویر «randomart» هم می‌کشد، یک تصویر ASCII کوچک از کلید که مقایسه‌ی دو اثر انگشت را با چشم آسان‌تر می‌کند.

## قاعده‌ی 0600

به معمای ابتدای پست برگردیم. SSH کلید خصوصی‌ای را که کاربران دیگر بتوانند بخوانند رد می‌کند. برای دیدنش یک نسخه از کلید خصوصی برداشتم، mode نسخه را 0644 کردم و بخش عمومی‌اش را خواستم:

```
$ ssh-keygen -y -f bad_key
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@         WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
Permissions 0644 for 'bad_key' are too open.
It is required that your private key files are NOT accessible by others.
This private key will be ignored.
Load key "bad_key": bad permissions
```

SSH اصلاً سعی نمی‌کند از کلید استفاده کند؛ فقط می‌نویسد مجوزها بازتر از حد است و کلید «نادیده گرفته خواهد شد». وقتی این در حین ورود رخ بدهد کلاینت بی‌صدا سراغ روش بعدی می‌رود، و همین است که شما را به درخواست رمز عبور می‌رساند. راه‌حل `chmod 600` است؛ [سیستم فایل و مجوزها](/fa/posts/linux-filesystem-permissions/) را ببینید.

سمت سرور هم بررسی مشابهی دارد. طبق man page فایل sshd_config، گزینه‌ی `StrictModes` (پیش‌فرض `yes`) باعث می‌شود sshd پیش از پذیرفتن ورود، mode و مالکیت فایل‌های کاربر و پوشه‌ی home را بررسی کند. پس پوشه‌ی home یا `authorized_keys` که همه بتوانند در آن بنویسند هم می‌تواند ورود با کلید را بشکند، و روی سرور فقط در لاگ دیده می‌شود.

دو چیز دیگر که امتحان کردم. `ssh-keygen -p -f key` passphrase کلید را عوض می‌کند. افزودن `-m PEM` کلید RSA من را به فایلی تبدیل کرد که با `-----BEGIN RSA PRIVATE KEY-----` شروع می‌شود، قالب قدیمی. روی کلیدهای واقعی passphrase را توصیه می‌کنم.

## authorized_keys

روی سرور، فایل {< term "authorized-keys" "authorized_keys" >} کلیدهای عمومی مجاز به ورود را فهرست می‌کند. هر خط می‌تواند با گزینه‌هایی شروع شود که کار آن کلید را محدود می‌کنند: `restrict` forwarding و pseudo-terminal و چیزهای دیگر را خاموش می‌کند؛ `from="..."` جایی را که کلید از آن می‌تواند استفاده شود محدود می‌کند؛ `command="..."` یک دستور را اجباری می‌کند. کلید بدون گزینه می‌تواند هر چیزی را اجرا و هر چیزی را forward کند.

برای ملموس‌شدن، یک بررسی‌کننده‌ی کوچک با Python نوشتم. بررسی خط‌به‌خط است، نه parser واقعی sshd. روی یک فایل ساختگی اجرایش کردم که کلیدهایش placeholderهای کوتاه‌شده‌اند:

```
# invented example
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEXAMPLE...EXAMPLE ci@example
restrict,from="198.51.100.0/24",command="/usr/bin/true" ssh-ed25519 AAAA...EXAMPLE backup@example
from="203.0.113.5" ssh-rsa AAAAB3NzaC1yc2EAAAADAQABEXAMPLE old@example
nonsense line
```

و این را چاپ کرد:

```
line 2: WARN no options: key can run anything, forward anything
line 3: OK ssh-ed25519
line 4: WARN options without 'restrict'
line 5: FAIL no key type found
```

خط ۲ گزینه ندارد، پس بررسی‌کننده هشدار می‌دهد که این کلید می‌تواند هر چیزی را اجرا و forward کند. خط ۳ با `restrict` شروع می‌شود، پس خوب است. خط ۴ گزینه دارد ولی `restrict` ندارد، پس هنوز چیزهایی به‌طور پیش‌فرض مجازند. خط ۵ اصلاً کلید نیست. (خط ۱ کامنت است و رد می‌شود.)

## known_hosts و TOFU

حالا جهت دیگر. کلاینت کلیدهای *میزبان* سرورها را در {< term "known-hosts" "known_hosts" >} نگه می‌دارد. این‌ها سرورها را شناسایی می‌کنند و با کلید *کاربر* شما فرق دارند. اولین اتصال به یک سرور «اعتماد در اولین استفاده» (TOFU) است: ssh اثر انگشت سرور را نشان می‌دهد و شما می‌پذیرید. از آن به بعد ssh مقایسه می‌کند و تغییر مشکوک است. `ssh-keygen -H` نام میزبان‌ها را در فایل hash می‌کند تا فایل لو ندهد از کدام سرورها استفاده می‌کنید، و `-F` یکی را جستجو می‌کند. این‌جا یک کلید موقت را به‌عنوان host key ساختگی برای `127.0.0.1` به کار بردم:

```
$ ssh-keygen -F 127.0.0.1 -f known_hosts
# Host 127.0.0.1 found: line 1
|1|98zxhnZ1VcQcFbxydmTLPNBypR0=|s9N2l/8OTKzirkt2xrXUBmfZcnE= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBfogGkj1mTYg3MbVhLA0iJ68wBo3k4qTMI1q9jDzWGW
```

خط اول نتیجه می‌گوید میزبان را در خط ۱ پیدا کرده. خط دوم خود ورودی است: `|1|...|...` نام hash‌شده است (salt و hash)، بعد نوع کلید و خود کلید. نام میزبان را از آن نمی‌شود خواند، ولی ssh هنوز می‌تواند تطبیقش دهد.

## ورود واقعی و کلید میزبانِ عوض‌شده

این بخش از اجرای اصلی این پست است (OpenSSH 10.3) که برای این بازنویسی تکرارش نکردم. `sshd` را با کاربر خودم روی `127.0.0.1:22922` راه انداختم، با config در `<tmp>`: `PasswordAuthentication no` و `UsePAM no` و `authorized_keys` موقت من. کلید موقت را پذیرفت:

```
$ ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i id_ed25519 -p 22922 127.0.0.1 echo ok
Warning: Permanently added '[127.0.0.1]:22922' (ED25519) to the list of known hosts.
ok
```

خط هشدار همان مرحله‌ی TOFU است: host key سرور به `known_hosts` اضافه شد. بعد `ok` خروجی دستور راه دور است. بعد `sshd` را با host key دیگری دوباره راه انداختم و دوباره وصل شدم:

```
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
Host key for [127.0.0.1]:22922 has changed and you have requested strict checking.
Host key verification failed.
```

کلاینت ادامه نمی‌دهد، چون کلیدی که یادش مانده دیگر نمی‌خواند. روی سرور واقعی این یعنی نصب دوباره یا حمله، پس پیش از پاک‌کردن خط قدیمی اثر انگشت تازه را از راه دیگری (کنسول، آدمی که به او اعتماد دارید) راستی‌آزمایی کنید. بعد از آزمایش آن `sshd` را کشتم و با `ps` دیدم چیزی نمانده است.

## ssh_config و agent

تایپ گزینه‌های بلند خسته‌کننده می‌شود، پس ssh یک فایل config می‌خواند. `ssh -G alias` پیکربندی حل‌شده را بدون اتصال چاپ می‌کند و راه امنی برای دیدن معنی یک config است. این config ساختگی است که به کار بردم (فقط آدرس‌های مخصوص مستندات):

```
Host jump
    HostName 198.51.100.2
    User deploy
Host web
    HostName 192.0.2.10
    User deploy
    ProxyJump jump
    ControlMaster auto
    ControlPersist 60
    IdentityFile <tmp>/id_ed25519
```

و این خط‌ها را از خروجی `ssh -F cfg -G web` برگزیدم (خروجی کامل بلندتر است):

```
user deploy
hostname 192.0.2.10
port 22
controlmaster auto
identityfile <tmp>/id_ed25519
controlpersist 60
proxyjump jump
```

`web` کاربر `deploy`، آدرس `192.0.2.10`، گزینه‌های multiplexing و jump host را به ارث برده و پورت پیش‌فرض ۲۲ را گرفته. `ProxyJump jump` یعنی «به `web` از راه `jump` برس».

یک {< term "ssh-agent" "ssh-agent" >} کلیدهای رمزگشایی‌شده را در حافظه نگه می‌دارد تا passphrase را یک بار تایپ کنید. در اجرای اصلی یکی خصوصی راه انداختم (`ssh-agent -a <tmp>/agent.sock`)، کلید موقت را اضافه کردم، در `ssh-add -l` دیدمش و کشتمش. برای این بازنویسی به هیچ agentی دست نزدم. agent forwarding (`-A`) به میزبان دور اجازه می‌دهد تا وقتی وصلید از agent شما استفاده کند؛ طبق man page، root آن میزبان می‌تواند سوءاستفاده کند، پس `ProxyJump` را ترجیح بدهید.

## گواهی‌ها

{< term "ssh-certificate" "گواهی SSH" >} یک کلید عمومی است که با یک کلید CA امضا شده. به‌جای کپی کلید هر کاربر روی همه‌ی سرورها، یک بار با CA امضایش می‌کنید و سرورهایی که به CA اعتماد دارند می‌پذیرندش. یک کلید CA موقت ساختم و کلید موقتم را برای کاربر `deploy` با اعتبار یک روز امضا کردم، بعد بررسی‌اش کردم (به خط‌های اصلی کوتاه شده):

```
$ ssh-keygen -s ca -I demo-cert -n deploy -V +1d id_ed25519.pub
$ ssh-keygen -L -f id_ed25519-cert.pub
        Type: ssh-ed25519-cert-v01@openssh.com user certificate
        Key ID: "demo-cert"
        Principals:
                deploy
        Critical Options: (none)
```

`Type` می‌گوید گواهی کاربر ed25519 است، `Key ID` برچسبی است که دادم و `Principals` نام‌های کاربری را فهرست می‌کند که با آن می‌تواند وارد شود. برخلاف [گواهی x509](/fa/posts/sec-tls-x509-certificates/) زنجیره ندارد: یک CA مستقیم امضا می‌کند و سرورها با `TrustedUserCAKeys` در `sshd_config` به آن اعتماد می‌کنند.

## سخت‌کردن سرور Linux

این تنظیم‌ها از man pageهای OpenSSH روی این مک می‌آیند (صفحه‌ی sshd_config را برای این بازنویسی خواندم) و روی Linux اجرا نشدند: `PasswordAuthentication no` (پیش‌فرض yes است)، `PermitRootLogin no` (پیش‌فرض `prohibit-password` است)، `MaxAuthTries` (پیش‌فرض ۶)، `LoginGraceTime` (پیش‌فرض ۱۲۰ ثانیه)، به‌علاوه‌ی `KbdInteractiveAuthentication no` و `AllowUsers` یا `AllowGroups`. ابزارهایی مثل fail2ban برای بستن شکست‌های تکراری هستند؛ امتحانش نکردم. port knocking را توصیه نمی‌کنم: امنیت با پنهان‌کاری است.

## نگه‌داشتن امن کلیدها

- **کلید خصوصی را در چت و تیکت و git نگذارید.** هر چیزی که یکی دارد را مخزن راز حساب کنید.
- **passphrase بگذارید و وقتی کسی می‌رود کلیدها را عوض کنید.** حذف خط یک نفر از `authorized_keys` کاری است که فراموش می‌شود.
- **وقتی `sshd_config` را عوض می‌کنید یک session دوم باز نگه دارید.** اشتباه در config مثل قانون فایروال می‌تواند بیرونتان بیندازد.
- **agent را به میزبان‌هایی که کنترل نمی‌کنید forward نکنید.**
- **کلید عوض‌شده‌ی میزبان را کورکورانه نپذیرید.** هشدار همان فلسفه‌ی `known_hosts` است.

## تمرین

در یک پوشه‌ی موقت با `ssh-keygen -t ed25519 -f ./key` یک کلید ed25519 بسازید. اثر انگشتش را با `ssh-keygen -lf key.pub` ببینید. روی یک ماشین Linux قابل‌دورریختن `sshd` خودتان را روی یک پورت بالا با config جدا راه بیندازید، با کلید وارد شوید، بعد host key را عوض کنید و هشدار را بخوانید.

## قدم بعدی

پست بعدی «کاربر، sudo و capability» است. ورود فقط شروع کار است: آن پست توضیح می‌دهد وقتی ورود کار کرد چه کاری مجاز است و چطور به یک پروسه فقط امتیازهایی بدهیم که لازم دارد.
