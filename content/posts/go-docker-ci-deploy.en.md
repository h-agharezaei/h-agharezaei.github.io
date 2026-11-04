+++
date = '2027-02-28T10:00:00+03:30'
draft = false
title = 'Docker, CI and deploying a Go service'
description = 'Deploy a Go service with Docker: a static binary, a multi-stage distroless Dockerfile, health endpoints and a GitHub Actions workflow with actionlint.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "docker", "ci", "github-actions", "deploy"]
cover = { image = "/images/covers/go-docker-ci-deploy.png", alt = "Docker, CI and deploying a Go service", hiddenInSingle = true }
+++

The service works on my laptop. That sentence is where most deployment stories begin. To run it anywhere else, someone has to answer three questions. How do we package it so that it runs the same on every machine? How do we know that every change still builds and passes its tests before it gets there? And what happens at the moment the platform wants to stop the old version and start the new one?

This post answers them for the `orders` service from [the net/http post](/posts/go-http-api-stdlib/). We build a small, static binary; put it into a {{< term "container" "container" >}} image with a Dockerfile; let {{< term "ci" "CI" >}} (continuous integration: a server that runs the checks on every push) test and publish the image; and give the service two health endpoints. The last question matters most, because a platform stops a container by sending it {{< term "sigterm" "SIGTERM" >}}, so the signal handling from [graceful shutdown](/posts/go-graceful-shutdown-workers/) becomes important once the service leaves my laptop. It comes right after [profiling with pprof](/posts/go-profiling-pprof/): we now know the service is not wasting its time, so we ship it.

> **Honest disclaimer.** The Docker daemon is off on this machine and I chose not to start it, so I never ran `docker build` here. The Dockerfile and the workflow below were written to be correct, but **the image was not built**, and I show no image size and no `docker build` output. What I did run for real, with Go 1.27 on macOS (arm64): the static cross-compiled binary, the health endpoints, the `-healthcheck` flag, SIGTERM, and `actionlint` on the workflow. The demo's `go.mod` says `go 1.26`, so that is the Go version the Dockerfile uses.

## A static binary

Why start with the binary? Because a Go program can be compiled into a single file with no outside dependencies, and that makes the image tiny and simple. By default a program that uses parts of the standard library such as DNS lookups may link to the system C library (libc). With `CGO_ENABLED=0` Go does not use C at all, and the result is a **static binary**: it needs nothing from the system it runs on, not even a libc.

I cross-compiled the service for Linux on arm64 (`GOOS=linux GOARCH=arm64`; the machine is a Mac, and the container will run Linux) in four ways, to see what each flag does:

```
$ CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o plain ./cmd/api
$ ... go build -trimpath ...                    # trim
$ ... go build -ldflags="-s -w" ...             # sw
$ ... go build -trimpath -ldflags="-s -w -X main.version=v1.2.3" ...   # full
plain  10103228 bytes
trim   10098362 bytes
sw      6881440 bytes
full    6881440 bytes
```

- `-s -w` removes the symbol table and the DWARF debug information, which saves about 3.2 MB here. The cost is that a debugger or a stack trace tool has less to work with.
- `-trimpath` saves almost nothing (4.9 KB). Its real job is removing local file paths from the binary, so builds on different machines produce the same result.
- `-X main.version=v1.2.3` sets a string variable at link time. The `full` build is the same size as `sw` because a short string costs nothing. I checked that the host build prints `v1.2.3` with `-version`.

`file` on the full build says `ELF 64-bit LSB executable, ARM aarch64, statically linked, stripped`. The exact sizes depend on the Go version: the original run with Go 1.26 measured 9,114,814 bytes for `plain` and 6,291,618 for the stripped builds.

## Health endpoints and a healthcheck flag

When a platform runs your service, it has to ask the service about its state. There are two different questions, and mixing them up is a classic mistake:

- **Liveness** ("is the process alive?"). If this fails, the platform restarts the process.
- **Readiness** ("should I send you traffic right now?"). If this fails, the platform keeps the process but stops sending requests to it.

