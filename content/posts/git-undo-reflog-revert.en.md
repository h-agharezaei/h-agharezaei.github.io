+++
date = '2026-11-07T10:00:00+03:30'
draft = false
title = 'Undoing work: reflog, revert and cherry-pick'
description = 'Git undo with reflog, reset, revert and cherry-pick: what each command changes, how to recover from a hard reset, and what Git cannot bring back.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "reflog", "revert", "cherry-pick"]
cover = { image = "/images/covers/git-undo-reflog-revert.png", alt = "Undoing work: reflog, revert and cherry-pick", hiddenInSingle = true }
+++

Imagine it is late, you are tired, and you type `git reset --hard HEAD~2`. Two commits vanish from `git log`. Every developer meets this moment sooner or later: "I ran one command and my work is gone. Can I get it back?"

The good news is that most of the time you can. Git rarely deletes anything right away. The exception is work that was never committed; I come back to that near the end. Everything else only depends on knowing which tool to reach for, whether the damage came from a reset or from a [conflict resolution](/posts/git-resolve-conflicts/) that went wrong. In this post we look at four tools: `reset`, which moves a branch; the reflog, which remembers where we have been; `revert`, which undoes a change safely; and `cherry-pick`, which takes one commit from somewhere else.

> Everything below was run with Git 2.39.2 in a throwaway repository, and the outputs are copied from those runs. Commit hashes belong to that run and will differ on your machine.

## reset: three levels

First, what does `reset` actually do? {{< term "git-reset" "git reset" >}} moves the current branch to another commit, for example two commits back. One question remains: what happens to your files and to the {{< term "staging-area" "index" >}} (the "queue for the next commit" from the [index post](/posts/git-index-staging/))? The answer depends on the option you pass.

To see it, I made a commit called `add line 4` that adds one line to `notes.txt`. Then I ran `git reset --<mode> HEAD~1` three times, once per option, putting the state back in between. Here is the result:

| Mode | Branch moves | Index | Working tree | `git status -s` after |
|---|---|---|---|---|
| `--soft` | yes | kept | kept | `M  notes.txt` (staged) |
| `--mixed` (default) | yes | reset | kept | ` M notes.txt` (unstaged) |
| `--hard` | yes | reset | reset | clean, `line 4` is gone from the file |

("Reset" means set to match the new commit. `git status -s` prints two letters per line: the first is the state of the index, the second is the state of the working tree.)

In plain words:

- `--soft` says "undo the commit, keep everything ready to commit again". The change is still staged.
- `--mixed`, the default, undoes the commit and keeps the change in the file, but it is no longer staged.
- `--hard` does not only move the branch; it also resets the files to that commit. It is the only one that throws away file contents, which is why it is the dangerous one.

## The "oops" and the {{< term "reflog" "reflog" >}}

Now the scary moment. In this repository I had commits up to `add line 5`, and I ran:

```bash
git reset --hard HEAD~2
```

```text
HEAD is now at 2ff9b35 add line 3
```

Two commits vanished from `git log`. But Git keeps a local diary, and it writes down every place `HEAD` has been. It is called the reflog. Each time you commit, switch branches or reset, a line is added:

```bash
git reflog | head -3
```

```text
2ff9b35 HEAD@{0}: reset: moving to HEAD~2
aeaffd1 HEAD@{1}: commit: add line 5
486542d HEAD@{2}: commit: add line 4
```

Read it from the top; the newest entry comes first. The first line is the reset we just did. The second says that one move before that, `HEAD` was on `aeaffd1`, which is `add line 5`. That is what `HEAD@{1}` means: "where we were one move ago". So to get back, we reset to that place again:

```bash
git reset --hard 'HEAD@{1}'
```

```text
HEAD is now at aeaffd1 add line 5
```

(I quoted the braces so the shell leaves them alone.) Both commits are back. This works because the reset only moved the branch pointer; the commits themselves were still in Git's database, and nobody was pointing at them. The reflog gives you the pointer back. Remember that the reflog is local to your clone and is never pushed.

## amend: fix the last commit

A more everyday case: you commit and then notice a typo in the message. `git commit --amend` fixes the last commit. I committed `add line 6 tpyo` and fixed it with `git commit --amend -m "add line 6"`. The reflog shows what really happened:

```text
57b3951 HEAD@{0}: commit (amend): add line 6
c2eab17 HEAD@{1}: commit: add line 6 tpyo
```

Amend does not edit the old commit. It creates a new one (`57b3951`) and moves the branch to it. The old one (`c2eab17`) stays reachable through the reflog for a while. Because this changes history, only amend commits you have not pushed.

