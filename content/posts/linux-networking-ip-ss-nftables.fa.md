+++
date = '2027-05-14T10:00:00+03:30'
draft = false
title = 'شبکه در Linux: ip، ss و nftables'
description = 'شبکه در Linux از روی man pageها: خواندن ip و ss، hookهای nftables و قوانین پیش‌فرض‌بستهٔ سرور، همراه با linter و parser فایل /proc/net/tcp با Go.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "networking", "iproute2", "ss", "nftables", "firewall", "go", "macos"]
cover = { image = "/images/covers/linux-networking-ip-ss-nftables.fa.png", alt = "شبکه در Linux: ip، ss و nftables", hiddenInSingle = true }
+++

این را روی یک مک نوشتم؛ هیچ‌چیز اینجا روی Linux اجرا نشده است. این نهمین پست سری Linux است، بعد از [I/O و epoll](/fa/posts/linux-io-epoll/). حالا سوکت‌ها دست کرنل‌اند؛ چطور آن‌ها را ببینیم و تصمیم بگیریم کدام بسته‌ها به آن‌ها برسد؟ واقعیت‌ها از man pageها و مستندات کرنل است؛ متن Linux‌مانند با عبارت «نمونه‌ی تصویری، ضبط‌نشده» علامت خورده و فقط آدرس‌های مستندات دارد. پیش‌زمینه: [آدرس‌دهی IP و زیرشبکه](/fa/posts/net-addressing-subnets/) و [TCP: دست‌دهی و حالت‌های اتصال](/fa/posts/net-tcp-handshake-states/).

## ip: آدرس، مسیر، همسایه

ابزارهای {{< term "iproute2" "iproute2" >}} همه با یک دستور به نام `ip` کار می‌کنند. man page آن شیءهای `address`، `link`، `route`، `neigh` و `netns` را فهرست می‌کند. جمله‌ای مثل «جایگزین ifconfig» در آن پیدا نکردم؛ پس فقط می‌گویم مستندات فعلی Linux از این ابزارها استفاده می‌کنند.

نمونه‌ی تصویری، ضبط‌نشده:

```
$ ip -br addr
lo     UNKNOWN  127.0.0.1/8
eth0   UP       192.0.2.10/24
$ ip route
default via 192.0.2.1 dev eth0
192.0.2.0/24 dev eth0 proto kernel scope link src 192.0.2.10
$ ip route get 203.0.113.5
203.0.113.5 via 192.0.2.1 dev eth0 src 192.0.2.10
```

مسیریابی دقیق‌ترین پیشوند منطبق را انتخاب می‌کند (طولانی‌ترین تطابق) و `default` پیشوند به طول صفر است که با همه چیز جور می‌شود؛ {{< term "cidr" "CIDR" >}} را در پست آدرس‌دهی ببینید. `ip neigh` جدول همسایه‌ها را نشان می‌دهد: کش IP به MAC برای لینک محلی.

## ss: سوکت‌ها

`ss -tlnp` یعنی TCP (`-t`)، فقط listen (`-l`)، عددی (`-n`)، با پروسه‌ها (`-p`)؛ `-s` آمار خلاصه می‌دهد. man pageی که گرفتم `Recv-Q` و `Send-Q` را توضیح نمی‌دهد. تا جایی که می‌فهمم، برای سوکت listen طول فعلی صف accept و سقف آن را نشان می‌دهند، یعنی {{< term "listen-backlog" "backlog" >}}؛ این قرارداد sock_diag کرنل است و اینجا راستی‌آزمایی نکردم. برای سوکت‌های متصل بایت‌های نخوانده و تأییدنشده‌اند.

نمونه‌ی تصویری، ضبط‌نشده:

```
$ ss -tlnp
State  Recv-Q Send-Q Local Address:Port Peer Address:Port
LISTEN 0      4096   0.0.0.0:22         0.0.0.0:*
LISTEN 0      511    127.0.0.1:8080     0.0.0.0:*
```

انبوهی سوکت در {{< term "time-wait" "TIME-WAIT" >}} برای کلاینت شلوغ عادی است؛ تعداد زیاد CLOSE-WAIT معمولاً یعنی برنامه `close()` را فراموش کرده.

## خواندن واقعی /proc/net/tcp

مستند کرنل برای `/proc/net/tcp` می‌گوید این رابط به نفع tcp_diag منسوخ شده، ولی هنوز نشان می‌دهد `ss` چه می‌خواند. آدرس شبیه `0100007F:1F90` و هگزادسیمال است. نمونه‌ی خود مستند، `010310AC`، همان 172.16.3.1 است؛ پس روی ماشین little-endian بایت‌های IPv4 برعکس می‌آیند. حالت یک عدد هگز از `include/net/tcp_states.h` است: 01 ESTABLISHED، 06 TIME_WAIT، 08 CLOSE_WAIT، 0A LISTEN.

