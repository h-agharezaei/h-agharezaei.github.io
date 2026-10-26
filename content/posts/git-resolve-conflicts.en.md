+++
date = '2026-11-05T10:00:00+03:30'
draft = false
title = 'Resolving conflicts and rerere'
description = 'Resolve Git merge conflicts step by step: read the markers, abort safely, understand ours vs theirs in merge and rebase, and reuse fixes with rerere.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge-conflict", "rerere", "beginner"]
cover = { image = "/images/covers/git-resolve-conflicts.png", alt = "Resolving conflicts and rerere", hiddenInSingle = true }
+++

In the [previous post](/posts/git-merge-vs-rebase/) we compared merge and rebase on two real histories. Both can stop halfway and ask you a question, and that moment scares many beginners. A {{< term "merge-conflict" "conflict" >}} is not an error in your repository. It is Git saying "two people changed the same place, you decide".

> Everything below was run with Git 2.39.2 on a throwaway repository, and the outputs are copied from those runs.

## Making a conflict

`main` and `feature` both change the `status:` line of `notes.txt`, starting from `status: draft`. Then:

```text
$ git merge feature
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Automatic merge failed; fix conflicts and then commit the result.
```

`git status` shows the state:

```text
Unmerged paths:
  (use "git add <file>..." to mark resolution)
	both modified:   notes.txt
```

"Both modified" is the conflict state: the same file changed on both sides. Git also tells you the way out, `git merge --abort`.

## Reading the markers

Git wrote both versions into the file:

```text
title: Report
<<<<<<< HEAD
status: published
=======
status: review
>>>>>>> feature
owner: nobody
```

Between `<<<<<<<` and `=======` is your side (`HEAD`, the branch you are on). Between `=======` and `>>>>>>>` is the other side. During the conflict, `git diff` shows a combined diff with two columns of `+` and `-`, one per side.

## Resolving

Edit the file into the final text, delete all marker lines, then tell Git it is done:

```bash
printf 'title: Report\nstatus: published\nowner: nobody\n' > notes.txt
git add notes.txt
git commit
```

`git add` is the "resolved" signal. The markers are just text; if you commit them, they stay.

## Backing out

If you are lost, abort. After `git merge --abort` the status was back to a clean `## main`. For a rebase, `git rebase --abort` returned me to `## feature` with the original commit `ea78c57` untouched.

## ours and theirs swap

`git checkout --ours -- file` and `--theirs` pick one side. The names are confusing, because a {{< term "rebase" "rebase" >}} replays your commits on top of the other branch. I stood on `feature` in both cases and checked what `--ours` gave:

| Operation on `feature` | `--ours` | `--theirs` |
|---|---|---|
| `git merge main` | `status: review` (feature) | `status: published` (main) |
| `git rebase main` | `status: published` (main) | `status: review` (feature) |

In a merge, "ours" is the branch you are on. In a rebase, Git is building a new history on top of `main`, so "ours" is that growing history and "theirs" is the commit being replayed, which is your own work. So "ours" is the base you build on.

## Seeing the base with zdiff3

By default you only see the two sides. With `git config merge.conflictStyle zdiff3` (available since Git 2.35, and my 2.39.2 has it) the markers also include the common ancestor from the {{< term "three-way-merge" "three-way merge" >}}:

```text
<<<<<<< HEAD
status: published
||||||| a4fb5af
status: draft
=======
status: review
>>>>>>> feature
```

Now you see both sides changed `draft`, to `published` and to `review`.

## rerere: resolve once

If you rebase a long branch repeatedly, or merge and then redo the merge, you meet the same conflict again. {{< term "rerere" "rerere" >}} ("reuse recorded resolution") remembers how you solved it:

```bash
git config rerere.enabled true
```

First time, Git records the conflicted text:

```text
CONFLICT (content): Merge conflict in notes.txt
Recorded preimage for 'notes.txt'
```

I resolved it and committed, and Git printed `Recorded resolution for 'notes.txt'.` Then I threw the merge away with `git reset --hard HEAD~1` and merged again:

```text
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Resolved 'notes.txt' using previous resolution.
Automatic merge failed; fix conflicts and then commit the result.
```

The file already contained my answer. Note that `git status` still showed `UU notes.txt`: rerere fills the file but does not stage it. You review, `git add`, and commit.

What it stores: a folder per conflict in `.git/rr-cache`, named by a hash of the conflicted text, holding a `preimage` (the conflict) and a `postimage` (your resolution). While a conflict is open, `git rerere status` lists the files it tracks and `git rerere diff` shows the current state of your resolution.

Limits: it matches the same conflicting text, so a changed neighbouring line means a new conflict. It is local to your clone, and it records only content conflicts. If a recorded resolution was wrong, `git rerere forget <path>` is the tool to drop it; I did not verify that step. Mergetools (`git mergetool`) open a visual three-pane editor; I did not run one here.

## A few things to watch

- Never commit the marker lines; search for `<<<<<<<` first.
- Run your tests after resolving. A clean textual merge can still be wrong semantically.
- During a rebase, resolve, `git add`, then `git rebase --continue`. Do not run `git commit` yourself.
- Do not trust "ours" and "theirs" in a rebase without checking the file, as the table shows.
- Read what rerere produced before you stage it.

## Exercise

Create a repo with two branches changing the same line. Merge and resolve with zdiff3 turned on. Reset the merge, enable rerere, resolve again, reset, and merge a third time. Look inside `.git/rr-cache`. Repeat with `git rebase` and check what `--ours` gives.

## What's next

The next post is "Undoing work: reflog, revert and cherry-pick".
