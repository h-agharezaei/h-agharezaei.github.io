+++
date = '2027-02-28T10:00:00+03:30'
draft = false
title = 'Docker, CI and deploying a Go service'
description = 'Deploy a Go service with Docker: a static binary, a multi-stage distroless Dockerfile, health endpoints and a GitHub Actions workflow with actionlint.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "docker", "ci", "github-actions", "deploy"]
cover = { image = "/images/covers/go-docker-ci-deploy.png", alt = "Docker, CI and deploying a Go service", hiddenInSingle = true, hiddenInList = true }
+++

Profiling was the previous topic. Now the service has to leave my laptop. We take the `orders` service from [the net/http post](/posts/go-http-api-stdlib/), put it in a container, and let CI test and publish it. SIGTERM handling from [graceful shutdown](/posts/go-graceful-shutdown-workers/) matters even more here, because the orchestrator stops a container with exactly that signal.

> **Honest disclaimer.** The Docker daemon is off on this machine and I chose not to start it, so I never ran `docker build`. The Dockerfile and the workflow below were written to be correct, but the image was not built. What I did run for real, on Go 1.26.0 (macOS arm64): the static cross-compiled binary, the health endpoints, `-healthcheck`, SIGTERM and `actionlint` on the workflow. So this post shows no image size and no `docker build` output.

## A static binary

With `CGO_ENABLED=0` the binary has no libc dependency. I cross-compiled it for linux/arm64 four ways:

```
$ CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o plain ./cmd/api
$ ... go build -trimpath ...                    # trim
$ ... go build -ldflags="-s -w" ...             # sw
$ ... go build -trimpath -ldflags="-s -w -X main.version=v1.2.3" ...   # full
plain  9114814 bytes
trim   9110092 bytes
sw     6291618 bytes
full   6291618 bytes
```

`-s -w` drops the symbol table and DWARF debug info and saves about 2.8 MB. `-trimpath` saves almost nothing (4.7 KB); its job is removing local paths from the binary so builds are reproducible. `-X main.version=...` sets a string variable at link time. `file` on the full build says `ELF 64-bit LSB executable, ARM aarch64, statically linked, stripped`.

## Health endpoints and a healthcheck flag

I added three things to `main.go`: `/healthz` (liveness, "the process answers"), `/readyz` (readiness, "send me traffic"), and a `-healthcheck` flag. Readiness is an `atomic.Bool` that is set after the listener starts and cleared the moment SIGTERM arrives:

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

The `-healthcheck` flag makes the binary call its own `/healthz` and exit 0 or 1. A distroless image has no shell and no `curl`, so this is how a Docker `HEALTHCHECK` can work: `HEALTHCHECK CMD ["/api", "-healthcheck"]` (I did not run it in Docker). On Kubernetes you would use HTTP probes instead. I ran the host-built binary with config from the environment:

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

The log shows `"shutting down"` then `"stopped"`. Without a server, `-healthcheck` prints `connection refused` and exits 1. Without `ORDERS_DB_PASSWORD` the service refuses to start with exit code 2, as before.

## The Dockerfile

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

Copying `go.mod` and running `go mod download` first means that layer is reused until dependencies change; editing source code only invalidates the later layers. `.dockerignore` (`.git`, `bin`, logs, docs) keeps the build context small. The final image has no compiler and no shell.

Tradeoffs between final stages, as I understand them:

- **distroless/static `:nonroot`**: according to its docs it contains CA certificates, timezone data and a non-root user. Easiest safe choice. No shell means `docker exec` debugging is harder.
- **scratch**: smallest, but you must copy CA certificates and create the user yourself.
- **alpine/debian**: a shell for debugging, at the cost of more packages to patch.

## CI with GitHub Actions

The workflow has a `test` job (`go vet`, `go test -race ./...`, `go build ./...`) and an `image` job that logs in to GHCR with `GITHUB_TOKEN`, and runs `docker/metadata-action` and `docker/build-push-action` (not on pull requests). Actions are pinned to full release tags (`actions/checkout@v7.0.1`, `docker/build-push-action@v7.4.0`, and so on; pinning to a commit SHA is stricter). The `image` job alone gets `packages: write`. I left `golangci-lint` out; it is a one-step addition. I validated the file:

```
$ go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml
$ echo $?
0
```

Then I broke it by renaming a step reference (`steps.meta` to `steps.metadata`):

```
ci-broken.yml:50:21: property "metadata" is not defined in object type
{meta: {conclusion: string; outcome: string; outputs: {string => string}}} [expression]
```

A typo in `runs-on: ubuntu-lastest` was also caught as an unknown label. `actionlint` checks syntax and expressions; it does not prove the push works. That needs a real run on GitHub.

## Deployment concepts

- **Config from the environment**: the same image runs everywhere; only `ORDERS_*` variables change.
- **Secrets are not in the image**: `ORDERS_DB_PASSWORD` is injected at runtime; anything in a layer can be read by whoever pulls the image.
- **Liveness vs readiness**: liveness failing means restart me; readiness failing means stop sending traffic. Our `/readyz` flips on shutdown.
- **Termination window**: the orchestrator sends SIGTERM and waits (on Kubernetes, `terminationGracePeriodSeconds`) before killing. Our shutdown timeout of 10 seconds must fit inside that window. Check your platform's actual value.
- **Rollback by tag**: deploy immutable tags (`type=sha`), so rollback means deploying the previous tag, not rebuilding.

## A few things to watch

- I did not verify the Dockerfile with a real build, so run `docker build` before trusting it.
- `-healthcheck` probes `127.0.0.1` on the port of `ORDERS_ADDR`; it fails if you bind to a different host.
- `latest` is not a version; use SHA or semver tags.
- `go test -race` needs cgo on the CI runner; that is fine on `ubuntu-latest`, but not inside the `CGO_ENABLED=0` image build.

## What's next

Next: the Go scheduler and garbage collector, to see what happens inside the runtime of the process we just shipped.
