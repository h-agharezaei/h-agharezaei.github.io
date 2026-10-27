+++
title = "bcrypt"
summary = "A password hashing function with a cost parameter and a built-in salt; it only uses the first 72 bytes of the password."
category = "Security"
related = ["password-hashing", "argon2", "salt"]
posts = ["sec-password-hashing"]
+++

The output looks like `$2a$10$...`: version, cost (a power of two of rounds) and salt plus hash in one string.
