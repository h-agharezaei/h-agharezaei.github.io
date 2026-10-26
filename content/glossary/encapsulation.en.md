+++
title = "Encapsulation"
summary = "Wrapping the data of one layer inside the header of the layer below."
category = "Networking"
related = ["tcp-ip-model", "mtu"]
posts = ["net-tcp-ip-model"]
+++

An HTTP request becomes the payload of a TCP segment, which becomes the payload of an IP packet, which becomes the payload of a link-layer frame. The receiver removes the headers in reverse order.
