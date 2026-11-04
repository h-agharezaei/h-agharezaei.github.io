+++
date = '2026-11-09T10:00:00+03:30'
draft = false
title = 'Finding a bug with git bisect'
description = 'git bisect finds the commit that broke your code with a binary search, by hand or fully automatic with git bisect run, with real runs on a 30-commit repo.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "bisect", "debugging", "beginner"]
cover = { image = "/images/covers/git-bisect.png", alt = "Finding a bug with git bisect", hiddenInSingle = true }
+++

Imagine that last month everything worked, today something is broken, and 30 commits sit between the two. Which one broke it? This problem has a name: a {{< term "regression" "regression" >}}, something that used to work and no longer does.

The clumsy way is to open the commits one by one and read each diff, up to 29 times in the worst case. `git bisect` answers the same question in about five tests. [Undoing work](/posts/git-undo-reflog-revert/) is easy once you know which commit to revert; bisect is how you find that commit.

> Everything below was run with Git 2.39 in a local demo repo. The commit hashes are real output from that run; on your machine they will differ.

## The idea: halve it

Picture a 30-page book. Page 1 is clean and the last page has a stain. On which page did the stain start? You do not need to flip through from the beginning. Open page 15: if it is clean, the stain started somewhere in 16 to 30; if it is stained, somewhere in 2 to 15. Every time, half of the possibilities disappear.

`git bisect` does exactly this to history. The method has a name: {{< term "binary-search" "binary search" >}}. You give it one good commit and one bad commit, Git checks out the commit in the middle, you test it and answer "good" or "bad", and Git halves the range. It continues until it reaches the first bad commit. {{< term "git-bisect" "git bisect" >}} has one requirement: at every commit you must be able to tell whether it is good or bad.

## The setup

To see it work I generated a repo with 30 commits. `calc.sh` defines `total()`, which should multiply two numbers. Commit 19 ("speed up total") silently changes `*` to `+`. All other commits just add a note file. So the bug lives in one known commit, and we can check whether bisect finds it.

The test is a short script. It runs `total 10 3` and exits with 0 (good) if the answer is `30`, and with 1 (bad) otherwise:

```sh
#!/bin/sh
[ "$(sh -c '. ./calc.sh; total 10 3')" = "30" ]
```

It fails on `main` (10 + 3 is 13) and passes on commit 1.

## Manual bisect

First we start bisect and name one bad commit (`main`, the current one) and one good commit (commit 1):

```text
$ git bisect start
$ git bisect bad
$ git bisect good <commit 1>
Bisecting: 14 revisions left to test after this (roughly 4 steps)
[5c39676...] commit 15: add note 15
```

(Git also prints a few `status:` lines, which I left out for brevity.) The message says that after this test there are still 14 suspect commits and about 4 more steps. Then Git checked out the middle of the range, commit 15.

At each step I ran `./test.sh`, answered with `git bisect good` or `git bisect bad`, and repeated. Here are the five steps in a summary; each line says which commit I was on, my answer, and where Git put the next one:

```text
commit 15 -> good   Bisecting: 7 revisions left (roughly 3 steps) -> commit 22
commit 22 -> bad    Bisecting: 3 revisions left (roughly 2 steps) -> commit 18
commit 18 -> good   Bisecting: 1 revision left  (roughly 1 step)  -> commit 20
commit 20 -> bad    Bisecting: 0 revisions left (roughly 0 steps) -> commit 19
commit 19 -> bad
8e5fe5f... is the first bad commit
    commit 19: speed up total
 calc.sh       | 2 +-
 notes/n19.txt | 1 +
```

Reading it: commit 15 was good, so the bug came later and Git went to 22. Commit 22 was bad, so the bug is between 16 and 22, and Git picked 18. Commit 18 was good and 20 was bad. Finally 19 was bad, and since its parent (18) was good, Git announced that 19 is the first bad commit. (The last lines are the diffstat; I shortened the real output a little.)

Five tests for 29 candidate commits, which matches log2(29) rounded up. With 1000 commits it would be about 10. Compare that with reading 30 diffs by hand: I would have opened up to 29 commits, and most of them are noise.

## Fully automatic: git bisect run

If a script can decide good or bad, why answer by hand? `git bisect run` runs the script at every step and reads the answer from its exit code:

```text
$ git bisect start HEAD <commit 1>
$ git bisect run ./test.sh
running  './test.sh'
...
8e5fe5fb5fcb245d276ce9c7b4df8f29369b444e is the first bad commit
commit 8e5fe5f...
    commit 19: speed up total
 calc.sh       | 2 +-
 notes/n19.txt | 1 +
bisect found first bad commit
```

(The dots stand for the middle steps, which go as above.) It took the same five steps with no typing from me. This is the real payoff: write a failing test first, then bisect. That test both tells you what the problem is and lets bisect run on its own.

## Log and reset

`git bisect log` prints every decision as replayable commands (`git bisect good 5c39676...`, and so on, ending with `# first bad commit: [8e5fe5f...]`). Save it to a file and replay it with `git bisect replay`, for example when you gave one answer wrong. Always finish with:

```text
$ git bisect reset
Previous HEAD position was 8e5fe5f commit 19: speed up total
Switched to branch 'main'
```

Bisect leaves you standing on a commit without a branch (a detached checkout) in the middle of history, and you stay there until you reset. `reset` takes you back to your branch.

## Commits you cannot test

Sometimes a midpoint does not even build, so the test can say neither good nor bad. In a second demo repo, commit 15 has a syntax error in `calc.sh` (fixed again in commit 16). The test now starts with `sh -n calc.sh || exit 125`; `sh -n` only checks syntax and the `exit 125` runs if it finds an error. By hand, I saw this:

```text
calc.sh: line 1: unexpected EOF while looking for matching `)'
exit 125
$ git bisect skip
Bisecting: 13 revisions left to test after this (roughly 4 steps)
[51e8a2e...] commit 16
```

The first line is `sh` complaining about the broken file. With `git bisect skip` I told Git to set this commit aside, and it brought the next one (16).

Exit code 125 is special for `git bisect run`: it means "skip this commit". The automatic run still found commit 19, and `git bisect log` recorded the `# skip: [d55fa36...] commit 15` line. If every commit near the culprit is untestable, Git can only tell you a range, not one commit.

## git bisect visualize

`git bisect visualize` shows the remaining suspect commits in a graphical viewer. I did not run it here because it needs a UI.

## Where bisect misleads

- **Know the exit codes.** According to the Git docs, 0 is good, 1 to 127 except 125 is bad, 125 is skip, and 128 or more aborts the bisect. So a script that crashes with a high code stops the whole run.
- **Your test script must be available at every commit Git checks out.** Mine is committed in commit 1. An untracked file outside the history also works, because checkout does not touch it.
- **Bisect assumes the bug stays once introduced.** If the test is flaky (sometimes passes, sometimes fails), one wrong answer halves the range the wrong way and you end up at an innocent commit.
- **Always `git bisect reset` before continuing normal work.** Otherwise you stay on a commit in the middle of history.
- **Bisect shines with {{< term "atomic-commit" "atomic commits" >}}.** An atomic commit is one small logical change that builds on its own. With such commits, "first bad commit" is a diff you can read in a minute. A giant "fix stuff" commit makes the answer useless.

## Exercise

1. Create a repo of 30 commits with a script, break a function at commit 19, and write `test.sh`.
2. Bisect by hand and count the steps. Then run it with `git bisect run`.
3. Make one midpoint commit unbuildable and watch `exit 125` skip it.

## What's next

Next is "Hooks and clean commit messages": how to stop bad commits before they enter history, which is what keeps bisect useful.
