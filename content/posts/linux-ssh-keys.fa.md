+++
date = '2027-05-20T10:00:00+03:30'
draft = false
title = 'SSH و کلیدها'
description = 'SSH و کلیدها در یک پوشه‌ی موقت: ed25519 و RSA، اثرانگشت، قانون 0600، authorized_keys، known_hosts، ssh_config، agent و گواهی‌ها.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "ssh", "openssh", "keys", "security", "sshd", "macos"]
cover = { image = "/images/covers/linux-ssh-keys.fa.png", alt = "SSH و کلیدها", hiddenInSingle = true }
+++

این دهمین پست سری Linux است، بعد از [شبکه در Linux: ip، ss و nftables](/fa/posts/linux-networking-ip-ss-nftables/) که در آن هشدار دادم یک قانون غلط فایروال روی SSH شما را بیرون می‌اندازد. همه‌چیز اینجا روی یک مک با OpenSSH 10.3 اجرا شده (`ssh -V` می‌گوید `OpenSSH_10.3p1, LibreSSL 3.3.6`)، نه روی Linux. فقط در یک پوشه‌ی موقت به نام `<tmp>` کار کردم، با مسیرهای صریح و `-F /dev/null -o IdentityAgent=none`، و هرگز به کلیدهای واقعی‌ام یا هیچ ماشین دوری دست نزدم. جاهایی که Linux ممکن است فرق داشته باشد با عبارت «طبق man page» گفته‌ام. کلید خصوصی یک راز است؛ [مدیریت رازها و کلیدها](/fa/posts/sec-secrets-management/) را ببینید.

## جفت‌کلید

یک {{< term "ssh-key-pair" "جفت‌کلید SSH" >}} یک فایل خصوصی است که نزد شما می‌ماند و یک خط عمومی که به اشتراک می‌گذارید. سه جفت با `ssh-keygen -t ... -N '' -C demo@example` ساختم (بدون passphrase، موقت):

```
$ ls -l id_*    (mode, bytes)
-rw-------  505 id_ecdsa       -rw-r--r--  174 id_ecdsa.pub
-rw-------  399 id_ed25519     -rw-r--r--   94 id_ed25519.pub
-rw-------  2602 id_rsa        -rw-r--r--  566 id_rsa.pub
$ ssh-keygen -lf id_ed25519.pub
256 SHA256:RGPI0NPYYwFmf2tRXHk7GKof9bSBEuj/v7XD9bHqaxc demo@example (ED25519)
```

فایل عمومی یک خط است: نوع، base64 و توضیح (`ssh-ed25519 AAAAC3Nz... demo@example`). فایل خصوصی با `-----BEGIN OPENSSH PRIVATE KEY-----` شروع می‌شود؛ فقط همین خط را چاپ کردم. ed25519 اینجا کوچک‌ترین است و خط عمومی RSA 3072 حدود شش برابر بزرگ‌تر است. اثرانگشت (**fingerprint**) هش کلید عمومی است؛ `ssh-keygen -lvf` تصویری به نام «randomart» هم می‌کشد که برای مقایسه‌ی بصری کلیدهاست.

## قانون 0600

SSH کلیدی را که دیگران بتوانند بخوانند قبول نمی‌کند. یکی را 0644 کردم و بخش عمومی‌اش را خواستم:

```
$ ssh-keygen -y -f id_ed25519
WARNING: UNPROTECTED PRIVATE KEY FILE!
Permissions 0644 for 'id_ed25519' are too open.
This private key will be ignored.
Load key "id_ed25519": bad permissions
```

راه‌حل `chmod 600` است؛ [فایل‌سیستم و سطح دسترسی](/fa/posts/linux-filesystem-permissions/) را ببینید. `ssh-keygen -p -f key` passphrase را عوض می‌کند و با افزودن `-m PEM` کلید RSA من به فایل قدیمی‌تر `-----BEGIN RSA PRIVATE KEY-----` تبدیل شد. برای کلیدهای واقعی passphrase توصیه می‌کنم.

## authorized_keys

روی سرور، فایل {{< term "authorized-keys" "authorized_keys" >}} کلیدهای عمومی مجاز را فهرست می‌کند و هر خط می‌تواند گزینه داشته باشد: `restrict` (forwarding، pty و موارد دیگر را خاموش می‌کند)، `from="..."` و `command="..."`. یک linter کوچک پایتونی نوشتم، فقط بررسی خط‌به‌خط و نه parser خود sshd، و روی فایلی ساختگی اجرایش کردم:

```
line 2: WARN no options: key can run anything, forward anything
line 3: OK ssh-ed25519
line 4: WARN options without 'restrict'
line 5: FAIL no key type found
```

## known_hosts و TOFU

