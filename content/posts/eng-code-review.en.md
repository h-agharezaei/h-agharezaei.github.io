+++
date = '2027-03-17T10:00:00+03:30'
draft = false
title = 'Effective code review'
description = 'Effective code review in Go: let gofmt, vet, the race detector and staticcheck go first, then see what only a human catches and how to say it kindly.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["code-review", "software-engineering", "testing", "go", "collaboration"]
cover = { image = "/images/covers/eng-code-review.png", alt = "Effective code review", hiddenInSingle = true }
+++

In [Refactoring safely](/posts/eng-refactoring-safely/) the safety net was a test. A {{< term "code-review" "code review" >}} is the other net, made of people, and it is expensive: a reviewer's attention is the scarcest thing on a team. So the rule I follow is that machines go first and humans review what machines cannot see. Test basics are in [Testing in Go](/posts/go-testing-basics/), layering in [Project layout and clean architecture](/posts/go-project-layout-clean-architecture/). Opinions are marked **in my experience**; the findings below were run.

> Go 1.26, a local git repo with two commits and a branch; the code is invented and flawed on purpose.

## A flawed PR

On `main` there is a tested `Page` helper. The branch `add-bulk-check` adds a link checker:

```text
$ git diff main --stat
 check.go      | 54 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
 check_test.go | 25 +++++++++++++++++++++++++
 2 files changed, 79 insertions(+)
```

The planted problems: a mis-indented line, a wrong `Printf` verb, concurrent writes to a map, an unchecked error, an unclosed response body, a leaked goroutine, and `LastPage` returning `total / size`. The core of the diff:

```go
func Status(url string) (int, error) {
	resp, err := http.Get(url)
	if err != nil {
		return 0, err
	}
	return resp.StatusCode, nil
}

go func() {
	defer wg.Done()
	code, _ := Status(u)
	fmt.Printf("checked %s: %s\n", u, code)
	out[u] = code
}()
```

## Machines first

```text
$ gofmt -l .
check.go

$ go vet ./...
check.go:27:29: fmt.Printf format %s has arg code of wrong type int
```

`go test -race` (I added `-vet=off`, because plain `go test` runs a vet subset and would stop at the same Printf line) printed `WARNING: DATA RACE` with both goroutine stacks pointing at the map write on line 28, then `--- FAIL: TestCheckAll`. {{< term "race-condition" "The race" >}} is caught only because the test exercises two URLs at once.

I pinned staticcheck with `go run honnef.co/go/tools/cmd/staticcheck@2025.1.1 ./...` and it reported one thing, the same Printf (`SA5009`). It did **not** flag the ignored error, the unclosed body, the leak or the boundary. A {{< term "static-analysis" "static analyzer" >}} only knows its patterns. Run all four in {{< term "ci" "CI" >}} so the human never spends a comment on them.

## What only a human catches

Plain `go test -vet=off` passes. Coverage says why:

```text
Status    75.0%
CheckAll  100.0%
FirstOK   0.0%
LastPage  66.7%
```

The three remaining findings, which no tool above reported:

- Unclosed body: `Status` never calls `resp.Body.Close()`. The test passes anyway.
- Leaked goroutines: in a throwaway test I called `FirstOK` with three URLs; goroutines went from 3 to 11 after 200 ms (probably some are connection goroutines, which I did not separate). The losers block forever on the unbuffered channel.
- Boundary: `LastPage(11, 5)` returned 2; eleven items need 3 pages. The one test used 10 and 5, the case that happens to work.

Then the things a tool cannot judge: `Status` and `FirstOK` hide `http.Get`, so they cannot be tested without a live server, and the default client has no timeout. That is design, and the review is the place for it.

## Say it as what / why / suggestion

```text
check.go:11  What: resp.Body is never closed.
             Why: connections are not reused and leak under load.
             Suggestion: defer resp.Body.Close() after the err check.

check.go:49  What: LastPage(11, 5) returns 2.
             Why: integer division rounds down, the last partial page is lost.
             Suggestion: (total+size-1)/size, plus a test with 11 and 5.
```

**In my experience** a comment with a reason and a way out gets fixed in one round; a bare "this is wrong" starts a thread. Tone helps too: ask ("could this block if the first call fails?"), prefix small things with `nit:`, and praise what is good.

## The author's side

- Self-review the diff before asking anyone; **in my experience** you find several issues yourself.
- Small PRs. I made two throwaway branches, 40 and 900 added lines, just to show the stat: `1 file changed, 40 insertions(+)` against `6 files changed, 900 insertions(+)`. **In my experience** nobody reads the second one; they skim and approve.
- A short description: what changed, why, how I tested it, what I did not test.

## When you disagree

Move from taste to evidence: a failing test, a measurement, the project's own style guide. If it is still taste, the author decides, and the reviewer writes `nit:`. If it is design, talk in person or a call, then write the result down in the PR.

## Concepts I did not run

A {{< term "codeowners" "CODEOWNERS" >}} file asks the owners of a path to review, and {{< term "branch-protection" "branch protection" >}} can require approvals and green checks before merge. Both live on the hosting platform; I did not set either up here.

## A few things to watch

- Do not review style by hand; automate it.
- Review the tests first: if they would not fail on a bug, the code under them is unreviewed.
- Review in short sessions; **in my experience** attention drops sharply after about an hour (my experience, not a measurement).
- Approve with comments when nothing blocks.

## Exercise

Take your last merged PR. Run `gofmt -l`, `go vet`, `go test -race` and staticcheck on it, then write one what / why / suggestion comment for something none of them reported.

## What's next

The next post is "API design: versioning and pagination".
