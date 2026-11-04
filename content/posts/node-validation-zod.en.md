+++
date = '2027-03-15T10:00:00+03:30'
draft = false
title = 'Input validation with Zod'
description = 'Input validation with Zod in Node.js: parse vs safeParse, real error shapes, coerce, strict, refine, transform and a 400 response at the HTTP boundary.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "zod", "validation", "security", "http"]
cover = { image = "/images/covers/node-validation-zod.png", alt = "Input validation with Zod", hiddenInSingle = true }
+++

Somebody sends your server this JSON to place an order: `{ "id": "nope", "qty": "2", "admin": true }`. The `id` is not a valid id, `qty` is the text `"2"` instead of a number, and `admin` is a field you never asked for. If your code reads `body.qty * price` without looking, it will compute something, and it may even look right: `"2" * 5` is 10 in JavaScript. The `admin` field, if you copy the body into a database row, may quietly do harm. A request body is just text that a stranger wrote.

The fix is not to sprinkle `if` checks everywhere. It is to check the data once, at the edge where it enters your program, and to let everything behind that edge work with data whose shape is known. The edge is a {{< term "trust-boundary" "trust boundary" >}}: a place where data passes from something you do not control (the internet, another service, a message queue) into your own code. Doing this check is called {{< term "schema-validation" "schema validation" >}}: you describe the valid shape once, and a library compares incoming data against it.

The data from [NATS JetStream from Node.js](/posts/node-nats-jetstream/) is still untrusted in this sense, and so is every HTTP body from [An HTTP server with node:http](/posts/node-http-server/). In this post I do the check with Zod, a schema library for JavaScript. It also helps against {{< term "mass-assignment" "mass assignment" >}} (a client setting fields it should not, see [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/)) and the tricks from [Injection and XSS](/posts/sec-injection-xss/).

> I ran everything with Node v20.13.1 and `zod` 4.1.5 (major version 4). The scripts are local examples; the server listens on 127.0.0.1 and a random port. The outputs are real and I show no timings. `typescript` was not installed, so I did not run any `z.infer` type check.

## One schema for an order

A Zod schema reads like a description of the valid data. Here is one for an order:

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

Read it top to bottom: `id` must be a UUID, `email` an email address, `status` is `new` or `paid` and is `new` when missing, `note` is optional text of at most 20 characters, and `items` is a non-empty list in which each item has a `sku` of at least 3 characters and a `qty` that is an integer from 1 to 10. `z.coerce.number()` means "turn text into a number first".

Now `Order.parse(...)` on this input, a good order plus an extra `admin: true` and a quantity written as text:

```js
{ id: '3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c', email: 'a@example.com',
  items: [{ sku: 'abc', qty: '2' }], admin: true }
```

returned:

```text
{
  id: '3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c',
  email: 'a@example.com',
  status: 'new',
  items: [ { sku: 'abc', qty: 2 } ]
}
```

Three things happened. `status` was missing, so it got its default `new`. `qty` `'2'` became the number 2 because of `z.coerce`. And the unknown key `admin` is gone: by default, a Zod object strips keys it does not know. What comes out of `parse` is a new, clean object, not the input.

## parse, safeParse and the issues

What if the data is bad? `parse` throws a `ZodError`. `safeParse` does not throw: it returns `{ success: true, data }` or `{ success: false, error }`. For input from the network I prefer `safeParse`, because a bad body is normal and expected, not an exceptional event.

I gave it a bad payload, `{ id: 'nope', email: 'x', items: [{ sku: 'a', qty: 99 }] }`. `parse` threw a `ZodError` with 4 issues. Each entry of `error.issues` has a `code`, a `path` (where in the input) and a `message`. For example the `qty` problem:

```text
{
 "origin": "number",
 "code": "too_big",
 "maximum": 10,
 "inclusive": true,
 "path": ["items", 0, "qty"],
 "message": "Too big: expected number to be <=10"
}
```

(This is one issue from the real output; I put the `path` array on one line to save space.) The path `["items", 0, "qty"]` says: in `items`, the first element, the field `qty`.

For an API response you usually want the errors grouped by field. This version has `z.flattenError`, which gives `fieldErrors` with a list of messages per top-level key:

```text
{
  formErrors: [],
  fieldErrors: {
    id: [ 'Invalid UUID' ],
    email: [ 'Invalid email address' ],
    items: [
      'Too small: expected string to have >=3 characters',
      'Too big: expected number to be <=10'
    ]
  }
}
```

Notice that the two problems in `items` are merged into one list and the position (which item, which field) is lost. `z.treeifyError` keeps the nesting. For the same error, its `items` part was:

```text
{"errors":[],"items":[{"errors":[],"properties":{"sku":{"errors":["Too small: expected string to have >=3 characters"]},"qty":{"errors":["Too big: expected number to be <=10"]}}}]}
```

Here you can find `items[0].properties.qty`. Choose by what your clients need: flat is simpler, tree is more precise.

## strict, refine, transform

Three more tools. The next lines are from one script, with the output of each as a comment:

