+++
date = '2027-01-15T10:00:00+03:30'
draft = false
title = 'Serde and JSON in Rust'
description = 'Rust serde and JSON: derive Serialize and Deserialize, rename and default attributes, three enum representations, Value and json!, and real error messages.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "serde", "json", "intermediate"]
cover = { image = "/images/covers/rust-serde-json.png", alt = "Serde and JSON in Rust", hiddenInSingle = true }
+++

A client sends your service this body: `{"name": "Roham", "age": "thirty"}`. Your code expects `age` to be a number. What happens next? In a dynamic language the string might travel quietly through three layers of code and blow up far from where it came in. In Rust you would like the opposite: the JSON is checked at the door, you get either a well-formed `User` or a clear error, and nothing in between.

That is the job of **serde**, the standard serialization library in Rust. *Serializing* means turning a value in memory into text or bytes that can be stored or sent; *deserializing* is the way back. Almost every service speaks JSON, so this is the post where our Rust types meet the outside world. It follows [async/await and Tokio in Rust](/posts/rust-async-tokio/). If you read the Go counterpart, [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/), the shape will look familiar, and I reuse its `User` payload so the two can be compared.

> I ran everything with Rust 1.90, `serde` 1.0.229 (feature `derive`) and `serde_json` 1.0.154. The outputs are copied from real runs of a local demo project with six small programs. I re-ran them all for this version of the post. Compiler warnings about unused fields are left out of the outputs.

## The idea: describe the shape once

Serde splits the work into two parts. The first part is *your data type*: you describe once what a `User` looks like. The second part is *the format*: JSON, in our case, provided by the crate `serde_json`. Serde itself knows nothing about JSON, and `serde_json` knows nothing about your types. The two meet through two {{< term "trait" "traits" >}}, `Serialize` and `Deserialize`.

You almost never write those traits by hand. You put `#[derive(Serialize, Deserialize)]` on your struct, and a *derive macro* writes the implementation for you at compile time, by looking at your fields. Here is the `User` from the demo:

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

`name` and `age` are plain fields. The other three carry `#[serde(...)]` attributes, small instructions to the derive macro. I will explain them in a moment; first the output. `serde_json::to_string(&u)` for a user with no email and no tags gives:

```text
{"name":"Roham","age":30}
```

Three fields are missing. `email` and `tags` are skipped because of `skip_serializing_if` (they are empty), and `password` is skipped always. With email and tags set, `to_string_pretty` produces the indented form (like Go's `MarshalIndent`):

```text
{
  "name": "Roham",
  "age": 30,
  "email": "r@example.com",
  "tags": [
    "rust",
    "backend"
  ]
}
```

`password` is still not there. Now the attributes, one by one:

- `skip_serializing_if = "Option::is_none"` leaves the key out when the value is `None`, instead of writing `"email": null`.
- `default` means: if the key is missing in the input, use the type's default value (here an empty `Vec`). Without it, a missing `tags` would be an error.
- `skip` removes the field in both directions. When reading, `password` is not taken from the input; it is filled with `String::default()`, the empty string. So the field type needs a `Default` implementation.

Reading goes through `from_str`, and the target type tells serde what to expect:

```rust
let back: User = serde_json::from_str(&serde_json::to_string(&u)?)?;
let min: User = serde_json::from_str(r#"{"name":"A","age":1}"#)?;
```

```text
User { name: "Roham", age: 30, email: Some("r@example.com"), tags: ["rust", "backend"], password: "" }
User { name: "A", age: 1, email: None, tags: [], password: "" }
```

The first line is the round trip: what went out came back, except `password: ""`, which was never written. The second line shows a minimal input: `email` is an `Option`, so absent means `None`, and `tags` has `default`, so absent means an empty list.

For files and streams there are `to_writer(File::create(..)?, &u)` and `from_reader(BufReader::new(File::open(..)?))`. The demo writes the user to a temporary file and reads it back; the printed `User` is identical to the one above. Wrap the file in a `BufReader`, because `from_reader` reads in many small pieces.

## When the JSON names do not match your fields

JSON written by other people rarely uses Rust naming. A field might be `orderId` while Rust style says `order_id`, or the API calls it `customer` while your struct says `customer_name`. Attributes handle that without making your Rust ugly:

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
    shipping: Shipping, // a struct with `city` and `zip`
}
```

The demo serializes one order, then reads the string `{"orderId":8,"customer":"X","qty":5,"city":"Rasht","zip":"9"}`:

```text
{"orderId":7,"customer":"Roham","quantity":2,"isGift":false,"city":"Tehran","zip":"1234"}
Order { order_id: 8, customer_name: "X", quantity: 5, is_gift: false, shipping: Shipping { city: "Rasht", zip: "9" } }
```

In the first line, `rename_all` turned every field name into camelCase, `rename` overrode one name (`customer`), and `flatten` moved the fields of `shipping` up into the same object, so `city` and `zip` sit next to `orderId`. In the second line, the input used `qty`: `alias` lets the field also accept that name when reading. `isGift` was absent, and `default` made it `false`.

## Enums: three ways to write the same value

A Rust enum can carry different data in each variant, and JSON has no such thing. So serde has to choose a representation, and the choice becomes part of your API contract. Take three variants: `Created { id }`, `Paid { id, amount }` and a plain `Cancelled`. Here they are with the three available attributes:

```text
default:    {"Created":{"id":1}}   {"Paid":{"id":1,"amount":9.5}}   "Cancelled"
tag="type": {"type":"Created","id":1}   {"type":"Paid","id":1,"amount":9.5}   {"type":"Cancelled"}
untagged:   {"id":1}   {"id":1,"amount":9.5}   null
```

(The demo prints each value on its own line; I put the three of each kind on one line.)

- **Externally tagged** is the default. The data is wrapped in an object whose single key is the variant name. A variant without data becomes a plain string.
- **Internally tagged**, with `#[serde(tag = "type")]`, puts the variant name inside the object as a field. This is usually what API clients expect for events.
- **Untagged** writes only the data and no name at all, so `Cancelled`, which has no data, becomes `null`. To read it back, serde tries the variants in the order they are declared and takes the first that fits.

