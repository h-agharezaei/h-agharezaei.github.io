+++
title = "Session"
summary = "Server-side state that is looked up by a random id stored in a cookie."
category = "Security"
related = ["jwt", "httponly", "csrf"]
posts = ["sec-sessions-vs-jwt"]
+++

The browser only holds an unguessable id; the server holds who the user is. Deleting the server entry ends the session at once.
