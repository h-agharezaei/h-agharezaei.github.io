+++
title = "Pepper"
summary = "A secret value kept outside the database and mixed into password hashing, so a stolen database alone is not enough."
category = "Security"
related = ["salt", "password-hashing"]
posts = ["sec-password-hashing"]
+++

Unlike a salt, a pepper is secret and shared by all users. It adds key management work, so it is an extra layer, not a replacement for a slow hash.
