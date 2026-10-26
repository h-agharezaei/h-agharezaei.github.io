+++
date = '2026-11-07T10:00:00+03:30'
draft = false
title = 'Undoing work: reflog, revert and cherry-pick'
description = 'Git undo with reflog, reset, revert and cherry-pick: what each command changes, how to recover from a hard reset, and what Git cannot bring back.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "reflog", "revert", "cherry-pick"]
cover = { image = "/images/covers/git-undo-reflog-revert.png", alt = "Undoing work: reflog, revert and cherry-pick", hiddenInSingle = true }
+++

In the [previous post](/posts/git-resolve-conflicts/) we resolved conflicts. Now the question every developer asks sooner or later: "I ran something and my work is gone. Can I get it back?" Most of the time you can, because Git rarely deletes anything right away. The trick is knowing which tool to reach for.

> Everything below was run with Git 2.39.2 in a throwaway repository, and the outputs are copied from those runs.

## reset: three levels

{{< term "git-reset" "git reset" >}} moves the current branch to another commit. What it does to the {{< term "staging-area" "index" >}} and the working tree depends on the mode. I made a commit `add line 4` and ran `git reset --<mode> HEAD~1` each time:

| Mode | Branch moves | Index | Working tree | `git status -s` after |
|---|---|---|---|---|
| `--soft` | yes | kept | kept | `M  notes.txt` (staged) |
| `--mixed` (default) | yes | reset | kept | ` M notes.txt` (unstaged) |
| `--hard` | yes | reset | reset | clean, `line 4` is gone from the file |

So `--soft` is "undo the commit, keep everything ready to commit again". `--hard` is the only one that throws away file contents.

## The "oops" and the {{< term "reflog" "reflog" >}}

```bash
git reset --hard HEAD~2
```

```text
HEAD is now at 2ff9b35 add line 3
```

Two commits vanished from `git log`. But Git keeps a local diary of where `HEAD` has been:

```bash
git reflog | head -3
```

```text
2ff9b35 HEAD@{0}: reset: moving to HEAD~2
aeaffd1 HEAD@{1}: commit: add line 5
486542d HEAD@{2}: commit: add line 4
```

`HEAD@{1}` is where we were one move ago. Go back there:

```bash
git reset --hard 'HEAD@{1}'
```

```text
HEAD is now at aeaffd1 add line 5
```

Both commits are back. The reflog is local to your clone and is never pushed.

## amend: fix the last commit

I committed `add line 6 tpyo` and fixed it with `git commit --amend -m "add line 6"`. The reflog shows what really happens: a new commit replaces the old one, and the old one stays reachable for a while.

```text
57b3951 HEAD@{0}: commit (amend): add line 6
c2eab17 HEAD@{1}: commit: add line 6 tpyo
```

Only amend commits you have not pushed, because it rewrites history.

## {{< term "git-revert" "revert" >}}: undo safely on shared branches

`git revert` does not rewrite anything. It adds a new commit that applies the opposite patch:

```text
6c01175 Revert "add b.txt (bug)"
7a8401b add c.txt
8d3aa62 add b.txt (bug)
84c3288 add a.txt
```

`b.txt` is gone, `c.txt` stays, and history is intact. This is what you want on a branch other people have pulled.

Reverting a {{< term "merge-commit" "merge commit" >}} needs one more hint, because Git must know which parent is the mainline:

```text
$ git revert --no-edit HEAD
error: commit 70591d9... is a merge but no -m option was given.
fatal: revert failed
$ git revert --no-edit -m 1 HEAD
[main 066c38f] Revert "Merge feature"
 1 file changed, 1 deletion(-)
 delete mode 100644 f.txt
```

`-m 1` means "keep the first parent", the branch you merged into.

## {{< term "cherry-pick" "cherry-pick" >}}: take one commit

I made a commit on a `hotfix` branch and copied it to `main`:

```bash
git cherry-pick -x 1e6057c
```

The copy has a new hash (`68d45b5`) because its parent differs, but the same patch. `git patch-id` proves it:

```text
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 1e6057c...   (original)
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 68d45b5...   (copy)
```

`-x` appends `(cherry picked from commit 1e6057c...)` to the message, which helps later when someone asks where a commit came from.

## What the reflog cannot save

I appended a line to `a.txt` without staging it, then ran `git restore a.txt`:

```text
 M a.txt          (before)
                  (after: clean, the line is gone)
```

The reflog has no record of that edit, because it was never committed. Git only remembers what it has stored. Untracked files and uncommitted changes are not protected, so commit or `git stash` before risky commands.

## Dangling commits and fsck

I deleted a branch with `git branch -D tmp` and expired the reflog. The commit still exists until garbage collection:

```bash
git fsck --lost-found
```

```text
dangling commit 0b1fb07a5e6289f46c88e2cd5ceaf064d9e01737
```

`git branch rescue 0b1fb07` brought it back. According to the docs, reflog entries expire after 90 days if reachable and 30 days if not (`gc.reflogExpire`, `gc.reflogExpireUnreachable`), and `git gc` may then delete the objects. I did not test that.

## A few things to watch

- Before `reset --hard`, run `git status`. Uncommitted work is not recoverable.
- Never amend or reset commits you already pushed; use `revert` there.
- If you panic, run `git reflog` first and change nothing.
- Always pass `-m 1` (or the right parent number) when reverting a merge commit; without it Git refuses.
- The reflog is per clone. A fresh clone has none.

## Exercise

In a temp repo make three commits, `git reset --hard HEAD~2`, then recover with the reflog. After that revert the middle commit and cherry-pick one commit from another branch with `-x`.

## What's next

The next post is "Finding a bug with git bisect".
