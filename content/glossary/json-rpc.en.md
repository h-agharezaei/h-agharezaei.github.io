+++
title = "JSON-RPC"
summary = "A small remote procedure call protocol: a JSON request with method, params and id, and a JSON response with result or error."
category = "Networking"
related = ["full-node"]
posts = ["bc-toy-node-go", "bc-go-ethereum-client"]
+++

Version 2.0 is transport-agnostic; blockchain nodes usually serve it over HTTP or WebSocket. Example: `{"jsonrpc":"2.0","id":1,"method":"getblockcount","params":[]}`.
