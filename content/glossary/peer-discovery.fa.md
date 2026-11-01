+++
title = "Peer discovery"
summary = "روشی که نود با آن آدرس نودهای دیگر را برای اتصال در شبکه‌ی P2P پیدا می‌کند."
category = "Blockchain"
fa_title = "peer discovery"
related = ["peer-to-peer", "gossip-protocol"]
posts = ["bc-p2p-gossip"]
+++

نودهای بیت‌کوین از DNS seed شروع می‌کنند و بعد آدرس‌ها را از peerها یاد می‌گیرند؛ کلاینت‌های اتریوم یک پروتکل discovery شبیه Kademlia روی UDP دارند. اگر مهاجم همه‌ی peerهای یک نود را در دست بگیرد (حمله‌ی eclipse)، نود فقط دید مهاجم را می‌بیند.
