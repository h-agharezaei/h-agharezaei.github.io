+++
title = "HSM"
summary = "Hardware security module: a device that generates and uses keys inside itself so they are not meant to be exported."
category = "Security"
related = ["key-custody", "signing-service"]
posts = ["bc-capstone"]
+++

A hardware security module keeps private keys inside tamper-resistant hardware and performs signing there; the application sends data and receives signatures. It protects the key itself, but it still signs whatever an authorized caller asks, so policy checks are still needed around it.