That last rule has a consequence that is easy to miss. You might expect reading `{"id":2,"amount":3.0}` as the untagged enum to give `Paid`, because the input has an `amount`. The real output is:

```text
Created { id: 2 }
```

`Created` is declared first and it only needs `id`; the extra `amount` is silently ignored, so the first variant already fits. The input `{"id":2}` also gives `Created`. And `Paid` can never be reached from JSON in this enum. Untagged enums work only when the variants cannot be confused with each other, or when the more specific variant comes first. (The internally tagged form has no such problem: `{"type":"Paid","id":2,"amount":3.0}` gives `Paid { id: 2, amount: 3.0 }`.)

The error messages differ between representations too:

```text
unknown variant `Refunded`, expected one of `Created`, `Paid`, `Cancelled`
missing field `type`
data did not match any variant of untagged enum Untagged
```

The first is for the internally tagged enum and a tag value nobody knows; it even lists the valid ones. The second is for the same enum with no `type` key at all. The third is for the untagged enum and the input `{"foo":1}`, and it is the least helpful: it has no useful position (line 0, column 0), because serde has tried every variant and has no single place to blame. That is the price of `untagged`.

## When you do not know the shape: Value and json!

Sometimes the JSON has no fixed shape, or you only need one field of it. For that there is `serde_json::Value`, an enum that can hold any JSON: null, bool, number, string, array or object. Indexing it with a missing key does not panic; it gives `Value::Null`. The `json!` macro builds values inline:

```rust
let mut v: Value = serde_json::from_str(r#"{"id":7,"name":"x","ok":true,"list":[1,2.5],"nested":{"a":null}}"#)?;
println!("missing: {}", v["nope"]);
v["name"] = json!("changed");
v["extra"] = json!({"n": 1, "tags": ["a", "b"]});
println!("{v}");
```

```text
missing: null
{"extra":{"n":1,"tags":["a","b"]},"id":7,"list":[1,2.5],"name":"changed","nested":{"a":null},"ok":true}
```

