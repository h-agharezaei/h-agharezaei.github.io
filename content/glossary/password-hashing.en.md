+++
title = "Password hashing"
summary = "A deliberately slow, salted one-way function used to store passwords so a database leak does not reveal them."
category = "Security"
related = ["salt", "bcrypt", "argon2"]
posts = ["sec-password-hashing"]
+++

Unlike a fast hash such as SHA-256, a password hash is tuned to cost real time (and memory) per guess. Use bcrypt or argon2id, never a plain fast hash.
