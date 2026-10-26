+++
title = "TCP/IP model"
summary = "The 4-layer model of the internet: link, internet, transport, application."
category = "Networking"
related = ["encapsulation", "tcp"]
posts = ["net-tcp-ip-model"]
+++

Each layer talks to the same layer on the other side and uses the layer below as a service: link (one hop on one network), internet (IP, hop-by-hop routing), transport (TCP/UDP, ports) and application (HTTP, DNS, gRPC). The 7-layer OSI model is a finer teaching split of the same idea.