## {{< term "git-revert" "revert" >}}: undo safely on shared branches

Now suppose the bad commit was already pushed and your teammates pulled it. Reset is wrong here, because it changes history that other people are building on. The right tool is `git revert`. It does not rewrite anything. It adds a new commit that applies the opposite of the bad commit's change.

In a test repository I made three commits: `add a.txt`, then `add b.txt (bug)`, then `add c.txt`. Then I reverted the second one. This is `git log --oneline`:

```text
6c01175 Revert "add b.txt (bug)"
7a8401b add c.txt
8d3aa62 add b.txt (bug)
84c3288 add a.txt
```

The top commit is the revert. `b.txt` is gone from the folder, `c.txt`, which came later, stays, and no old commit was touched. On a branch other people have pulled, this is exactly what you want.

Reverting a {{< term "merge-commit" "merge commit" >}} needs one more hint. A merge commit has two parents (two commits just before it), and Git cannot know which side the "undo" should be measured against. You have to say which one is the mainline:

```text
$ git revert --no-edit HEAD
error: commit 70591d9... is a merge but no -m option was given.
fatal: revert failed
$ git revert --no-edit -m 1 HEAD
[main 066c38f] Revert "Merge feature"
 1 file changed, 1 deletion(-)
 delete mode 100644 f.txt
```

The first time, Git refused and said why. The second time, with `-m 1`, it worked. `-m 1` means "treat the first parent as the mainline", that is, the branch you merged into. As a result `f.txt`, which had come from the `feature` branch, was removed.

## {{< term "cherry-pick" "cherry-pick" >}}: take one commit

Sometimes you do not want to undo anything; you want one particular commit from somewhere else. Say you made a small fix on a branch called `hotfix` and you need only that fix on `main`. That is what `cherry-pick` does. I brought the `hotfix` commit onto `main` like this:

```bash
git cherry-pick -x 1e6057c
```

The result is a new commit on `main` with a different hash (`68d45b5`). The hash differs because a commit's hash also depends on its parent, and the new commit has a different parent. The change it applies, though, is the same. `git patch-id` proves it; it makes a signature from the change itself, ignoring the parent:

```text
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 1e6057c...   (original)
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 68d45b5...   (copy)
```

Both signatures are the same. The `-x` option also appends `(cherry picked from commit 1e6057c...)` to the commit message. Later, when someone asks where this commit came from, the answer is right there.

## What the reflog cannot save

Now the limit of all this. I appended a line to `a.txt` without staging it, then ran `git restore a.txt`:

```text
 M a.txt          (before)
                  (after: clean, the line is gone)
```

The `M` in the first line means the file was modified. After `restore` the status is clean and the line is gone. The reflog has no record of that edit, because it was never committed. Git only remembers what it has stored. Untracked files and uncommitted changes are not protected, so commit or run `git stash` before risky commands.

## Dangling commits and fsck

One more case: you deleted a branch and the reflog no longer helps. I deleted a branch with `git branch -D tmp` and expired the reflog (threw its entries away). Now no name points to that branch's commit. But the commit still exists in the database until garbage collection, and `git fsck`, which looks for orphaned objects, can find it:

```bash
git fsck --lost-found
```

```text
dangling commit 0b1fb07a5e6289f46c88e2cd5ceaf064d9e01737
```

"Dangling" means a commit that no ref and no other commit leads to. I gave it a new name with `git branch rescue 0b1fb07` and it was back.

This does not last forever. According to the Git docs, reflog entries expire after 90 days if the commit is still reachable and after 30 days if not (`gc.reflogExpire` and `gc.reflogExpireUnreachable`), and `git gc` may then delete the objects. I did not test those time limits.

## Rules for recovery

- Before `reset --hard`, run `git status`. Uncommitted work is not recoverable.
- Never amend or reset commits you already pushed. Others may be building on them, so use `revert` there.
- If you panic, run `git reflog` first and change nothing. Just look and find the right place.
- Always pass `-m 1` (or the right parent number) when reverting a merge commit; without it Git refuses.
- The reflog is per clone. A fresh clone has none, and a teammate's reflog does not help you.
- According to the Git docs, after you revert a merge, merging the same branch again will not bring its changes back, because Git thinks they were already merged. I did not test this.

## Exercise

In a temp repo make three commits, run `git reset --hard HEAD~2`, then recover with the reflog. After that revert the middle commit and cherry-pick one commit from another branch with `-x`.

## What's next

The next post is "Finding a bug with git bisect": undoing a commit is easy, finding the one that broke things is the harder part.
