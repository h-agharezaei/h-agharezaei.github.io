+++
title = "TIME_WAIT"
summary = "The state of the side that closed first, kept for a while after the connection ends."
category = "Networking"
related = ["tcp", "three-way-handshake"]
posts = ["net-tcp-handshake-states"]
+++

After the close sequence the side that sent its FIN first stays in TIME_WAIT for about twice the maximum segment lifetime (2*MSL, according to the docs). It lets late packets die out and a lost final ACK be re-sent.
