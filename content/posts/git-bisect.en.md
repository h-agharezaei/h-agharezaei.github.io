+++
date = '2026-11-09T10:00:00+03:30'
draft = false
title = 'Finding a bug with git bisect'
description = 'git bisect finds the commit that broke your code with a binary search, by hand or fully automatic with git bisect run, with real runs on a 30-commit repo.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "bisect", "debugging", "beginner"]
cover = { image = "/images/covers/git-bisect.png", alt = "Finding a bug with git bisect", hiddenInSingle = true }
+++

In the [previous post](/posts/git-undo-reflog-revert/) we learned how to undo work. Now a harder question: something that worked last month is broken today, and 30 commits sit in between. Which one did it? That is a {{< term "regression" "regression" >}}, and `git bisect` is the tool for it.

> Everything below was run with Git 2.39 in a local demo repo. The commit hashes are real output from that run.

## The setup

I generated a repo with 30 commits. `calc.sh` defines `total()`, which should multiply two numbers. Commit 19 ("speed up total") silently changes `*` to `+`. All other commits just add a note file. The test is a script that exits 0 when good and 1 when bad:

```sh
#!/bin/sh
[ "$(sh -c '. ./calc.sh; total 10 3')" = "30" ]
```

It fails on `main` and passes on commit 1.

## Manual bisect

{{< term "git-bisect" "git bisect" >}} runs a {{< term "binary-search" "binary search" >}} over history. Tell it one bad and one good commit:

```text
$ git bisect start
$ git bisect bad
$ git bisect good <commit 1>
Bisecting: 14 revisions left to test after this (roughly 4 steps)
[5c39676...] commit 15: add note 15
```

Git checked out the middle. I ran `./test.sh`, answered `git bisect good` or `git bisect bad`, and repeated:

```text
commit 15 -> good   Bisecting: 7 revisions left (roughly 3 steps) -> commit 22
commit 22 -> bad    Bisecting: 3 revisions left (roughly 2 steps) -> commit 18
commit 18 -> good   Bisecting: 1 revision left  (roughly 1 step)  -> commit 20
commit 20 -> bad    Bisecting: 0 revisions left (roughly 0 steps) -> commit 19
commit 19 -> bad
8e5fe5f... is the first bad commit
    commit 19: speed up total
 calc.sh       | 2 +-
```

Five tests for 29 candidate commits, which matches log2(29) rounded up. With 1000 commits it would be about 10. Compare that with reading 30 diffs by hand: I would have opened up to 29 commits, and most of them are noise.

## Fully automatic: git bisect run

If a script can decide good or bad, let Git drive. The exit code is the answer:

```text
$ git bisect start HEAD <commit 1>
$ git bisect run ./test.sh
running  './test.sh'
...
8e5fe5fb5fcb245d276ce9c7b4df8f29369b444e is the first bad commit
commit 8e5fe5f...
    commit 19: speed up total
 calc.sh       | 2 +-
bisect found first bad commit
```

It took the same five steps with no typing from me. This is the real payoff: write a failing test first, then bisect.

## Log and reset

`git bisect log` prints every decision as replayable commands (`git bisect good 5c39676...`, and so on, ending with `# first bad commit: [8e5fe5f...]`). Save it to a file and replay it with `git bisect replay`. Always finish with:

```text
$ git bisect reset
Previous HEAD position was 8e5fe5f commit 19: speed up total
Switched to branch 'main'
```

Until you reset, you are on a detached checkout in the middle of history.

## Commits you cannot test

Sometimes a midpoint does not even build. In a second demo repo, commit 15 has a syntax error in `calc.sh` (fixed again in commit 16). The test now starts with `sh -n calc.sh || exit 125`. By hand, I saw this:

```text
calc.sh: line 1: unexpected EOF while looking for matching `)'
exit 125
$ git bisect skip
Bisecting: 13 revisions left to test after this (roughly 4 steps)
[51e8a2e...] commit 16
```

Exit code 125 is special for `git bisect run`: it means "skip this commit". The automatic run still found commit 19, and `git bisect log` recorded the `# skip: [d55fa36...] commit 15` line. If every commit near the culprit is untestable, Git can only tell you a range, not one commit.

## git bisect visualize

`git bisect visualize` shows the remaining suspect commits in a graphical viewer. I did not run it here because it needs a UI.

## A few things to watch

- Exit codes: 0 is good, 1 to 127 except 125 is bad, 125 is skip, and 128 or more aborts the bisect. Anything crashing with a high code will stop the run.
- Your test script must exist at every commit Git checks out. Mine is committed in commit 1; an untracked file outside the history also works.
- Bisect assumes the bug stays once introduced. A flaky test gives wrong answers.
- Always `git bisect reset` before continuing normal work.
- Bisect shines with {{< term "atomic-commit" "atomic commits" >}}: small, buildable commits turn "first bad commit" into a diff you can read in a minute. A giant "fix stuff" commit makes the answer useless.

## Exercise

1. Create a repo of 30 commits with a script, break a function at commit 19, and write `test.sh`.
2. Bisect by hand and count the steps. Then run it with `git bisect run`.
3. Make one midpoint commit unbuildable and watch `exit 125` skip it.

## What's next

Next is "Hooks and clean commit messages": how to stop bad commits before they enter history, which is what keeps bisect useful.
