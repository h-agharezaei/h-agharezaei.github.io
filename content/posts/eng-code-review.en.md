+++
date = '2027-03-17T10:00:00+03:30'
draft = false
title = 'Effective code review'
contentType = 'tutorial'
description = 'Effective code review in Go: let gofmt, vet, the race detector and staticcheck go first, then see what only a human catches and how to say it kindly.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["code-review", "software-engineering", "testing", "go", "collaboration"]
cover = { image = "/images/covers/eng-code-review.png", alt = "Effective code review", hiddenInSingle = true }
+++

Picture a code review where the first comment says "this line is indented wrongly", the second says "I would name this variable differently", and the approval comes after ten minutes. Meanwhile the change has a real bug in it, and nobody saw it, because the reviewer's attention was spent on things a program could have found.

To see how much a machine can and cannot catch, I planted seven problems in a small Go pull request (PR) and ran the usual tools on it. `gofmt`, `go vet` and the race detector together caught three. A response body that is never closed, leaked goroutines and an off-by-one error passed every tool. {{< term "code-review" "Code review" >}}, a person reading a change before it is merged, is the net for those. It is also expensive, because a reviewer's attention is the scarcest thing on a team. My rule follows from that: machines go first, and humans review what machines cannot see.

Unlike the safety net in [Refactoring safely](/posts/eng-refactoring-safely/), which was a test, this one is made of people. Test basics are in [Testing in Go](/posts/go-testing-basics/), and layering is in [Project layout and clean architecture](/posts/go-project-layout-clean-architecture/). I mark my opinions with **in my experience**. The findings below come from actual runs.

> The demo is a local git repo with two commits and a branch. I originally ran it with Go 1.26 and re-ran it with Go 1.27.3 for this edit. The code is invented and flawed on purpose. I could not re-run staticcheck in this re-run, so its result below is from the original run.

## A flawed PR

On `main` there is a small `Page` helper that already has a test. The branch `add-bulk-check` adds a link checker (a program that requests many URLs and reports their status codes). The size of the change looks like this:

```text
$ git diff main --stat
 check.go      | 54 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
 check_test.go | 25 +++++++++++++++++++++++++
 2 files changed, 79 insertions(+)
```

The seven planted problems are:

1. a mis-indented line;
2. a wrong `Printf` verb (`%s` for an integer);
3. several goroutines writing to one map at the same time;
4. an unchecked error;
5. an HTTP response body that is never closed;
6. a goroutine that leaks (it blocks forever and is never cleaned up);
7. `LastPage` returning `total / size`, which rounds down.

Here is the core of the diff, so you can look for the problems yourself before I show what found them:

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

I ran the cheap automatic checks first. `gofmt -l` lists files that are not formatted, and `go vet` looks for suspicious constructs:

```text
$ gofmt -l .
check.go

$ go vet ./...
check.go:27:29: fmt.Printf format %s has arg code of wrong type int
```

Problem 1 (indentation) and problem 2 (the verb) are found. Next, `go test -race` runs the tests with the race detector, which watches memory accesses and reports when two goroutines touch the same variable without synchronization. I added `-vet=off`, because plain `go test` runs a subset of vet and would stop at the same `Printf` line before reaching the race. The race detector printed `WARNING: DATA RACE`, with the stacks of both goroutines pointing at the map write on line 28, and then `--- FAIL: TestCheckAll`. {{< term "race-condition" "The race" >}} is only caught because the test happens to check two URLs at once. A test with one URL would have passed.

I also ran staticcheck, pinned to one version, with `go run honnef.co/go/tools/cmd/staticcheck@2025.1.1 ./...`. It reported one thing, the same `Printf` problem (`SA5009`). It did **not** report the ignored error, the unclosed body, the leak or the boundary error. A {{< term "static-analysis" "static analyzer" >}} only knows the patterns it was written for. (This was the original run. When I tried to run it again for this edit, my environment would not let me run a freshly downloaded tool, so I did not re-run it.)

The practical advice is to run all four in {{< term "ci" "CI" >}}, so that the human reviewer never has to spend a comment on them.