کلاینت کلید *میزبان* سرورها را در {{< term "known-hosts" "known_hosts" >}} نگه می‌دارد؛ این کلیدها سرور را شناسایی می‌کنند و با کلید *کاربر* فرق دارند. اولین اتصال «اعتماد در اولین استفاده» (TOFU) است: اثرانگشت را می‌پذیرید و تغییر بعدی مشکوک است. `ssh-keygen -H` نام میزبان‌ها را هش می‌کند و `-F` جست‌وجو می‌کند:

```
$ ssh-keygen -F 127.0.0.1 -f known_hosts
# Host 127.0.0.1 found: line 1
|1|ONhPF46cjlIWMhhj+xun8mOwJlQ=|muhnCYY1... ssh-ed25519 ...
```

## ورود واقعی و تغییر کلید میزبان

`sshd` را با کاربر خودم روی `127.0.0.1:22922` بالا آوردم، با پیکربندی در `<tmp>` (`PasswordAuthentication no`، `UsePAM no` و authorized_keys خودم). کلید موقت را پذیرفت:

```
$ ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i id_ed25519 -p 22922 127.0.0.1 echo ok
Warning: Permanently added '[127.0.0.1]:22922' (ED25519) to the list of known hosts.
ok
```

بعد با یک کلید میزبان دیگر دوباره راهش انداختم و وصل شدم:

```
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
Host key for [127.0.0.1]:22922 has changed and you have requested strict checking.
Host key verification failed.
```

روی سرور واقعی یعنی نصب مجدد یا حمله: پیش از حذف خط قدیمی از راهی دیگر بررسی کنید. بعد sshd را کشتم و با `ps` دیدم چیزی نمانده است.

## ssh_config و agent

`ssh -G alias` پیکربندی نهایی را بدون اتصال چاپ می‌کند. با پیکربندی‌ای با آدرس‌های ساختگی (`Host web`، `ProxyJump jump`، `ControlMaster auto`):

```
user deploy
hostname 192.0.2.10
port 22
controlmaster auto
identityfile <tmp>/id_ed25519
controlpersist 60
proxyjump jump
```

یک {{< term "ssh-agent" "ssh-agent" >}} کلیدهای باز‌شده را در حافظه نگه می‌دارد. یک agent خصوصی (`ssh-agent -a <tmp>/agent.sock`) بالا آوردم، کلید موقت را اضافه کردم، در `ssh-add -l` دیدم و کشتمش. Agent forwarding (`-A`) تا وقتی وصل هستید به میزبان دور اجازه‌ی استفاده از agent شما را می‌دهد؛ طبق man page، root آنجا می‌تواند سوءاستفاده کند، پس `ProxyJump` را ترجیح بدهید.

## گواهی‌ها

یک {{< term "ssh-certificate" "گواهی SSH" >}} کلید عمومی‌ای است که کلید CA امضایش کرده (`ssh-keygen -s ca -I demo-cert -n deploy -V +1d key.pub`). `ssh-keygen -L` نوع `ssh-ed25519-cert-v01@openssh.com`، شناسه، principal به نام `deploy` و اعتبار را نشان داد. برخلاف [گواهی x509](/fa/posts/sec-tls-x509-certificates/) زنجیره ندارد: یک CA مستقیم امضا می‌کند و سرور با `TrustedUserCAKeys` به آن اعتماد می‌کند.

## سخت‌سازی سرور Linux

از man page OpenSSH روی مک، اجرا‌نشده روی Linux: `PasswordAuthentication no` (پیش‌فرض yes)، `PermitRootLogin no` (پیش‌فرض `prohibit-password`)، `MaxAuthTries` (پیش‌فرض 6)، `LoginGraceTime` (پیش‌فرض 120 ثانیه)، به‌علاوه‌ی `KbdInteractiveAuthentication no` و `AllowUsers`/`AllowGroups`. fail2ban برای بستن تلاش‌های ناموفق تکراری وجود دارد؛ امتحانش نکردم. port knocking را توصیه نمی‌کنم، پنهان‌کاری است.

## چند نکته‌ی مهم

- کلید خصوصی را هرگز در چت، تیکت یا git نگذارید.
- passphrase بگذارید و کلید کسانی را که می‌روند بچرخانید.
- هنگام تغییر `sshd_config` یک نشست دوم باز نگه دارید.
- agent را به میزبانی که کنترلش ندارید forward نکنید.
- کلید میزبان تغییرکرده را کورکورانه نپذیرید.

## تمرین

در یک پوشه‌ی موقت یک کلید ed25519 بسازید، sshd خودتان را روی پورت بالا اجرا کنید، وارد شوید، بعد کلید میزبان را عوض کنید و هشدار را بخوانید.

## قدم بعدی

پست بعدی «کاربر، sudo و capability» است.
