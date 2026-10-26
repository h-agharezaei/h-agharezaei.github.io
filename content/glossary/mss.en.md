+++
title = "MSS"
summary = "Maximum Segment Size: the most TCP payload bytes per segment."
category = "Networking"
related = ["mtu", "tcp"]
posts = ["net-tcp-ip-model"]
+++

It is roughly the MTU minus the IP and TCP headers (20 + 20 bytes without options), so 1460 on a 1500 MTU. Each side announces its MSS when the connection opens.
