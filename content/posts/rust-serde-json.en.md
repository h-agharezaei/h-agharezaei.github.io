+++
date = '2027-01-15T10:00:00+03:30'
draft = false
title = 'Serde and JSON in Rust'
description = 'Rust serde and JSON: derive Serialize and Deserialize, rename and default attributes, three enum representations, Value and json!, and real error messages.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "serde", "json", "intermediate"]
cover = { image = "/images/covers/rust-serde-json.png", alt = "Serde and JSON in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-async-tokio/) we ran async code with Tokio. Almost every service that does I/O also speaks JSON, so this post covers **serde**, the standard serialization framework in Rust. If you read the Go counterpart, [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/), the shape of this post will look familiar, and I reuse its `User` payload for parity.

> I ran everything with Rust 1.90, `serde` 1.0.229 (feature `derive`) and `serde_json` 1.0.154. Outputs are copied from real runs. Each section is a small program in a local demo project.

## Derive and the basic calls

`serde` defines the traits `Serialize` and `Deserialize`; `serde_json` is the JSON format on top. The derive macros write the implementations for you:

```rust
#[derive(Debug, Serialize, Deserialize)]
struct User {
    name: String,
    age: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    email: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    tags: Vec<String>,
    #[serde(skip)]
    password: String,
}
```

```text
{"name":"Roham","age":30}
```

That is `serde_json::to_string(&u)` with no email and no tags. With both set, `to_string_pretty` gives the indented form (same as Go's `MarshalIndent`), and `from_str` reads it back:

```text
User { name: "Roham", age: 30, email: Some("r@example.com"), tags: ["rust", "backend"], password: "" }
```

`skip` removes `password` in both directions, and on read it is filled from `Default`, so the type needs `Default`. `default` lets `tags` be absent in the input. A missing `Option` field is fine too. For files and streams use `to_writer(File::create(..)?, &u)` and `from_reader(BufReader::new(File::open(..)?))`; both round-tripped in my run. Wrap files in `BufReader`, because `from_reader` does many small reads.

## Renaming, flatten, alias

```rust
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Order {
    order_id: u64,
    #[serde(rename = "customer")]
    customer_name: String,
    #[serde(alias = "qty")]
    quantity: u32,
    #[serde(default)]
    is_gift: bool,
    #[serde(flatten)]
    shipping: Shipping, // struct with city and zip
}
```

```text
{"orderId":7,"customer":"Roham","quantity":2,"isGift":false,"city":"Tehran","zip":"1234"}
```

`rename_all` converts every field name, `rename` overrides one, `alias` accepts an extra name when reading (I fed it `"qty":5`), and `flatten` inlines the inner struct's fields, so `city` and `zip` sit next to `orderId`.

## Enums: three representations

This is where serde surprises people. The same three variants (`Created { id }`, `Paid { id, amount }`, `Cancelled`), three attributes:

```text
default:    {"Created":{"id":1}}   {"Paid":{"id":1,"amount":9.5}}   "Cancelled"
tag="type": {"type":"Created","id":1}   {"type":"Paid","id":1,"amount":9.5}   {"type":"Cancelled"}
untagged:   {"id":1}   {"id":1,"amount":9.5}   null
```

- **Externally tagged** (default) wraps the data in the variant name. Unit variants become plain strings.
- **Internally tagged** (`#[serde(tag = "type")]`) puts the tag inside the object. This is usually what API clients expect for events.
- **Untagged** writes only the data. Reading tries variants in order and takes the first match, so `{"id":2,"amount":3.0}` gave `Paid`, but `{"id":2}` gave `Created`, and `Cancelled` serialized to `null`. Use it only when the shapes cannot be confused.

Errors differ as well:

```text
unknown variant `Refunded`, expected one of `Created`, `Paid`, `Cancelled`
missing field `type`
data did not match any variant of untagged enum Untagged
```

The last message has no useful location (line 0, column 0). That is the price of `untagged`.

## Value and json!

For data without a fixed shape, use `serde_json::Value`. Indexing a missing key returns `Value::Null` instead of panicking, and `json!` builds values inline:

```rust
let mut v: Value = serde_json::from_str(r#"{"id":7,"name":"x","list":[1,2.5]}"#)?;
v["name"] = json!("changed");
v["extra"] = json!({"n": 1, "tags": ["a", "b"]});
```

```text
{"extra":{"n":1,"tags":["a","b"]},"id":7,"list":[1,2.5],"name":"changed","nested":{"a":null},"ok":true}
```

Keys came out sorted, because without the `preserve_order` feature the map is ordered by key. (Go's `map[string]any` also encodes with sorted keys.)

## Numbers

`Value` keeps integers and floats apart. From `[1, 1.0, 18446744073709551615, 9223372036854775808]`: `1` is both `i64` and `u64`, `1.0` is only `f64`, and the two big numbers are `u64` only, with exact digits. In Go, `map[string]any` would make all of them `float64`. Serializing `(i64::MIN, u64::MAX, 1.0, 0.1, 1e21)` gave `[-9223372036854775808,18446744073709551615,1.0,0.1,1e+21]`: a float keeps its `.0`.

Typed targets are strict: `from_str::<i64>("1.0")` fails with `invalid type: floating point `1.0`, expected i64`, while `from_str::<f64>("1")` gives `1.0`.

## Errors

For `struct User { name: String, age: u8 }` I got:

```text
trailing comma at line 1 column 14
EOF while parsing an object at line 1 column 12
key must be a string at line 4 column 3
missing field `age` at line 1 column 12
invalid type: string "thirty", expected u8 at line 1 column 26
invalid value: integer `300`, expected u8 at line 1 column 21
```

The error has `line()`, `column()` and `classify()` (`Syntax`, `Data`, `Eof`, `Io`). Unlike Go, a missing field is an error unless it is an `Option` or has `default`; Go silently leaves the zero value. Unknown fields are ignored by default (also like Go), and `#[serde(deny_unknown_fields)]` turns them into an error: ``unknown field `nickname`, expected `name` or `age` at line 1 column 30``.

## A custom deserializer

Some APIs send an id as `5` in one place and `"5"` in another. `deserialize_with` handles that with a small private untagged enum:

```rust
#[derive(Deserialize)]
#[serde(untagged)]
enum StrOrNum { Num(u64), Str(String) }

fn id_from_str_or_num<'de, D: Deserializer<'de>>(d: D) -> Result<u64, D::Error> {
    match StrOrNum::deserialize(d)? {
        StrOrNum::Num(n) => Ok(n),
        StrOrNum::Str(s) => s.trim().parse().map_err(serde::de::Error::custom),
    }
}
// on the field: #[serde(deserialize_with = "id_from_str_or_num")] id: u64
```

```text
{"id":5} -> Item { id: 5 }
{"id":"6"} -> Item { id: 6 }
{"id":"abc"} -> error: invalid digit found in string at line 1 column 12
{"id":true} -> error: data did not match any variant of untagged enum StrOrNum at line 1 column 11
```

## A few things to watch

- Pick the enum representation on purpose; the default is not what most REST clients expect.
- `skip` needs `Default` on the field type for deserialization.
- Prefer typed structs; use `Value` only for truly dynamic parts.
- Integer overflow is an error, not wrap-around or truncation.
- `untagged` errors are vague, and variant order matters.

## Exercise

1. Add `#[serde(tag = "type")]` to an enum of your own and compare the JSON with the default.
2. Make a struct reject unknown fields and read the error for a typo.
3. Write the same payload with Go struct tags and compare the output of both programs.

## What's next

Next we will build an API with Axum in Rust and use these types for request and response bodies.
