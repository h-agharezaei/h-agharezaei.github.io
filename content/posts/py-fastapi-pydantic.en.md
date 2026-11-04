+++
date = '2027-04-22T10:00:00+03:30'
draft = false
title = 'Building an API with FastAPI and Pydantic'
description = 'FastAPI and Pydantic v2: validated parameters and 422 errors, request models, response_model, Depends, sync vs async handlers, lifespan and SIGTERM.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "fastapi", "pydantic", "api", "validation"]
cover = { image = "/images/covers/py-fastapi-pydantic.png", alt = "Building an API with FastAPI and Pydantic", hiddenInSingle = true }
+++

Suppose you are building an API with one endpoint, `/items/{item_id}`, and the ID must be an integer. Someone sends `/items/abc`. In most frameworks you now write the code that checks the value, builds an error message, picks a status code and decides what the error JSON looks like. Then you do the same for the query string, then for every field of every request body. It is boring code, and it is easy to forget one field.

FastAPI takes a different route. You declare what each input should look like, with ordinary {{< term "type-hint" "type hints" >}} ([Type hints and mypy](/posts/py-type-hints-mypy/)), and the framework checks the request before your function runs. If the check fails, your function is never called and the client gets a clear error that says which input was wrong and why. The same declarations also shape the response and produce the API's documentation. The checking itself is done by {{< term "pydantic" "Pydantic" >}}, a library that turns type annotations on a class into a validator. If you know Zod from [Input validation with Zod](/posts/node-validation-zod/), the idea is the same. The `async def` handlers we will meet run on the event loop from [the previous post](/posts/py-asyncio/).

