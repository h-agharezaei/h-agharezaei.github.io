+++
date = '2027-04-19T10:00:00+03:30'
draft = false
title = 'ADRs and documenting decisions'
contentType = 'tutorial'
description = 'ADRs and documenting decisions: four records in a Go repo, a checker run on good and broken sets, superseding instead of editing, and an index.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["adr", "documentation", "architecture", "software-engineering", "go"]
cover = { image = "/images/covers/eng-adr-documentation.png", alt = "ADRs and documenting decisions", hiddenInSingle = true }
+++

Six months after a decision, a new teammate asks: "why do we poll the outbox instead of publishing straight to the broker?" Nobody remembers. Somebody half-recalls a long chat thread, nobody can find it, and so the team either argues the decision again from scratch or, worse, undoes it without knowing what it was protecting.

The fix is old and cheap: write down the why, in the repo, next to the code. An {{< term "adr" "ADR" >}} (architecture decision record) is a short text file that keeps one decision, the reasons for it, and what it costs. The register in [Technical debt](/posts/eng-technical-debt/) recorded what was wrong and what to do about it; an ADR records why the system is shaped the way it is. It is reviewed like code, as in [Effective code review](/posts/eng-code-review/), and a post like [API design: versioning and pagination](/posts/eng-api-design-versioning-pagination/) is full of decisions that would be worth recording. I mark my opinions with **in my opinion**. The checks and git outputs were run.

> The demo is a small Go repo for an orders service with four ADRs. The service and the ADRs are invented, with a fake author and fixed dates, and the decisions are not recommendations. I originally ran it with Go 1.26 and re-ran every command below with Go 1.27.3 for this edit.

## The format

An ADR is short on purpose. I use the layout Michael Nygard proposed when he introduced the idea: a Title, a Status, a Context, a Decision and Consequences. Here is ADR 4 from the demo in full, so you can see what a real one looks like. It replaces ADR 2:

```markdown
# 4. Run several relays with SKIP LOCKED

## Status

Accepted

Supersedes [2. Use an outbox in Postgres](0002-use-an-outbox-in-postgres.md)

## Context

ADR 2 chose one polling relay. It stopped publishing during a deploy and events were late. We still want the outbox itself.

## Decision

We keep the outbox table from ADR 2, but run two or more relays. Each claims rows with `SELECT ... FOR UPDATE SKIP LOCKED` inside a transaction.

## Consequences

A relay can restart without stopping delivery. Order between events of different orders is no longer guaranteed, and a crash after publish but before commit still duplicates an event, so consumers stay idempotent.
```

Here is how to read it, section by section.

- **Title.** A number and a short sentence in the imperative: "Run several relays with SKIP LOCKED". The number never changes. It is how other records point at this one.
- **Status.** Where the decision stands: proposed, accepted, superseded or deprecated. This one is accepted, and it says it supersedes ADR 2, meaning it replaces it.
- **Context.** The situation that forced a decision: what hurt, what the constraints were. It does not mention the solution yet. Here: one relay stopped during a deploy, and events were late.
- **Decision.** What we chose, in one or two sentences, in active voice: "We keep the outbox table, but run two or more relays."
- **Consequences.** What follows from the decision, good and bad. Here the bad part is stated plainly: ordering between orders is lost and duplicates are still possible.

The other three records are in the same shape. ADR 1 says we keep ADRs at all. ADR 2 uses an {{< term "outbox-pattern" "outbox" >}} table instead of writing to the database and the broker separately ("dual writes"). ADR 3 chooses {{< term "jetstream" "JetStream" >}} for events. ADR 4 is the one above. Consumers must stay {{< term "idempotency" "idempotent" >}}, which means processing the same event twice does no harm, as in [the outbox post](/posts/go-outbox-pattern-nats/).

A common alternative layout is MADR, a Markdown template with an explicit list of options. I put ADR 3 in that style next to the other one, in `docs/adr-madr/`:

```markdown
# Use NATS JetStream for events
* Status: accepted
## Considered Options
* NATS JetStream
* Kafka
## Decision Outcome
Chosen option: "NATS JetStream", because the team already runs NATS.
```

This is an abbreviated excerpt of the file. **In my opinion** the difference is small: MADR forces you to list the options you rejected, and Nygard's layout is shorter. Pick one and stay with it.

## Writing a good Context and Consequences

The Title, Status and Decision are easy. Most of the value, and most of the mistakes, are in the other two sections.

- Context states forces, not the solution: what hurt, what constraints exist, what we do not know yet. If the context already argues for the answer, the reader cannot judge the decision.
- Consequences must include a cost. An ADR whose consequences are all good reads like a sales pitch. ADR 2 admits it is a "single point of failure", and ADR 4 later fixed exactly that. That link between the two records is only possible because the first one was honest.
- Write the ADR in the pull request that implements the decision, while the reasons are still fresh.

## Statuses and immutability

The statuses I use are proposed, accepted, superseded and deprecated. **In my experience** one rule keeps ADRs trustworthy: never rewrite an accepted ADR. You may fix a typo and change the status line, nothing else. If you change your mind, you write a new ADR that says "Supersedes 2", and ADR 2 gets the line "Superseded by 4". Nothing is deleted, so a reader can see both what the team believed then and what it believes now.