یک برنامه‌ی کوچک Go نوشتم که این را رمزگشایی و حالت‌ها را می‌شمارد. ورودی‌اش یک fixture **ساختگی** در همین قالب است (آدرس‌های مستندات)، نه سوکت‌های این مک. واقعاً اجرا شد و تست‌های واحدش گذشت:

```
$ lx9 tcp testdata/proc_net_tcp.txt
127.0.0.1:8080         0.0.0.0:0              LISTEN
0.0.0.0:22             0.0.0.0:0              LISTEN
192.0.2.10:443         203.0.113.5:50000      ESTABLISHED
...
CLOSE_WAIT   1
ESTABLISHED  2
LISTEN       2
TIME_WAIT    3
```

(ردیف‌های میانی حذف شده.) روی Linux آن را به فایل واقعی می‌دهید؛ من ندادم.

## nftables: جدول، chain، hook

{{< term "nftables" "nftables" >}} با `nft` پیکربندی می‌شود. طبق man page، مجموعه‌قوانین از جدول، chain و rule ساخته می‌شود. base chain با یک اولویت به یک hook از {{< term "netfilter" "netfilter" >}} وصل است (`prerouting`، `input`، `forward`، `output`، `postrouting`)؛ عدد کمتر زودتر اجرا می‌شود. ترافیک ورودی به همین میزبان از `input` می‌گذرد و ترافیک عبوری از `forward`. `policy` یا `accept` است (پیش‌فرض) یا `drop`. حکم `drop` یا `reject` ارزیابی را تمام می‌کند؛ `accept` فقط base chain جاری را تمام می‌کند و chain بعدی هنوز می‌تواند بسته را drop کند. {{< term "connection-tracking" "ردیابی اتصال" >}} به قوانین `ct state` (new، established، related) می‌دهد و NAT هم از همین سازوکار استفاده می‌کند.

مجموعه‌قوانین یک سرور، به‌صورت متن (ورودی linter من؛ بررسی نحوی واقعی `nft -c -f file` است که اجرا نکردم):

```
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;
        iif "lo" accept
        ct state established,related accept
        tcp dport 22 ct state new limit rate 10/minute accept
        tcp dport { 80, 443 } accept
        log prefix "drop: " drop
    }
}
```

## linter، نه parser

linter من در chain ورودی سه چیز را وارسی می‌کند: policy برابر drop، یک accept برای established/related و یک accept برای loopback. فقط regexp روی خطوط است و parser خود nft **نیست**؛ ردنشدنش چیزی درباره‌ی معتبر بودن ثابت نمی‌کند. خروجی واقعی روی فایل درست و روی نسخه‌ای که policy آن accept شده و قاعده‌ی established حذف شده:

```
$ lx9 lint testdata/good.nft
OK: 3 checks passed
$ lx9 lint testdata/bad.nft
FAIL: input chain policy is not drop
FAIL: no 'ct state established,related accept' in input chain
```

برنامه با `GOOS=linux GOARCH=arm64 go vet ./... && go build` هم گذشت؛ روی Linux اجرا نشد.

## namespace و veth

کانتینرها با {{< term "namespace" "namespace" >}} شبکه پشته‌ی شبکه‌ی خودشان را می‌گیرند، [cgroup و namespace](/fa/posts/linux-cgroups-namespaces/) را ببینید. طبق man pageهای ip-netns و ip-link، `ip netns add net0` یکی می‌سازد و `ip link add ... type veth` یک جفت {{< term "veth" "veth" >}} می‌سازد: دو رابط مجازی که مثل کابل به هم وصل‌اند؛ یک سر را با `ip link set ... netns net0` به namespace ببرید. اجرا نشد.

## چند نکته‌ی مهم

- از default drop شروع کنید، ولی کنسول خارج از باند نگه دارید: قانون غلط روی SSH شما را بیرون می‌اندازد.
- اول `iif "lo"` و established/related را اجازه بدهید، وگرنه سرویس‌های محلی و پاسخ‌ها خراب می‌شوند.
- اتصال‌های تازه روی پورت‌های باز را rate-limit کنید.
- پیش از اعمال، با `nft -c -f` نحو را بررسی کنید.
- منبعم man pageها بود؛ نسخه‌ها فرق می‌کنند.

## تمرین

روی یک VM دورریختنی `ss -tlnp` را بزنید، بعد `ss -tan` را وقتی یک `curl` باز است، و با `/proc/net/tcp` مقایسه کنید.

## قدم بعدی

پست بعدی «SSH و کلیدها» است.