```js
const P = z.object({ name: z.string() });
P.strict().safeParse({ name: 'a', extra: 1 }).error.issues;
// [ { code: 'unrecognized_keys', keys: [ 'extra' ], path: [], message: 'Unrecognized key: "extra"' } ]

const Range = z.object({ from: z.number(), to: z.number() })
  .refine(v => v.from < v.to, { message: 'from must be < to', path: ['to'] });
Range.safeParse({ from: 5, to: 1 }).error.issues;
// [ { code: 'custom', path: [ 'to' ], message: 'from must be < to' } ]

const Tag = z.string().trim().toLowerCase().transform(s => s.split(','));
Tag.parse('  A,B ');
// [ 'a', 'b' ]
```

(In the script the `P.parse({ name: 'a', extra: 1 })` call without `strict` returns `{ name: 'a' }`; the extra key is simply stripped.)

- **`.strict()`** makes unknown keys an error instead of silently ignoring them. Use it when an unexpected field means the client is confused.
- **`.refine`** handles a rule that involves several fields, like "from must be less than to". Give it a `path` so the message lands on a field.
- **`.transform`** changes the output, so the parsed value may no longer look like the input. Here the text `'  A,B '` was trimmed, lowercased and split into an array.

## At the HTTP boundary

Now the part that matters for a server. The handler reads the body, parses the JSON, and then runs the schema. If it fails, the answer is 400 with the field errors. If it passes, only the clean value goes on:

```js
const r = Order.safeParse(data);
if (!r.success) return send(res, 400, { error: 'validation', issues: z.flattenError(r.error).fieldErrors });
send(res, 200, { id: r.data.id, status: r.data.status, units: total(r.data) });
```

The business function `total` only ever receives a valid order; it needs no checks of its own. The script starts the server, sends five real requests with `fetch` and prints the status and body of each:

```text
ok      200 {"id":"3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c","status":"new","units":2}
bad     400 {"error":"validation","issues":{"id":["Invalid UUID"],"email":["Invalid email address"],"items":["Too small: expected array to have >=1 items"]}}
type    400 {"error":"validation","issues":{"id":["Invalid input: expected string, received number"],"email":["Invalid input: expected string, received null"],"items":["Invalid input: expected array, received string"]}}
proto   200 {"id":"3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c","status":"new","units":1}
broken  400 {"error":"invalid JSON"}
```

- `ok`: a good order, with `qty` given as text. It answers 200 with 2 units.
- `bad`: wrong id, wrong email, an empty `items` list. Each problem is listed under its field.
- `type`: right fields but wrong types (`id` is a number, `email` is null, `items` is a string). The messages say what was expected and what was received.
- `proto`: a body with a `__proto__` key; the next section explains it. The answer is an ordinary 200.
- `broken`: `{oops` is not JSON at all. `JSON.parse` fails before Zod sees anything, so this case has its own 400 and its own message.

## Keys like `__proto__`

JSON can contain a key named `__proto__`. After `JSON.parse` it is an ordinary own key of the object, not the object's prototype. But if some code later copies keys with plain assignment, `__proto__` can start to matter. This is the idea behind {{< term "prototype-pollution" "prototype pollution" >}}.

I tried it with `{"name":"x","__proto__":{"isAdmin":true},"constructor":{"prototype":{"polluted":1}}}`. Parsing it with `z.object({ name: z.string() })` returned `{ name: 'x' }`. Its prototype was still `Object.prototype`, and `isAdmin` was `undefined`. Parsing the same input with `.loose()`, which keeps unknown keys, was different: the result had `isAdmin: true`, although only on that one object (`({}).isAdmin` stayed `undefined`). A plain `Object.assign({}, evil)` showed the same effect. My reading is that the `__proto__` key was copied by assignment, which sets the prototype of the result; I did not read Zod's source to confirm that.

So in the default mode a key like this is harmless, and that is a good reason to avoid `.loose()` on public input. The same body sent to the server (the `proto` line above) gave a normal 200 and, afterwards, `({}).isAdmin` was still `undefined` in the server's process. This was a local check on this version, not a security proof.

## Compared with Go

In Go, `encoding/json` ignores unknown fields by default unless you call `DisallowUnknownFields` on the decoder. Struct tags such as `json:"qty"` only name fields; they do not check ranges (see [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/)). Zod does the shape and the rules in one place.

## What validation does not cover

- **Validating in many places.** Validate at the boundary once and pass the parsed value on, not the raw body. Otherwise some code path will use the unchecked data.
- **Coercion that is too friendly.** `z.coerce.number()` turned `''` into `0` in my run, while `'abc'` failed. Without `coerce`, `'2'` is rejected ("expected number, received string"). Coerce only where you really accept text.
- **Echoing issues blindly.** Messages can reveal internal field names. Decide what a client may see.
- **Believing it checks everything.** Validation checks shape, not authorization or business rules. A valid order from the wrong user is still wrong.
- **Floating versions.** Pin the major version of Zod; v4 messages differ from older ones.

## Exercise

Add a `PATCH /orders` schema built from `Order.partial()` and make unknown keys a 400. Test that an empty body still fails, using a `refine` that requires at least one field.

## What's next

The next post is "Worker threads and cluster in Node.js". Valid input can still be expensive to handle: one slow synchronous function blocks every request, and that post shows how to move it out of the way.
