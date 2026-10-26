# Writing guide for blog posts (read fully before writing)

Blog: Hugo + PaperMod, repo root = this directory. Author persona: "Roham", a senior backend engineer (Go & Node.js) learning and teaching in public. First person, plain, practical. The calendar, series and titles live in [ROADMAP.md](ROADMAP.md) (source of truth). Reference posts to imitate (read both languages of at least one): `content/posts/go-generics.*`, `content/posts/rust-ownership.*`, `content/posts/nats-jetstream-idempotency.*`.

## Deliverables per post
- `content/posts/<slug>.fa.md` (Persian, primary) and `content/posts/<slug>.en.md` (English), same slug, same content.
- Persian must read as natively written: natural phrasing, correct ZWNJ (می‌کنیم، نمی‌شود)، technical terms stay in English and are **bold** on first use. Code, identifiers and output stay LTR English. Keep terminology consistent with earlier posts (check how they translate: ownership, goroutine, interface...).
- New technical terms go to the glossary (see "Glossary" below).
- The cover image line (see "Cover") is added by the orchestrator, not by you.

## Front matter (TOML, exactly these keys, in this order)
```
+++
date = '<date from ROADMAP>T10:00:00+03:30'
draft = false
title = '<title in that language>'
description = '<one sentence, 120-155 characters, main keyword first, only claims the post supports>'
categories = ["<category from ROADMAP>"]
series = ["<series name from ROADMAP>"]
tags = ["lowercase", "english", "tags"]
+++
```
- Single-quoted strings; if the string contains an apostrophe use double quotes. Broken front matter breaks the build for everybody.
- If `title` + ` | Roham` would exceed 60 characters add `seoTitle = '...'` (≤ 52 chars EN, ≤ 50 FA) right after `title`.
- Dates: Hugo does not build future dates (`buildFuture = false`), the daily workflow publishes each post on its day.

## Structure
1. Intro paragraphs with NO heading: why this topic; link the previous post of the same series (fa: `/fa/posts/<slug>/`, en: `/posts/<slug>/`) and 2-4 relevant earlier posts.
2. `##` sections: concept in small runnable examples, then a real run with real output, then `## A few things to watch` / `## چند نکته‌ی مهم` (3-5 bullets), then (fundamentals) `## Exercise` / `## تمرین`, then `## What's next` / `## قدم بعدی` naming the next post of the series by TITLE only (never write a slug in prose).
3. Length: prose under **850 words per language**, counted as `sed '/^```/,/^```/d' file | wc -w` (tables and shown output count). Recount after your FINAL edit.

## Truthfulness rules (the most important part)
- Every code block presented as runnable must have been actually run by you with the real toolchain; paste the REAL output. Compile errors and panics shown must come from a program in your demo directory.
- Allowed claims: (a) verified by a run; (b) a documented fact you are certain of, phrased as "according to the docs" or hedged; (c) nothing else. No invented numbers, versions, benchmarks, links, CVEs. If something was not run, say so in the post ("I did not run X").
- Comparisons between languages: only facts you are certain of or measured, short.
- Timing numbers: run `uptime` first; only publish ns/ms when the 1-minute load average is < 2-3 and label them "measured here". Otherwise show deterministic measures (counts, allocs, bytes) or no numbers.
- Never put local machine workarounds (DYLD_*, GOPROXY tweaks, GONOSUMDB) into posts as advice.
- Only link to the author's own posts and well-known official sites; never invent GitHub URLs.
- Continuity: if the post says "in the previous post we did X", your demo must really build on the previous post's demo/state (read it first). If that demo does not exist yet, do not claim continuity.
- Security posts: defensive only, own code on localhost, no real-world exploit chains or third-party targets.

## Where to put demo code
- Go: `~/Documents/work/golang/blog-series/<slug>/` · Rust: `~/Documents/work/rust/blog-series/<slug>/` · other languages/shell: `~/Documents/work/blog-series/<slug>/` (create dirs as needed). Do NOT modify existing demo repos; do NOT create GitHub repos; do NOT `git commit`/push anything (the orchestrator commits). Describe demos as local examples (no repo link).