The missing key printed `null`. The second line is the whole value after the two assignments. Notice that the keys came out in alphabetical order, not in the order I wrote them: the object type behind `Value` is sorted by key, unless you turn on the `preserve_order` feature of `serde_json`. (Go's `map[string]any` is also written with sorted keys.)

`Value` is handy, but every access can fail at run time, so use it only for the genuinely dynamic parts of a payload and give everything else a typed struct.

## Numbers need care

JSON has just one kind of number, but Rust has many. `Value` keeps integers and floats apart. For the input `[1, 1.0, 18446744073709551615, 9223372036854775808]` the demo asks each element what it is:

```text
1: is_i64=true is_u64=true is_f64=false
1.0: is_i64=false is_u64=false is_f64=true
18446744073709551615: is_i64=false is_u64=true is_f64=false
9223372036854775808: is_i64=false is_u64=true is_f64=false
```

`1` is an integer, fits both `i64` and `u64`. `1.0` is a float and only a float. The two huge numbers fit only `u64`, and their digits are exact. In Go, decoding into `map[string]any` would turn all four into `float64`, and the biggest one would lose precision.

Writing floats keeps the distinction: `(i64::MIN, u64::MAX, 1.0, 0.1, 1e21)` is written as `[-9223372036854775808,18446744073709551615,1.0,0.1,1e+21]`, so `1.0` stays `1.0`.

Typed targets are strict. Asking for an `i64` and giving `1.0` fails, while asking for an `f64` and giving `1` works:

```text
Err(Error("invalid type: floating point `1.0`, expected i64", line: 1, column: 3))
Ok(1.0)
Err(Error("invalid value: integer `300`, expected u8", line: 1, column: 3))
Err(Error("invalid value: integer `-1`, expected u8", line: 1, column: 2))
Ok("null")
```

The last three lines say: `300` does not fit in a `u8`, `-1` does not either, and serializing `NaN` (not-a-number) does not fail but writes `null`, because JSON has no way to write it. In short, an integer that is too big is an error, never a silent wrap-around.

## Errors you will actually meet

Now back to the opening question. Here are the eight inputs of the `errors` demo, all read as `struct User { name: String, age: u8 }`:

```text
trailing comma: trailing comma at line 1 column 14  [line=1 col=14 classify=Syntax]
truncated: EOF while parsing an object at line 1 column 12  [line=1 col=12 classify=Eof]
multiline: key must be a string at line 4 column 3  [line=4 col=3 classify=Syntax]
missing field: missing field `age` at line 1 column 12  [line=1 col=12 classify=Data]
wrong type: invalid type: string "thirty", expected u8 at line 1 column 26  [line=1 col=26 classify=Data]
overflow u8: invalid value: integer `300`, expected u8 at line 1 column 21  [line=1 col=21 classify=Data]
negative u8: invalid value: integer `-1`, expected u8 at line 1 column 20  [line=1 col=20 classify=Data]
unknown ok: ok User { name: "x", age: 3 }
```

Our opening payload is the `wrong type` line: the error says what it found (the string `"thirty"`), what it wanted (`u8`) and where (line 1, column 26). Each error also has `line()`, `column()` and `classify()`, which tells you whether the problem is `Syntax` (not valid JSON), `Data` (valid JSON, wrong content), `Eof` (the text ended early) or `Io`. A web handler can use that to answer 400 with a useful message.

Two differences from Go are worth knowing. In Go, a missing field silently stays at its zero value; in serde it is an error unless the field is an `Option` or has `default`. Unknown fields, like `nickname` in the last line, are ignored by default in both. If you would rather reject them, put `#[serde(deny_unknown_fields)]` on the struct, and the same input fails with:

```text
unknown field `nickname`, expected `name` or `age` at line 1 column 30
```

## One more tool: a custom deserializer

Some APIs are inconsistent: an id arrives as `5` in one place and as `"5"` in another. You can handle this with `deserialize_with`, a function that reads the field in your own way. Here it uses a small private untagged enum, so it first tries a number, then a string:

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

(`'de` is a lifetime that ties the deserializer to the input text; you can copy this signature as it is.) The demo feeds it four inputs:

```text
{"id":5} -> Item { id: 5 }
{"id":"6"} -> Item { id: 6 }
{"id":"abc"} -> error: invalid digit found in string at line 1 column 12
{"id":true} -> error: data did not match any variant of untagged enum StrOrNum at line 1 column 11
```

Both `5` and `"6"` give a `u64`. The string `"abc"` fails inside our own `parse()`, and its message is passed on through `Error::custom`. The boolean fits neither variant, so we get the vague untagged error again, but this time with a position.

## Where serde bites

- **Choose the enum representation on purpose.** The default, externally tagged, is not what most REST clients expect; `tag = "type"` usually is.
- **`untagged` is order-dependent and its errors are vague.** As we saw, a more general variant declared first swallows the input of a more specific one.
- **`skip` needs `Default`** on the field's type, because reading must still produce some value.
- **Prefer typed structs.** Use `Value` for the truly dynamic part only; every access on it can fail at run time.
- **A number that does not fit is an error,** not wrap-around or truncation. That is good, but make sure your API integer types match what clients really send.

## Exercise

1. Add `#[serde(tag = "type")]` to an enum of your own and compare the JSON with the default.
2. Reorder the variants of an untagged enum so that the more specific one comes first, and read `{"id":2,"amount":3.0}` again.
3. Make a struct reject unknown fields and read the error for a typo in a key.
4. Write the same payload with Go struct tags and compare the output of both programs.

## What's next

The types we described here are exactly what an HTTP service receives and returns. The next post, *Building an API with Axum in Rust*, turns them into request and response bodies.
