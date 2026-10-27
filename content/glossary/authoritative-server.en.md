+++
title = "Authoritative server"
summary = "A DNS server that holds the real records of a zone and answers with the AA flag."
category = "Networking"
related = ["recursive-resolver", "dns"]
posts = ["net-dns-in-practice"]
+++

An authoritative server is the source of truth for a zone. It does not search elsewhere: it answers from its own data or says the name does not exist, and sets the AA (authoritative answer) flag.
