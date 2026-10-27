+++
date = '2027-04-19T10:00:00+03:30'
draft = false
title = 'ADRs and documenting decisions'
description = 'ADRs and documenting decisions: four records in a Go repo, a checker run on good and broken sets, superseding instead of editing, and an index.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["adr", "documentation", "architecture", "software-engineering", "go"]
cover = { image = "/images/covers/eng-adr-documentation.png", alt = "ADRs and documenting decisions", hiddenInSingle = true }
+++

The previous post, [Technical debt](/posts/eng-technical-debt/), ended with a register of things we chose to leave alone. A register says what we decided, not why. Six months later someone asks "why do we poll the outbox?" and the answer is in a chat thread nobody can find. An {{< term "adr" "ADR" >}} (architecture decision record) is a short file in the repo that keeps the why. It is reviewed like code ([Effective code review](/posts/eng-code-review/)), and posts like [API design: versioning and pagination](/posts/eng-api-design-versioning-pagination/) are full of decisions worth recording. Opinions are marked **in my opinion**; the checks and git output were run.

> Go 1.26. The orders service and its four ADRs are invented, with a fake author and fixed dates in a local demo repo. The decisions are not recommendations.

## The format

I use the Nygard layout (Title, Status, Context, Decision, Consequences). This is ADR 4, which replaces ADR 2:

```markdown
# 4. Run several relays with SKIP LOCKED

## Status

Accepted

Supersedes [2. Use an outbox in Postgres](0002-use-an-outbox-in-postgres.md)

## Context

ADR 2 chose one polling relay. It stopped publishing during a deploy and events were late. We still want the outbox itself.
```

The set is: 1 record decisions, 2 use an {{< term "outbox-pattern" "outbox" >}} instead of dual writes, 3 use {{< term "jetstream" "JetStream" >}} for events, 4 run several relays. Consumers stay {{< term "idempotency" "idempotent" >}}, as in [the outbox post](/posts/go-outbox-pattern-nats/). A common alternative is MADR, which I put next to it in `docs/adr-madr/`:

```markdown
# Use NATS JetStream for events
* Status: accepted
## Considered Options
* NATS JetStream
* Kafka
## Decision Outcome
Chosen option: "NATS JetStream", because the team already runs NATS.
```

**In my opinion** the difference is small: MADR forces you to list options, Nygard is shorter. Pick one.

## Good Context and Consequences

- Context states forces, not the solution: what hurt, what constraints exist, what we do not know.
- Consequences must include a cost. An ADR whose consequences are all good reads as a sales pitch. ADR 2 admits "single point of failure"; ADR 4 later fixed exactly that.
- Write it in the pull request that implements the decision.

## Statuses and immutability

Statuses I use: proposed, accepted, superseded, deprecated. **In my experience** the rule that keeps ADRs trustworthy is: never rewrite an accepted ADR. You may fix a typo and change the status line, nothing else. A changed mind is a new ADR that says "Supersedes 2", and ADR 2 gets "Superseded by 4". The history stays honest.

## A checker

Rules like these rot unless a machine enforces them, so I wrote a small Go program (stdlib only, about 200 lines). It checks sequential numbering, that the filename slug matches the title, required sections, allowed statuses, and that every `Supersedes` link points to a file marked superseded by this one. On the good set:

```text
$ go run ./cmd/adrcheck check docs/adr
ok
```

On a copy I broke on purpose (a renamed file, an invented status "Approved", a missing ADR 3, a deleted section, and ADR 2 no longer marked superseded):

```text
$ go run ./cmd/adrcheck check testdata/broken
FAIL 0001-record-decisions.md: filename slug should be "record-architecture-decisions"
FAIL 0002-use-an-outbox-in-postgres.md: status "approved" is not one of proposed/accepted/superseded/deprecated
FAIL 0004-run-several-relays-with-skip-locked.md: expected number 0003 (numbering must be sequential)
FAIL 0005-use-nats-jetstream-for-events.md: missing or empty section Consequences
FAIL 0004-run-several-relays-with-skip-locked.md: supersedes 0002-use-an-outbox-in-postgres.md, but that file is not marked 'Superseded by' this one
5 problem(s)
```

The same program has a `links` mode for relative markdown links:

```text
$ go run ./cmd/adrcheck links testdata/badlinks
FAIL testdata/badlinks/README.md: broken link runbook.md
FAIL testdata/badlinks/README.md: broken link adr/0009-nope.md
2 problem(s)
```

It belongs in {{< term "ci" "CI" >}}. I wrote this workflow but did not run it on GitHub, only the two commands locally:

```yaml
name: docs
on:
  pull_request:
    paths: ["docs/**", "cmd/adrcheck/**"]
jobs:
  adr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
      - run: go run ./cmd/adrcheck check docs/adr
      - run: go run ./cmd/adrcheck links docs
```

The tool also generates `docs/adr/README.md` from the files (`adrcheck index docs/adr`), so nobody edits an index by hand:

```text
| # | Title | Status |
|---|---|---|
| 1 | Record architecture decisions | accepted |
| 2 | Use an outbox in Postgres | superseded |
| 3 | Use NATS JetStream for events | accepted |
| 4 | Run several relays with SKIP LOCKED | accepted |
```

## Why in the repo

History follows the file even after a rename:

```text
$ git log --follow --format="%h %ad %s" --date=short -- docs/adr/0002-use-an-outbox-in-postgres.md
5e19d0e 2027-03-15 ADR 4: run several relays; mark ADR 2 superseded
0f3b713 2027-02-22 ADR 2: clearer title, rename file
f45c20c 2027-02-08 Add polling outbox relay (ADR 0002)
```

`git blame` on the code leads to the commit that added the ADR together with the relay:

```text
$ git blame -L 6,6 internal/outbox/relay.go
f45c20ca (Roham 2027-02-08 6) // PollInterval is how often the single relay polls. See docs/adr/0002.
```

A wiki page cannot be in the same commit as the code it explains.

## Which document?

| Document | Answers | Lives | My rule of thumb |
|---|---|---|---|
| {{< term "rfc" "RFC" >}} / design doc | what should we build, with alternatives | before the work | long, discussed, may be thrown away |
| ADR | what did we decide and why | with the code | short, immutable |
| README | what is this, how do I run it | with the code | current state only |
| {{< term "runbook" "Runbook" >}} | what do I do at 3 a.m. | with the service | edited constantly |

This table is my opinion, not a standard.

## When not to write one

Skip it for easily reversible choices (a variable name, a lint rule) and decisions obvious from the code. **In my opinion** the test is: would a new teammate, in a year, plausibly undo this out of ignorance?

## A few things to watch

- An ADR written after the fact tends to justify rather than explain.
- Do not edit old ADRs "to keep them correct". Supersede.
- Statuses only mean something if the checker fails when they lie.
- A checker proves structure, not that the reasoning is good. Reviewers still read.

## Exercise

Write one ADR for a decision your team made last month, in the template above, with one honest negative consequence. Then rename the file and see what a checker would say.

## What's next

The next post is "Feature flags and trunk-based development".
