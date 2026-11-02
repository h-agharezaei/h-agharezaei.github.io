+++
title = "Signing service"
summary = "A separate process that holds a key and signs only requests that pass its own policy checks."
category = "Blockchain"
related = ["key-custody", "hot-wallet", "least-privilege"]
posts = ["bc-capstone"]
+++

A signing service keeps the private key out of the application. Callers can ask for a few narrow operations, such as signing a withdrawal, and the service checks each request against its policy (allowed contract, limits, chain id) before signing. It should fail closed and not trust its caller.
