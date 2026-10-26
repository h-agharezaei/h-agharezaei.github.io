+++
title = "SHA-1"
summary = "Hash function Git uses by default to name objects (40 hex characters)."
category = "Git"
related = ["git-object"]
posts = ["git-how-git-thinks"]
+++

Git runs the content (with a type and size header) through SHA-1 and uses the digest as the object id. Newer repositories can use SHA-256 instead, with 64 hex characters.