> I re-ran everything with Python 3.14.0, fastapi 0.162.0, uvicorn 0.54.0, httpx 0.28.1, Pydantic 2.14.1 (so v2) and email-validator 2.3.0, in a throwaway `uv` virtual environment. Servers ran on `127.0.0.1` with a random port. The demo scripts are local examples. I show orders and counts, no timings. (With this httpx version, importing FastAPI's `TestClient` prints a deprecation warning from Starlette; it does not change any result below.)

## Parameters and the 422 response

Here is the smallest example. One path parameter, one query parameter with a default:

```python
@app.get("/items/{item_id}")
def item(item_id: int, limit: int = 10):
    return {"item_id": item_id, "limit": limit}
```

FastAPI reads the signature. `item_id` appears in the path, so it is a path parameter. `limit` is not in the path, so it is a query parameter (`?limit=3`), and because it has a default it is optional. Both are annotated `int`, so FastAPI converts the incoming text to an integer. Everything in a URL is text, so this conversion is necessary and it is the first thing validation does.

I called the app through `TestClient`, which sends requests to the app in the same process without a network. `/items/5?limit=3` gives `200 {"item_id": 5, "limit": 3}`: the strings `"5"` and `"3"` arrived in the function as integers. Now the bad request, `/items/abc`:

```text
422 {"detail": [{"type": "int_parsing", "loc": ["path", "item_id"], "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "abc"}]}
```

422 is the HTTP status code for "I understood the request, but the data in it is not valid". The body is a list, because several things can be wrong at once. Each item has:

- `loc`: where the problem is. Here it is the path, parameter `item_id`.
- `type`: a short machine-readable code, here `int_parsing`.
- `msg`: a sentence for humans.
- `input`: the value that was rejected.

`?limit=x` gives the same shape with `loc: ["query", "limit"]`. In both cases my function never ran. That is the point: the function can assume its arguments are valid.

## Request models and response_model

Query parameters are fine for small inputs. For a JSON body you describe the shape with a class that inherits from `BaseModel`:

```python
class UserIn(BaseModel):
    name: str = Field(max_length=20)
    age: int = Field(gt=0)
    email: EmailStr          # needs email-validator
    password: str
    addresses: list[Address] = []

@app.post("/users", response_model=UserOut, status_code=201)
def create(u: UserIn): return u
```

`Field(...)` adds rules on top of the type: `name` at most 20 characters, `age` greater than zero. `EmailStr` checks that the text looks like a valid email address (this needs the separate `email-validator` package). `addresses` is a list of another model, `Address`, with `city` and `zip`, so Pydantic validates nested data too.

The second part of the idea is `response_model=UserOut`. `UserOut` has the same fields except `password`. The handler returns the whole `UserIn`, password included, and FastAPI filters it through `UserOut` before sending. This is a safety net: a secret field cannot leak just because someone returned the wrong object. I posted a valid body, with the name written as `" Ann "` (spaces around it), and got a 201 with:

```text
{"name": "Ann", "age": 30, "email": "a@example.com", "addresses": [{"city": "Oslo", "zip": "0150"}]}
```

There is no password, the nested list is intact, and the name has no spaces. The spaces were removed by a small validator I wrote, not by Pydantic itself:

```python
@field_validator("name")
@classmethod
def no_blank(cls, v):
    if not v.strip():
        raise ValueError("name must not be blank")
    return v.strip()
```

A `field_validator` runs after the basic checks and may reject the value or return a cleaned one. Sending `"  "` as the name gave `Value error, name must not be blank`.

What happens when several fields are bad at once? I sent a body with a 21-character name, `age: 0` and the email `"nope"`. The response contained all three errors together, so a client can fix everything in one round trip. Here they are, shortened to the useful parts:

```text
string_too_long   ["body","name"]   ctx: {"max_length": 20}
greater_than      ["body","age"]    ctx: {"gt": 0}
value_error       ["body","email"]  value is not a valid email address: An email address must have an @-sign.
```

`ctx` carries the limit that was broken, which is handy for building a friendly message on the client.

## What Pydantic checks and what it converts

So far Pydantic converted `"5"` to `5` without complaint. Is it checking types, or is it fixing them? Both, and it is worth knowing exactly where the line is. I ran Pydantic alone, without FastAPI, on a model with one field `n: int`:

```text
P.model_validate({"n": "5"})   -> P(n=5)
.model_dump() / model_dump_json() -> {'n': 5} / {"n":7}
lax  {'n': 'five'} -> int_parsing
lax  {'n': 5.5}    -> int_from_float
strict '5'         -> int_type | Input should be a valid integer
```

By default Pydantic works in **lax mode**. It converts values when the conversion is safe and obvious: the string `"5"` becomes the integer 5. It refuses when the conversion is not: `"five"` cannot be parsed, and `5.5` is refused with `int_from_float` because turning it into an integer would silently throw away the `.5`. If you want no conversion at all, `ConfigDict(strict=True)` makes the model strict, and then even `"5"` is rejected with `int_type`. The same lax conversion applies to JSON: `P.model_validate_json('{"n": "5"}')` also gave `n=5`.

Lax mode is the right default for HTTP, because query strings and path parameters are always text. If FastAPI were strict there, no integer parameter would ever work. For internal data you control, strict mode is worth considering. The last two lines of the output show the other direction: `model_dump()` turns a model back into a plain dict, and `model_dump_json()` into a JSON string.

## Depends: shared logic as a parameter

Many endpoints need the same preparation, for example checking who is calling. FastAPI lets you write that once as a function and ask for its result as a parameter, with `Depends`:

```python
def need_token(authorization: Annotated[str | None, Header()] = None):
    if authorization != "Bearer secret":
        raise HTTPException(401, "bad token")
    return "alice"

@app.get("/me")
def me(user: Annotated[str, Depends(need_token)]): ...
```

`need_token` reads the `Authorization` header (that is what `Header()` says). If it is wrong, it raises `HTTPException` and the client gets a 401; otherwise it returns the user name, and FastAPI passes it to `me` as `user`. Without a header I got `401 {"detail": "bad token"}`, and with `Bearer secret` I got `200 {"user": "alice"}`.

This is called {{< term "dependency-injection" "dependency injection" >}}: the handler says what it needs and the framework supplies it. It helps in two ways. The check cannot be forgotten inside one handler's body, because it is part of the signature. And tests can replace the dependency with a fake. The token here is a toy, of course; real authentication is in [Sessions or JWT](/posts/sec-sessions-vs-jwt/).

## def, async def and background tasks

You have probably noticed that some handlers are `def` and some `async def`. Does it matter? I made two endpoints that return the name of the thread they run on, and called them on a real uvicorn server (not `TestClient`, because the test client runs async handlers on a thread of its own, which would give a misleading answer):

```text
/sync  -> {"thread":"AnyIO worker thread"}
/async -> {"thread":"MainThread"}
```

A plain `def` handler is run in a {{< term "thread-pool" "thread pool" >}}, so a slow one does not stop the server. An `async def` handler runs directly on the event loop, on the main thread. It comes with a rule that the next section shows.

FastAPI can also run a job after the response has been sent, with `BackgroundTasks`. The demo handler queued a job and printed a line, and the server log showed `handler returning` first and then `background ran job1`. The client already had its answer by then.

## The trap: blocking inside async def

An `async def` handler runs on the event loop, so if it blocks, everything blocks, as we saw in [asyncio in Python](/posts/py-asyncio/). To check it I wrote two endpoints that both call `time.sleep(0.3)`. One is declared `def`, the other `async def`. The client starts a request to the slow endpoint, waits 0.1 seconds, sends `/ping`, and prints which request finished first. Three runs each gave the same result:

```text
/slow-sync       ['ping', 'slow']
/slow-async-bad  ['slow', 'ping']
```

With `def`, the sleep happens in a worker thread, so `ping` is answered while the slow request is still sleeping. With `async def`, the sleep blocks the event loop itself; `ping` has to wait until the slow handler is done. The fix is the same as before: use a plain `def`, move the blocking call into `asyncio.to_thread`, or use an async library.

There is one more trap, related to defaults. In a plain function, `def f(x, acc=[])` creates the list once and shares it between calls: the second call returned `[1, 2]`. Pydantic does not do that. A model field with the default `[]` gets its own copy for each model, and in the demo a second model's `tags` stayed `[]` after I appended to the first one's.

## The generated documentation

Because FastAPI knows every parameter and model, it can describe the whole API. `/openapi.json` is generated from the code. In the demo, the `openapi` field was `3.1.0`, the paths included `/items/{item_id}`, and the description of that parameter was:

```text
{"name": "item_id", "in": "path", "required": true, "schema": {"type": "integer", "title": "Item Id"}}
```

The schema of `UserOut` lists `addresses`, `age`, `email` and `name`, and no password, as it should. FastAPI also serves an interactive page at `/docs` built from the same JSON. I cannot show a browser here and did not open it. For why a machine-readable contract is useful, see [OpenAPI and API contracts](/posts/eng-openapi-contracts/).

## Startup, shutdown and SIGTERM

An API usually needs to do something when it starts (open a connection) and when it stops (close it). FastAPI's `lifespan` is an async context manager for this: code before `yield` runs at startup, code after it at shutdown. The demo only prints `startup` and `shutdown`.

I sent {{< term "sigterm" "SIGTERM" >}} to the running uvicorn process ([Processes and signals](/posts/linux-processes-signals/)). The log was `startup`, then `shutdown`, and my shell reported exit code 143, which is 128 plus 15, the number of SIGTERM. The `shutdown` line proves the code after `yield` ran, so this was a {{< term "graceful-shutdown" "graceful shutdown" >}}. Afterwards `ps` showed no uvicorn process.

## Compared with Zod, Go and net/http

Zod validates at runtime against a schema that you write separately from your types; Pydantic derives validation from the type annotations on a class. Go has no built-in validation of struct fields: you check them by hand or add a library. With `net/http` ([An API with net/http](/posts/go-http-api-stdlib/)) you decode and validate everything yourself, while FastAPI does both from the function signature.

## Before using it for real

- Keep input and output models separate. If one model serves both, a secret field such as `password` will eventually leak into a response.
- Choose `def` or `async def` on purpose. If the handler calls a blocking library, `def` is the safe choice; `async def` needs an async library inside.
- Pin versions. FastAPI and Pydantic change quickly, and error messages or defaults can differ between releases.
- Do not copy the toy token check from this post into real code.

## Exercise

Add `PATCH /users/{id}` with a model whose fields are all optional, a `Depends` that loads the user or returns 404, and a test with `TestClient`.

## What's next

Next is "SQLAlchemy and Postgres", because this API still has no database to store its users in.
