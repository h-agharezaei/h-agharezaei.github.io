+++
date = '2026-11-05T10:00:00+03:30'
draft = false
title = 'Resolving conflicts and rerere'
description = 'Resolve Git merge conflicts step by step: read the markers, abort safely, understand ours vs theirs in merge and rebase, and reuse fixes with rerere.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge-conflict", "rerere", "beginner"]
cover = { image = "/images/covers/git-resolve-conflicts.png", alt = "Resolving conflicts and rerere", hiddenInSingle = true }
+++

You run `git merge feature` and get: `CONFLICT (content): Merge conflict in notes.txt`. The file is full of strange marks and Git says "automatic merge failed". Many people see this for the first time and think something broke.

Both [merge and rebase](/posts/git-merge-vs-rebase/) can stop halfway and ask you a question. A {{< term "merge-conflict" "conflict" >}} is not an error in your repository. Git is saying: "two people changed the same place, and I cannot pick one of them without your opinion; you decide." In this post we see what Git shows, how to read and resolve it, how to back out if you get lost, and how Git can learn to reuse a resolution you have already made (rerere).

> Everything below was run with Git 2.39.2 on a throwaway repository, and the outputs are copied from those runs. The commit hashes (like `ea78c57` and `a4fb5af`) belong to my first runs and will differ in yours.

## Making a conflict

To see a conflict, let us make one. The file `notes.txt` has three lines, and the middle one is `status: draft`. The `feature` branch changed it to `status: review` and committed, and the `main` branch changed the same line to `status: published`. Both started from the same point and changed one line in two different ways. Now, on `main`, we say:

```text
$ git merge feature
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Automatic merge failed; fix conflicts and then commit the result.
```

The first line says Git tried to merge automatically, the second says it failed on `notes.txt`, and the last gives the way forward: resolve it and commit. `git status` shows the state:

```text
Unmerged paths:
  (use "git add <file>..." to mark resolution)
	both modified:   notes.txt
```

(This is only part of the `git status` output.) "Both modified" is the conflict state: the same file changed on both sides. Higher up in the same output, Git also tells you the way out, `git merge --abort`. If you want a shorter output, `git status -sb` prints `UU notes.txt` for this file (`UU` means unmerged on both sides).

## Reading the markers

Now we open the file. Git wrote both versions into the file itself:

```text
title: Report
<<<<<<< HEAD
status: published
=======
status: review
>>>>>>> feature
owner: nobody
```

There are three marker lines and the parts between them:

- Between `<<<<<<<` and `=======` is your side. `HEAD` means the branch you are on (here `main`): `status: published`.
- Between `=======` and `>>>>>>>` is the other side, the `feature` branch: `status: review`.
- The lines outside the markers (`title` and `owner`) have no conflict, and Git already resolved them.

During the conflict, `git diff` shows a combined diff:

```text
diff --cc notes.txt
index b48eb8f,994df04..0000000
--- a/notes.txt
+++ b/notes.txt
@@@ -1,3 -1,3 +1,7 @@@
  title: Report
++<<<<<<< HEAD
 +status: published
++=======
+ status: review
++>>>>>>> feature
  owner: nobody
```

Instead of one column of `+` and `-` there are two, one per side: the first column compares the current file with `main`, and the second with `feature`. The line `status: published` has a `+` only in the second column, because it is an addition relative to `feature` but was already in `main`; and `status: review` is the other way around. The marker lines have `+` in both columns because they were in neither side.

## Resolving

Resolving means deciding yourself what the final text is. Edit the file so that what you want stays, delete all marker lines, then tell Git it is done. I decided `published` stays:

```bash
printf 'title: Report\nstatus: published\nowner: nobody\n' > notes.txt
git add notes.txt
git commit
```

`git add` is the "this file is resolved" signal. Then `git commit` makes the merge commit. Remember that the markers are just text; Git does not stop you from committing them. If you commit them, they stay in history.

## Backing out

If you get lost in the middle, you do not have to continue. You can cancel the whole operation and return to the state before it started. After `git merge --abort`, the status was clean again and `git status -sb` printed only `## main`.

A rebase is the same. When I ran `git rebase main` on `feature` and got a conflict, `git status -sb` showed `## HEAD (no branch)` and `UU notes.txt`. That means we are in the middle of a rebase and HEAD is temporarily not attached to any branch. With `git rebase --abort` I was back on `## feature` with the original commit `ea78c57`, unchanged.

## ours and theirs swap

