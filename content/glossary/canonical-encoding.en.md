+++
title = "Canonical encoding"
summary = "A serialization rule that gives exactly one byte sequence for each value, so everyone hashes the same bytes."
category = "Blockchain"
related = ["block-header", "sha-256"]
posts = ["bc-hashes-blocks-chain"]
+++

Default JSON output is not canonical: key order, whitespace, escaping and number formats can differ between libraries. Fixed-width fields in a fixed order, or length prefixes for variable fields, avoid that.
