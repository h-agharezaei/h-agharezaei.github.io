+++
title = "Byte order mark"
summary = "Invisible bytes at the start of a text file; in UTF-8 they are EF BB BF and mark the file as UTF-8."
category = "Python"
related = []
posts = ["py-data-csv-sqlite"]
+++

A BOM is a few bytes at the start of a file. UTF-8 does not need one, but Excel adds or expects it to detect the encoding. If you read such a file as plain `utf-8`, the BOM shows up as the character `\ufeff` glued to the first column name; `utf-8-sig` removes it.
