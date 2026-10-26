+++
title = "Subnet"
summary = "A contiguous block of IP addresses sharing one prefix."
category = "Networking"
related = ["cidr", "netmask"]
posts = ["net-addressing-subnets"]
+++

A subnet is a block of addresses that share a prefix, usually one broadcast domain. A larger block can be split into smaller subnets by lengthening the prefix, for example a `/24` into four `/26`.