I added `/healthz` for liveness, `/readyz` for readiness, and a `-healthcheck` flag to `main.go`. Readiness is an `atomic.Bool`. It becomes true after the listener starts and is cleared the moment SIGTERM arrives:

```go
root.HandleFunc("GET /readyz", func(w http.ResponseWriter, _ *http.Request) {
	if !ready.Load() {
		http.Error(w, "not ready", http.StatusServiceUnavailable)
		return
	}
	w.Write([]byte("ready\n"))
})
// ... after SIGTERM:
ready.Store(false) // fail readiness first, then srv.Shutdown
```

The `-healthcheck` flag makes the binary call its own `/healthz` and exit with 0 or 1. Why have it? The final image will be "distroless", which has no shell and no `curl`, so a normal health-check command has nothing to run. With this flag, a Docker `HEALTHCHECK CMD ["/api", "-healthcheck"]` can work using only the binary. (I did not run it in Docker. On Kubernetes you would use HTTP probes on `/healthz` and `/readyz` instead.)

Here is the host-built binary running with its configuration read from the environment. I started it, called the two endpoints, ran the health check, and then sent SIGTERM:

```
$ ORDERS_ADDR=:18431 ORDERS_DB_PASSWORD=s3cret ORDERS_LOG_FORMAT=json ./host &
$ curl -si localhost:18431/healthz | sed -n '1p;$p'
HTTP/1.1 200 OK
ok
$ curl -si localhost:18431/readyz | sed -n '1p;$p'
HTTP/1.1 200 OK
ready
$ ./host -healthcheck; echo $?
0
$ kill -TERM $PID; wait $PID; echo "exit=$?"
exit=0
```

(The port in my run was a different free port; I show `18431`. `sed -n '1p;$p'` prints only the status line and the last line of each response.) Both endpoints answer 200, the health check exits 0, and SIGTERM leads to a clean exit with code 0. The JSON log has the lines `"shutting down"` and then `"stopped"`, which is the graceful path.

Two failure cases are worth knowing. Without a server listening, `-healthcheck` prints `connection refused` and exits 1. Without `ORDERS_DB_PASSWORD`, the service refuses to start and exits with code 2, as in earlier posts.

## The Dockerfile