## A checker

Rules like these rot unless a machine enforces them. So I wrote a small Go program, `adrcheck`, using only the standard library (199 lines). It checks that numbering is sequential, that the filename matches the title, that the required sections are present, that the status is one of the allowed ones, and that every `Supersedes` link points to a file that is marked as superseded by this one. On the good set it prints:

```text
$ go run ./cmd/adrcheck check docs/adr
ok
```

A checker is only believable if I have seen it fail. So I made a copy of the set and broke it on purpose: a renamed file, an invented status "Approved", a missing ADR 3, a deleted section, and ADR 2 no longer marked as superseded:

```text
$ go run ./cmd/adrcheck check testdata/broken
FAIL 0001-record-decisions.md: filename slug should be "record-architecture-decisions"
FAIL 0002-use-an-outbox-in-postgres.md: status "approved" is not one of proposed/accepted/superseded/deprecated
FAIL 0004-run-several-relays-with-skip-locked.md: expected number 0003 (numbering must be sequential)
FAIL 0005-use-nats-jetstream-for-events.md: missing or empty section Consequences
FAIL 0004-run-several-relays-with-skip-locked.md: supersedes 0002-use-an-outbox-in-postgres.md, but that file is not marked 'Superseded by' this one
5 problem(s)
```

Each line names a file and the rule it broke, and the five lines match the five things I broke. The last line is the interesting one: it is the case where ADR 4 claims to replace ADR 2, but ADR 2 does not say so. (The program also exits with status 1, so CI turns red.)

The same program has a `links` mode that checks relative markdown links between the docs:

```text
$ go run ./cmd/adrcheck links testdata/badlinks
FAIL testdata/badlinks/README.md: broken link runbook.md
FAIL testdata/badlinks/README.md: broken link adr/0009-nope.md
2 problem(s)
```

Both commands belong in {{< term "ci" "CI" >}}. I wrote the workflow below, but I did not run it on GitHub. I ran only the two commands locally:

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

It runs only when a pull request touches the docs or the checker, and it runs the two commands in order.

The tool can also generate the index `docs/adr/README.md` from the files themselves (`adrcheck index docs/adr`), so nobody edits an index by hand and it cannot go out of date:

```text
| # | Title | Status |
|---|---|---|
| 1 | [Record architecture decisions](0001-record-architecture-decisions.md) | accepted |
| 2 | [Use an outbox in Postgres](0002-use-an-outbox-in-postgres.md) | superseded |
| 3 | [Use NATS JetStream for events](0003-use-nats-jetstream-for-events.md) | accepted |
| 4 | [Run several relays with SKIP LOCKED](0004-run-several-relays-with-skip-locked.md) | accepted |
```

(This is the table part of the generated file, which also has a heading and a "do not edit" line above it.)

## Why in the repo

A decision in a wiki or chat is separated from the code it explains. In the repo, git keeps them together. History survives even a rename. Here is the history of ADR 2, which was renamed once:

```text
$ git log --follow --format="%h %ad %s" --date=short -- docs/adr/0002-use-an-outbox-in-postgres.md
5e19d0e 2027-03-15 ADR 4: run several relays; mark ADR 2 superseded
0f3b713 2027-02-22 ADR 2: clearer title, rename file
f45c20c 2027-02-08 Add polling outbox relay (ADR 0002)
```

`--follow` makes git continue the history across the rename. The oldest line shows that the ADR was added in the same commit as the relay code. That is the useful part. A comment in the code points to the record, and `git blame` leads from the code to that commit:

```text
$ git blame -L 6,6 internal/outbox/relay.go
f45c20ca (Roham 2027-02-08 10:00:00 +0330 6) // PollInterval is how often the single relay polls. See docs/adr/0002.
```

A wiki page cannot be in the same commit as the code it explains.

## Which document?

ADRs are not the only kind of document, and they do not replace the others. This table shows how I tell them apart:

| Document | Answers | Lives | My rule of thumb |
|---|---|---|---|
| {{< term "rfc" "RFC" >}} / design doc | what should we build, with alternatives | before the work | long, discussed, may be thrown away |
| ADR | what did we decide and why | with the code | short, immutable |
| README | what is this, how do I run it | with the code | current state only |
| {{< term "runbook" "Runbook" >}} | what do I do at 3 a.m. | with the service | edited constantly |

This table is my opinion, not a standard.

## When not to write one

Do not write an ADR for easily reversible choices (a variable name, a lint rule) or for decisions that are obvious from the code. **In my opinion** the test is: would a new teammate, a year from now, plausibly undo this out of ignorance? If yes, write it down.

## How ADRs lose their value

- **Written after the fact.** An ADR written long after the decision tends to justify rather than explain.
- **Edited "to keep it correct".** Do not edit old ADRs. Supersede them, so the history stays honest.
- **Statuses that lie.** A status only means something if the checker fails when it is wrong.
- **Structure is not quality.** A checker proves the structure, not that the reasoning is good. Reviewers still have to read.

## Exercise

Write one ADR for a decision your team made last month, in the template above, with one honest negative consequence. Then rename the file and see what a checker would say.

## What's next

The next post is "Feature flags and trunk-based development". An ADR records a decision after it is made. The next question is how to keep a change reversible even after it has shipped.
