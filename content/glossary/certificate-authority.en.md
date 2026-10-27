+++
title = "Certificate authority (CA)"
summary = "The party whose signature on a certificate a client chooses to trust."
category = "Networking"
related = ["x509-certificate", "tls"]
posts = ["net-tls-openssl"]
+++

A CA signs certificates. A client trusts a certificate if a chain of signatures leads to a CA in its trust store (or one given with `-CAfile`). A private CA made for a demo or an internal network works the same way, only your machines trust it.
