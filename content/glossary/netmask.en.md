+++
title = "Netmask"
summary = "A 32-bit mask whose leading ones mark the network part of an IPv4 address."
category = "Networking"
related = ["cidr", "subnet"]
posts = ["net-addressing-subnets"]
+++

A netmask is the prefix length written as an address: `/24` is `255.255.255.0`. ANDing an address with the mask gives the network address.
