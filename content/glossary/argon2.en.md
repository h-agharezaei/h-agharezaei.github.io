+++
title = "argon2"
summary = "A modern password hashing function whose cost is set by time, memory and parallelism; argon2id is the usual variant."
category = "Security"
related = ["password-hashing", "bcrypt", "salt"]
posts = ["sec-password-hashing"]
+++

Because it needs lots of memory per guess, it is harder to attack with GPUs. Hashes are usually stored in the PHC string format with the parameters inside.