## Environment (macOS arm64) — what is and is not available
- Available: Go 1.26, Rust 1.90 (+ cargo, clippy, rustfmt), Node 20.13 (nvm), Python 3.14 (+ `uv`, `venv`), git, curl, dig, nslookup, openssl, nc, lsof, netstat, traceroute, Google Chrome (headless), protoc (+ protoc-gen-go), Postgres 18.3 via embedded binaries, nats-server via the Go embedded module. Network works (Go proxy, crates.io, npm, PyPI).
- NOT available: Docker daemon (OFF and must stay off; never start it), a Linux kernel (Linux-specific things like /proc, systemd, cgroups, epoll, nftables, strace cannot be run: say so explicitly, do not fake output), `sudo` (so no tcpdump captures), Redis, pgbouncer, tshark, nmap.
- Postgres: use the Go module `github.com/fergusstrange/embedded-postgres` (a working launcher is in `~/Documents/work/golang/blog-series/go-postgres-pgx-sqlc`, read only). For non-Go demos start it from a tiny Go launcher (random free port, temp data dir). Stop it when done and verify no stray process (`ps`). Never install system packages with brew.
- NATS: embedded nats-server (see `~/Documents/work/golang/blog-series/go-graceful-shutdown-workers`, mode `server`).
- `protoc` is broken unless `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/Cellar/abseil/20260107.1/lib` is set (local workaround; never mention as advice).
- Go: use a PRIVATE build cache `export GOCACHE=<scratchpad>/gocache-<slug>`; if the default proxy mirror times out use `GOPROXY=https://proxy.golang.org,direct`.
- Parallel agents share the machine: never run a command that can wait for stdin without `</dev/null`; disk is scarce (a few GB free): `df -h /System/Volumes/Data` before big builds, use `CARGO_PROFILE_DEV_DEBUG=0`, and when you are DONE delete your own build artifacts (`target/`, private GOCACHE, `node_modules`, `.venv`, temp binaries, temp hugo output). Any `rm -rf` must use guarded variables: `rm -rf "${DIR:?}/sub"`.
- Verify the build: `cd <repo> && hugo --buildFuture --destination <your own dir under the scratchpad>` must finish with no errors and no `glossary term ... not found` warnings; confirm your page exists at `/posts/<slug>/` and `/fa/posts/<slug>/`; delete the output dir afterwards. If another agent's half-written file breaks the build, do not edit it: wait a minute and retry or build a trimmed copy.

## Glossary (required for every post)
Glossary entries live in `content/glossary/<term-slug>.fa.md` and `.en.md`.
1. List the technical terms your post introduces or leans on. For each, check `ls content/glossary/<term-slug>.en.md`. Reuse existing ones.
2. Create ONLY missing ones (both languages, short): create files exclusively so you never overwrite (`open(path, "x")` in Python). Do NOT edit existing glossary files (other agents run in parallel; the orchestrator will merge the `posts` lists).
3. Front matter of an entry (TOML): `title` (English term, e.g. "MVCC"), `summary` (one line, used as the tooltip), `category`, `related = [slugs of other terms]`, `posts = ["<your post slug>"]`, and for the `.fa.md` also `fa_title`. Body: a short definition (2-4 sentences, optional tiny example). Links to other terms: `/glossary/x/` (en) and `/fa/glossary/x/` (fa). Existing categories: Go, Rust, Messaging, Security; new ones follow the series: Git, Node.js, Databases, Algorithms, Networking, Python, Engineering, Linux, Distributed.
4. In the post, at the FIRST body mention of each term (not in headings, code blocks or links) use the shortcode: `{{< term "slug" "text as written" >}}`. Aim for 4-10 terms per post, only meaningful ones.
5. In your final report list `terms_used: [...]` and `terms_created: [...]` (slugs).

## Cover and commit rules (handled by the orchestrator)
- Every post needs a cover shown in the list: `python3 scripts/generate-covers.py --front-matter` adds `cover = { image = "/images/covers/<slug>[.fa].png", alt = "<title>", hiddenInSingle = true }` (never `hiddenInList`) and `python3 scripts/generate-covers.py` renders the PNGs (Chrome). New series colors/names are in `SER`/`PLANNED` at the top of that script.
- Commits: plain messages, NO `Co-Authored-By: Claude` and no "Generated with Claude Code" trailer (the owner objected twice). Work goes on a branch and is merged by pull request. Before any git command that talks to GitHub run `ssh-add ~/.ssh/id_rsa_second`.

## Final report (under 120 words)
Your two file paths, the demo dir, the exact commands you ran to verify, `terms_used`/`terms_created`, and anything you were unsure about or deliberately left out.