## What only a human catches

Four problems are left, and plain `go test -vet=off` passes. The coverage report shows why the tests did not notice:

```text
Status    75.0%
CheckAll  100.0%
FirstOK   0.0%
LastPage  66.7%
```

`FirstOK` is never run by any test at all. `Status` and `LastPage` have lines that are never executed. So these findings could not have come from a tool above:

- **Ignored error.** In `CheckAll`, `code, _ := Status(u)` throws the error away. When a request fails, `Status` returns 0 and the result map just says 0, so nobody can tell "unreachable" from anything else.
- **Unclosed body.** `Status` never calls `resp.Body.Close()`. The test passes anyway, because one short test does not run out of connections. In production, each unclosed response keeps its connection from being reused.
- **Leaked goroutines.** `FirstOK` starts one goroutine per URL and returns the first answer. The others try to send their answer on a channel nobody reads anymore, so they wait forever. In a throwaway test I called `FirstOK` with three working URLs and counted the goroutines stuck on that channel send after 200 ms. For this edit I counted again and found two, the two that lost the race. (In the original run I counted all goroutines instead: 3 before and 11 after, which also includes connection goroutines I did not separate.)
- **Boundary.** `LastPage(11, 5)` returned 2, but eleven items need 3 pages. The only test used 10 and 5, the one case that happens to work.

Then there are things no tool can judge. `Status` and `FirstOK` hide the call to `http.Get`, so they cannot be tested without a live server, and the default HTTP client has no timeout. That is design, and the review is the place for it.

## Say it as what / why / suggestion

Finding a problem is half the work. The other half is how you say it. I like a comment with three parts: what is wrong, why it matters, and what I suggest:

```text
check.go:11  What: resp.Body is never closed.
             Why: connections are not reused and leak under load.
             Suggestion: defer resp.Body.Close() after the err check.

check.go:49  What: LastPage(11, 5) returns 2.
             Why: integer division rounds down, the last partial page is lost.
             Suggestion: (total+size-1)/size, plus a test with 11 and 5.
```

**In my experience** a comment with a reason and a way out gets fixed in one round. A bare "this is wrong" starts a thread. Tone helps as well. Ask instead of declaring ("could this block if the first call fails?"). Start small things with `nit:` so the author knows they are optional. And say so when something is good.

## The author's side

Review is a two-person job, and the author can do a lot to make it easier.

- **Read your own diff first.** **In my experience** you find several issues yourself.
- **Keep PRs small.** To show the effect, I made two throwaway branches, one with 40 added lines and one with 900, and only looked at the git stat: `1 file changed, 40 insertions(+)` against `6 files changed, 900 insertions(+)`. **In my experience** nobody really reads the second one. They skim it and approve.
- **Write a short description.** What changed, why, how I tested it, and what I did not test.

## When you disagree

Move from taste to evidence: a failing test, a measurement, the project's own style guide. If it is still taste, the author decides, and the reviewer writes `nit:`. If it is a design question, talk in person or on a call, and then write the result down in the PR so the decision is not lost.

## Concepts I did not run

A {{< term "codeowners" "CODEOWNERS" >}} file asks the owners of a path to review changes to it. {{< term "branch-protection" "Branch protection" >}} can require approvals and green checks before a merge. Both live on the hosting platform, and I did not set up either here.

## Where reviews waste attention

- **Reviewing style by hand.** Automate it, as above.
- **Reading the code before the tests.** Review the tests first. If they would not fail on a bug, the code under them is effectively unreviewed.
- **Long marathon sessions.** Review in short sessions. **In my experience** attention drops sharply after about an hour. That is not a measurement.
- **Withholding approval for nothing.** Approve with comments when nothing blocks the merge.

## Exercise

Take your last merged PR. Run `gofmt -l`, `go vet`, `go test -race` and staticcheck on it. Then write one what / why / suggestion comment for something none of them reported.

## What's next

The next post is "API design: versioning and pagination". A review is about one change and one author. In API design a single change has to work for many clients at once, so a mistake costs more.