Git has two names for the two sides, "ours" and "theirs", and `git checkout --ours -- file` or `--theirs` picks that side for the file. The names are confusing because their meaning changes with the operation. The reason is that **{{< term "rebase" "rebase" >}}** replays your work on top of the other branch.

To see it, in both cases I was on `feature` (which has `status: review`) and brought `main` in with the two methods. Then let us see which version `--ours` and `--theirs` give:

| Operation on `feature` | `--ours` | `--theirs` |
|---|---|---|
| `git merge main` | `status: review` (feature) | `status: published` (main) |
| `git rebase main` | `status: published` (main) | `status: review` (feature) |

In a merge, "ours" is the branch you are on. In a rebase it is the other way around. Git first stands on `main` and then replays your commits on it one by one. So at the moment of conflict, "ours" is the history being built (that is `main`) and "theirs" is the commit being replayed, which is your own work. If you run `--theirs` in a rebase, you keep your own version.

## Seeing the base with zdiff3

In the default markers you only see two sides, and you do not know what each one started from. With `git config merge.conflictStyle zdiff3` (according to the Git docs, available from version 2.35 on; my 2.39.2 has it) the common ancestor version, the base of the {{< term "three-way-merge" "three-way merge" >}}, also appears in the markers. (A three-way merge means that to combine two versions, Git compares both with the common version from before they split.)

```text
<<<<<<< HEAD
status: published
||||||| a4fb5af
status: draft
=======
status: review
>>>>>>> feature
```

The new part is between `|||||||` and `=======`, the original version (`draft`). Now it is clear that both sides changed `draft`, one to `published` and the other to `review`. When a conflict is larger than one line, seeing this original is a great help.

## rerere: resolve once

Suppose you rebase a long branch many times, or you redo a merge after undoing it. The same conflict comes back every time and you have to type the same resolution again. **{{< term "rerere" "rerere" >}}** ("reuse recorded resolution") remembers how you resolved a conflict. First we turn it on:

```bash
git config rerere.enabled true
```

The first time a conflict comes up, Git records the conflict text:

```text
CONFLICT (content): Merge conflict in notes.txt
Recorded preimage for 'notes.txt'
```

I resolved it and committed, and Git wrote `Recorded resolution for 'notes.txt'.`, meaning that besides the conflict itself it also recorded your resolution. Now the experiment: I threw the merge away with `git reset --hard HEAD~1` and merged again:

```text
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Resolved 'notes.txt' using previous resolution.
Automatic merge failed; fix conflicts and then commit the result.
```

The third line says it applied the previous resolution. The file already had my answer and no markers. But note that `git status` still showed `UU notes.txt`: rerere fills in the file but does not stage it. You look at the result, run `git add` and commit. This is on purpose, because it wants you to read and confirm the result yourself.

What gets stored? For each conflict there is a directory in `.git/rr-cache` named by the hash of the conflict text. It holds two files: `preimage` (the conflict itself) and `postimage` (your resolution). While a conflict is open, `git rerere status` lists the files rerere is tracking, and `git rerere diff` shows how the current file differs from the recorded conflict. (Right after the conflict and before you resolve it, only the marker lines differ.)

If a recorded resolution was wrong, `git rerere forget notes.txt` deletes it. I tried this too, and Git printed `Forgot resolution for 'notes.txt'`.

Limits:

- **It works only when the conflict text is the same.** Changing a neighbouring line means a new conflict.
- **It is stored only in your clone.** Your teammates do not see your resolutions.
- **It records only content conflicts.**
- **I did not run `git mergetool` here.** That tool opens a graphical three-pane editor.

## Before committing a resolution

- **Never commit marker lines.** Before `git add`, search the file for `<<<<<<<`.
- **Run the tests after resolving.** A textually clean merge can still be wrong in meaning: each side is right alone but not together.
- **In the middle of a rebase, after resolving, run `git add` and then `git rebase --continue`.** Do not run `git commit` yourself.
- **In a rebase, do not trust "ours" and "theirs" without checking.** Their meaning is the opposite of a merge, as the table above shows.
- **Read what rerere produced before staging it.** It fills in the file but does not guarantee it is right.

## Exercise

Create a repository with two branches that change the same line. Merge and resolve it with zdiff3 enabled. Reset the merge, turn rerere on, resolve again, reset, and merge a third time. Look inside `.git/rr-cache`. Repeat the same with `git rebase` and see what `--ours` gives.

## What's next

Next is "Undoing work: reflog, revert and cherry-pick". If a resolution you made turns out to be bad, there we see the tools for undoing it.
