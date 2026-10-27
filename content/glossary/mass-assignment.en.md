+++
title = "Mass assignment"
summary = "A bug where the server copies every field of a client request into an internal object, so the client can set fields it should never control (price, status, role)."
category = "Security"
related = ["stride"]
posts = ["sec-threat-modeling-stride", "sec-authorization-rbac-idor"]
+++

The fix is an allow-list input type with only the fields the client may send, and the server computing or defaulting the rest.
