+++
title = "NTLM"
summary = "A Windows challenge-response authentication protocol; a leaked NTLMv2 hash can be cracked or relayed."
category = "Security"
related = ["cve"]
posts = ["microsoft-365-outage-exchange-online-2026"]
+++

When Windows connects to a network resource, for example a file share over SMB, it can prove the user's identity with NTLM without sending the password. If an attacker tricks the client into connecting to a server they control, they receive the user's NTLMv2 response and can try to crack it offline or relay it to another service. Blocking outbound SMB (TCP 445) and preferring Kerberos reduce the risk.
