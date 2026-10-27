+++
date = '2027-03-15T10:00:00+03:30'
draft = false
title = 'Input validation with Zod'
description = 'Input validation with Zod in Node.js: parse vs safeParse, real error shapes, coerce, strict, refine, transform and a 400 response at the HTTP boundary.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "zod", "validation", "security", "http"]
cover = { image = "/images/covers/node-validation-zod.png", alt = "Input validation with Zod", hiddenInSingle = true }
+++

In the previous post, [NATS JetStream from Node.js](/posts/node-nats-jetstream/), I said the payload is still untrusted. The same is true of every HTTP body from [An HTTP server with node:http](/posts/node-http-server/). Everything that crosses a {{< term "trust-boundary" "trust boundary" >}} should go through {{< term "schema-validation" "schema validation" >}} once, at the edge; the code behind it then works with data of a known shape. Here I do that with Zod. It also closes the door on [mass assignment](/posts/sec-owasp-top10-in-code/) and similar tricks from [Injection and XSS](/posts/sec-injection-xss/).

> Node v20.13.1, `zod` 4.1.5 (major version 4). Local example scripts on 127.0.0.1, real outputs, no timings. `typescript` was not installed, so I did not run any `z.infer` type check.

## One schema for an order

```js
export const Order = z.object({
  id: z.uuid(),
  email: z.email(),
  status: z.enum(['new', 'paid']).default('new'),
  note: z.string().max(20).optional(),
  items: z.array(z.object({
    sku: z.string().min(3),
    qty: z.coerce.number().int().min(1).max(10),
  })).min(1),
});
```

`parse` of `{ id, email, items: [{ sku: 'abc', qty: '2' }], admin: true }` returned:

```text
{
  id: '3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c',
  email: 'a@example.com',
  status: 'new',
  items: [ { sku: 'abc', qty: 2 } ]
}
```

Three things happened: `status` got its default, `qty` `'2'` became the number 2 through `z.coerce`, and the unknown key `admin` was dropped. By default objects strip unknown keys.

## parse, safeParse and the issues

`parse` throws a `ZodError` (4 issues for my bad payload); `safeParse` returns `{ success, data }` or `{ success: false, error }` without throwing. For input from the network I prefer `safeParse`, since a bad body is normal, not exceptional. With `error.issues` each entry has `code`, `path` and `message`, for example:

```text
{ "code": "too_big", "maximum": 10, "path": ["items", 0, "qty"],
  "message": "Too big: expected number to be <=10" }
```

(I trimmed `origin` and `inclusive`.) This version also has `z.flattenError`, giving `fieldErrors` with one message list per top-level key:

```text
fieldErrors: { id: [ 'Invalid UUID' ], email: [ 'Invalid email address' ],
  items: [ 'Too small: expected string to have >=3 characters',
           'Too big: expected number to be <=10' ] }
```

Note that the two `items` messages are merged, losing the index. `z.treeifyError` keeps the nesting (`items[0].properties.qty`). Choose by what your clients need.

## strict, refine, transform

```text
P.strict() on {name, extra}: code 'unrecognized_keys', keys ['extra'], message 'Unrecognized key: "extra"'
refine from<to on {from:5,to:1}: code 'custom', path ['to'], message 'from must be < to'
z.string().trim().toLowerCase().transform(s => s.split(',')).parse('  A,B ')  ->  [ 'a', 'b' ]
```

Use `.strict()` when an unknown field should be an error, not be silently ignored. `.refine` handles rules that involve several fields; give it a `path` so the message lands on a field. `.transform` changes the output, so the parsed value may no longer equal the input.

## At the HTTP boundary

```js
const r = Order.safeParse(data);
if (!r.success) return send(res, 400, { error: 'validation', issues: z.flattenError(r.error).fieldErrors });
send(res, 200, { id: r.data.id, status: r.data.status, units: total(r.data) });
```

`total` only ever receives a valid order. Real requests against the server:

```text
ok     200 {"id":"3f2b8c1e-...","status":"new","units":2}
bad    400 {"error":"validation","issues":{"id":["Invalid UUID"],"email":["Invalid email address"],"items":["Too small: expected array to have >=1 items"]}}
type   400 {"error":"validation","issues":{"id":["Invalid input: expected string, received number"],"email":["Invalid input: expected string, received null"],"items":["Invalid input: expected array, received string"]}}
broken 400 {"error":"invalid JSON"}
```

Broken JSON is a separate case: `JSON.parse` fails before Zod sees anything, so it gets its own 400.

## Keys like __proto__

`JSON.parse` of `{"name":"x","__proto__":{"isAdmin":true},"constructor":{...}}` gives an object that has `__proto__` as an ordinary own key. Parsing it with `z.object({ name: z.string() })` returned `{ name: 'x' }`, with prototype `Object.prototype` and no `isAdmin`. With `.loose()`, which keeps unknown keys, the result did get `isAdmin: true` (inherited, via the copied `__proto__`), though `({}).isAdmin` stayed `undefined`. So a {{< term "prototype-pollution" "prototype-pollution" >}}-style key is harmless in the default mode, and a good reason to avoid `.loose()` on public input. The same payload sent to the server gave an ordinary 200 with a clean result. This was a local check on this version, not a security proof.

## Compared with Go

In Go, `encoding/json` ignores unknown fields by default unless you call `DisallowUnknownFields` on the decoder, and struct tags such as `json:"qty"` only name fields, they do not check ranges (see [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/)). Zod does shape and rules in one place.

## A few things to watch

- Validate at the boundary once, and pass the parsed value on, not the raw body.
- `z.coerce.number()` turned `''` into `0` in my run and `'abc'` failed; coerce only where you really accept strings.
- Do not echo raw issues blindly if they could reveal internal field names you want hidden.
- Validation checks shape, not authorization or business rules.
- Pin the major version; v4 messages differ from older ones.

## Exercise

Add a `PATCH /orders` schema from `Order.partial()` and make unknown keys a 400. Test that an empty body still fails with a `refine` that requires at least one field.

## What's next

The next post is "Worker threads and cluster in Node.js".