Now the image. A Docker **image** is a frozen package of files plus the command to run; a **container** is a running instance of an image. An image is built in **layers**, one per instruction, and Docker caches each layer and reuses it if nothing above it changed. The Dockerfile below uses two stages (a **multi-stage build**): the first stage has the whole Go toolchain and compiles the binary, and the second stage is a tiny image that receives only the binary.

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.26 AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
ARG TARGETOS
ARG TARGETARCH
ARG VERSION=dev
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -trimpath -ldflags="-s -w -X main.version=${VERSION}" \
    -o /out/api ./cmd/api

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/api /api
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/api"]
```

Reading it from the top:

- The build stage runs on the builder's own platform (`$BUILDPLATFORM`) and cross-compiles for the target (`GOOS`/`GOARCH` come from `TARGETOS` and `TARGETARCH`). That way building an arm64 image on an amd64 machine does not need emulation.
- We copy `go.mod` first and run `go mod download`. That layer is reused until the dependencies change; editing source code only invalidates the later layers. This is the single most useful trick for fast builds.
- `ARG VERSION` goes into the binary through `-X main.version`, so a running service can tell you which build it is.
- The final stage has no compiler and no shell. `USER nonroot:nonroot` makes the process run as a normal user, not as root.
- A `.dockerignore` file (`.git`, `.github`, `bin`, logs, markdown files and the Dockerfile itself) keeps the build context small.

There are three common choices for the final stage, as I understand them:

- **distroless/static `:nonroot`**: according to its documentation it contains CA certificates, timezone data and a non-root user. It is the easiest safe choice. Having no shell means `docker exec` debugging is harder.
- **scratch**: the smallest possible, an empty image. You must copy the CA certificates in and create the user yourself.
- **alpine or debian**: has a shell for debugging, at the cost of more packages that you have to keep patched.

## CI with GitHub Actions

CI means that on every push a machine checks out the code, builds it and runs the tests. In GitHub Actions the file is a **workflow** in `.github/workflows/`. It has **jobs**, each job runs on a **runner** (a fresh machine; `ubuntu-latest` here), and each job has **steps**.

Ours has two jobs:

- `test`: runs `go vet`, `go test -race ./...` and `go build ./...`.
- `image`: runs only after `test` passes and not on pull requests. It logs in to GHCR (GitHub's container registry) with the built-in `GITHUB_TOKEN`, then runs `docker/metadata-action` to compute image tags and `docker/build-push-action` to build and push.

Some details I care about:

- Actions are pinned to full release tags (`actions/checkout@v7.0.1`, `docker/build-push-action@v7.4.0`, and so on). Pinning to a commit SHA is stricter, because a tag can be moved.
- The workflow's default permission is `contents: read`. Only the `image` job additionally gets `packages: write`, so the test job runs with read-only access to the repository and cannot publish anything.
- I left `golangci-lint` out. It is a one-step addition.

I validated the workflow file with `actionlint`, a linter for GitHub Actions files (version 1.7.12):

```
$ actionlint .github/workflows/ci.yml
$ echo $?
0
```

Then I broke a copy on purpose, with two mistakes: `runs-on: ubuntu-lastest` (a typo) and a step reference renamed from `steps.meta` to `steps.metadata`. `actionlint` caught both:

```
broken/ci-broken.yml:14:14: label "ubuntu-lastest" is unknown. available labels are ...
broken/ci-broken.yml:50:21: property "metadata" is not defined in object type
{meta: {conclusion: string; outcome: string; outputs: {string => string}}} [expression]
```

(The first line lists many valid labels in the real output; I cut that list. The typo is reported for both jobs, at lines 14 and 27.) Keep in mind what this proves: `actionlint` checks syntax and expressions. It does not prove that the push to the registry works. That needs a real run on GitHub, which I did not do.

## Deployment concepts

- **Config from the environment.** The same image runs everywhere; only the `ORDERS_*` variables change between environments.
- **Secrets are not in the image.** `ORDERS_DB_PASSWORD` is injected when the container starts. Anything written into an image layer can be read by whoever pulls the image.
- **Liveness and readiness are different.** Liveness failing means "restart me". Readiness failing means "stop sending me traffic". Our `/readyz` flips to failing as soon as shutdown begins.
- **The termination window.** The platform sends SIGTERM and then waits for a limited time before it kills the process (on Kubernetes this is `terminationGracePeriodSeconds`). Our shutdown timeout of 10 seconds must fit inside that window. Check your platform's actual value.
- **Rollback by tag.** Deploy immutable tags (`type=sha` in the metadata action, which according to its docs makes a tag from the commit SHA), so a rollback means deploying the previous tag, not rebuilding.

## Container and CI traps

- **The Dockerfile was not built.** I did not verify it with a real build, so run `docker build` before you trust it.
- **`-healthcheck` only probes `127.0.0.1`.** It uses the port from `ORDERS_ADDR`. If you bind the server to a different host address, the check fails.
- **`latest` is not a version.** It points to whatever was pushed last, so you cannot say what is running. Use SHA or semver tags.
- **`go test -race` needs cgo.** The race detector needs a C toolchain, which `ubuntu-latest` has. It does not work inside the `CGO_ENABLED=0` image build, so tests belong in the `test` job, not in the Dockerfile.
- **Readiness flipping is not the whole story.** Our service marks itself not ready and immediately starts shutting down. Whether the platform has already stopped sending traffic by then depends on the platform; on some, a short sleep between the two steps is common. I did not test this.

## What's next

The next post is "The Go scheduler and garbage collector". We have shipped the service; now we look inside the Go runtime that it runs on, to see why goroutines are cheap and what the garbage collector does while requests are being served.
