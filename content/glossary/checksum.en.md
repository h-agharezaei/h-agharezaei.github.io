+++
title = "Checksum"
summary = "A small number computed from data to detect accidental corruption."
category = "Networking"
related = ["tcp"]
posts = ["net-tcp-ip-model"]
+++

The IPv4 header checksum is the one's complement of the one's complement sum of the header's 16-bit words. Recomputing the sum over the whole header, checksum included, gives 0xFFFF when it is intact. It detects accidents, not attackers.
