+++
title = "Deadline"
summary = "An absolute point in time after which a network read or write fails with a timeout."
category = "Networking"
related = ["socket", "context"]
posts = ["net-sockets-tcp-from-scratch", "net-udp-sockets"]
+++

In Go, `SetReadDeadline` sets a time (not a duration) on a connection; a Read that is still blocked then returns an `i/o timeout` error. You must set it again before each read if you want an idle timeout. See [context](/glossary/context/) for cancellation in general.
