+++
date = '2027-04-22T10:00:00+03:30'
draft = false
title = 'Building an API with FastAPI and Pydantic'
description = 'FastAPI and Pydantic v2: validated parameters and 422 errors, request models, response_model, Depends, sync vs async handlers, lifespan and SIGTERM.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "fastapi", "pydantic", "api", "validation"]
cover = { image = "/images/covers/py-fastapi-pydantic.png", alt = "Building an API with FastAPI and Pydantic", hiddenInSingle = true }
+++

In the [previous post](/posts/py-asyncio/) we learned the event loop; now `async def` handlers run on it. FastAPI builds on {{< term "pydantic" "Pydantic" >}} and reads your {{< term "type-hint" "type hints" >}} ([type hints and mypy](/posts/py-type-hints-mypy/)) to validate input, shape output and generate docs. If you know Zod ([input validation with Zod](/posts/node-validation-zod/)), the model is familiar.

> Python 3.14.0, fastapi 0.162.0, uvicorn 0.54.0, httpx 0.28.1, Pydantic 2.14.1 (so v2), email-validator 2.3.0, in a throwaway `uv` venv. Server on `127.0.0.1`, random port. Demo scripts are local examples. I publish orders and counts, no timings.

## Parameters and 422

```python
@app.get("/items/{item_id}")
def item(item_id: int, limit: int = 10):
    return {"item_id": item_id, "limit": limit}
```

With `TestClient`, `/items/5?limit=3` gives `200 {"item_id": 5, "limit": 3}`. `/items/abc` gives:

```text
422 {"detail": [{"type": "int_parsing", "loc": ["path", "item_id"], "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "abc"}]}
```

Each error has `loc` (where), `msg` and `type`. `?limit=x` gives the same shape with `loc: ["query", "limit"]`. The function never ran.

## Request models and response_model

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

`UserOut` has no `password`. Posting a valid body (name `" Ann "`) returned 201 with `{"name": "Ann", "age": 30, "email": "a@example.com", "addresses": [{"city": "Oslo", "zip": "0150"}]}`: no password, and the nested list survived. A bad body reports all failures at once:

```text
string_too_long   ["body","name"]   ctx: {"max_length": 20}
greater_than      ["body","age"]    ctx: {"gt": 0}
value_error       ["body","email"]  An email address must have an @-sign.
```

A `field_validator` strips the name and rejects blank ones: `"  "` gave `Value error, name must not be blank`.

## Pydantic on its own

```text
P.model_validate({"n": "5"})   -> P(n=5)
.model_dump() / model_dump_json() -> {'n': 5} / {"n":7}
lax  {'n': 'five'} -> int_parsing
lax  {'n': 5.5}    -> int_from_float
strict '5'         -> int_type | Input should be a valid integer
```

By default Pydantic is lax: the string `"5"` becomes 5, but `5.5` is refused. With `ConfigDict(strict=True)` the string is rejected too. Note that HTTP query strings are always text, which is why FastAPI needs lax mode there.

## Depends

```python
def need_token(authorization: Annotated[str | None, Header()] = None):
    if authorization != "Bearer secret":
        raise HTTPException(401, "bad token")
    return "alice"

@app.get("/me")
def me(user: Annotated[str, Depends(need_token)]): ...
```

Without a header: `401 {"detail": "bad token"}`. With `Bearer secret`: `200 {"user": "alice"}`. This is {{< term "dependency-injection" "dependency injection" >}}: tests can replace the dependency, and the check cannot be forgotten inside the handler body. The token here is a toy; real auth is in [sessions or JWT](/posts/sec-sessions-vs-jwt/).

## sync, async and background tasks

I returned the thread name from both kinds of handler on a real uvicorn server:

```text
/sync  -> {"thread":"AnyIO worker thread"}
/async -> {"thread":"MainThread"}
```

A plain `def` runs in a {{< term "thread-pool" "thread pool" >}}; `async def` runs on the event loop itself. A `BackgroundTasks` job runs after the response is sent: the log showed `handler returning` and then `background ran job1`.

## Pitfall: blocking inside async def

Two endpoints sleep 0.3 s with `time.sleep`, one declared `def`, one `async def`. I started the slow request, then sent `/ping` 0.1 s later, and printed the finish order. Three runs each:

```text
/slow-sync       ['ping', 'slow']
/slow-async-bad  ['slow', 'ping']
```

The `async def` version froze the loop, so the ping waited. Same lesson as [asyncio](/posts/py-asyncio/): use `def`, `to_thread` or an async library.

Another pitfall: `def f(x, acc=[])` shares the list between calls (`[1, 2]` on the second call), but a Pydantic model copies its default: a second model's `tags` stayed `[]`.

## OpenAPI

`/openapi.json` is generated from the code: `openapi` was `3.1.0`, the paths included `/items/{item_id}`, and the parameter was `{"name": "item_id", "in": "path", "required": true, "schema": {"type": "integer", "title": "Item Id"}}`. `UserOut`'s schema lists `addresses, age, email, name` and no password. `/docs` serves an interactive UI from it; I cannot show a browser here and did not open it. See [OpenAPI and API contracts](/posts/eng-openapi-contracts/).

## Lifespan and shutdown

A `lifespan` async context manager prints `startup` before `yield` and `shutdown` after. I sent {{< term "sigterm" "SIGTERM" >}} to uvicorn ([processes and signals](/posts/linux-processes-signals/)): the log was `startup`, `shutdown`, and my shell reported exit code 143 (128 + 15, uvicorn re-raises the signal). It is a {{< term "graceful-shutdown" "graceful shutdown" >}}; afterwards `ps` showed no uvicorn process.

## Versus Zod, Go and net/http

Zod validates at runtime from a schema you write separately; Pydantic derives validation from type annotations on a class. Go has no built-in struct validation: you check fields by hand or add a library. With `net/http` ([an API with net/http](/posts/go-http-api-stdlib/)) you decode and validate yourself; FastAPI does both from the signature.

## A few things to watch

- Keep input and output models separate, or a secret field leaks.
- Pick `def` or `async def` deliberately.
- Pin versions; FastAPI and Pydantic move fast.
- Do not copy the toy token check.

## Exercise

Add `PATCH /users/{id}` with an optional-field model, a `Depends` that loads the user or returns 404, and a test with `TestClient`.

## What's next

The next post is "SQLAlchemy and Postgres".
