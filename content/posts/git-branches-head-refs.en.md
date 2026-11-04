+++
date = '2026-11-01T10:00:00+03:30'
draft = false
title = 'Branches, HEAD and refs: just pointers'
description = 'Git branches explained: a branch is a 41-byte file, HEAD is a pointer, tags and remote-tracking branches are refs. Real runs, detached HEAD and recovery.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "branches", "refs", "head"]
cover = { image = "/images/covers/git-branches-head-refs.png", alt = "Branches, HEAD and refs: just pointers", hiddenInSingle = true }
+++

Open the file `.git/refs/heads/main`. All you see is 40 hex characters and a newline. That is it; that is the whole branch.

A branch feels heavy, because we say "go to the branch", "copy the branch", "merge the branch", and it sounds like each branch is a separate version of the project. But in Git a {{< term "git-branch" "branch" >}} is only a name that points at a {{< term "commit" "commit" >}}. That is why creating one costs nothing and a deleted branch can usually be brought back. The [previous post](/posts/git-index-staging/) followed a change from the working tree and the index to a commit; this post asks what the commits themselves hang from, and how Git knows where you are standing right now.

> Everything below was run with Git 2.39.2 in a temporary directory. The commit ids belong to that run and will differ on your machine.

## A branch is a file

To start, I have a repository with two commits. First the list of commits, then the content of the branch file, then the byte count of that file:

```text
$ git log --oneline
33cf254 second
7d52f5a first
$ cat .git/refs/heads/main
33cf25487ec218f465e614aa03dfb60f2827492f
$ wc -c < .git/refs/heads/main
      41
```

The content of the `main` file is the full hash of the last commit (`33cf254…`, which `git log` shows shortened). The 41 bytes are 40 hex characters plus a newline. That is the whole branch. Every time you commit on `main`, Git just writes a new id into this file.

A name that points to an object like this is called a {{< term "git-ref" "ref" >}} (short for reference). Branches live in `refs/heads/`, and we will see that tags and other things are refs too.

## HEAD says where you are

If a branch is only a name, how does Git know which name you are working on, and where to add the next commit? The answer is another file:

```text
$ cat .git/HEAD
ref: refs/heads/main
$ git symbolic-ref HEAD
refs/heads/main
```

{{< term "head" "HEAD" >}} is a file too. Usually, instead of a commit id, it holds the name of a branch (this is called a **symbolic ref**, a ref that points to another ref). So "the current branch" means "the branch HEAD names". When you commit, Git reads HEAD to see which branch it points to and writes the new commit id into that branch's file. The command `git symbolic-ref HEAD` shows the same thing without opening the file.

## Creating a branch means writing a file

Now that we know what a branch is, creating one should be very simple. I tried two ways: the normal `git branch feature`, and the low-level `git update-ref`, which writes a ref directly.

```text
$ git branch feature
$ cat .git/refs/heads/feature
33cf25487ec218f465e614aa03dfb60f2827492f
$ git update-ref refs/heads/other HEAD
$ git branch
  feature
* main
  other
```

The `feature` file has the same hash as `main`, and `git branch` lists both next to `main` (the star marks the one HEAD points to now). Both commands give the same result. Nothing is copied, no files and no history; only 41 bytes are written. That is why a branch is free.

`git switch -c work` both creates a branch and moves HEAD to it. After that I made a commit on `work` and ran `git branch -vv` (the verbose form):

```text
$ git switch -c work
Switched to a new branch 'work'
$ cat .git/HEAD
ref: refs/heads/work
$ git branch -vv
  feature 33cf254 second
  main    33cf254 second
  other   33cf254 second
* work    b9cdb9f third on work
```

The HEAD file now says `refs/heads/work`. Three branches still point at `second` and only `work` moved one commit ahead, because the new commit id was written into the `work` file and the others were not touched.

## Fast-forward

So the new commit is on `work` and `main` is behind. I went back to `main` and merged `work` into it:

```text
$ git switch main
Switched to branch 'main'
$ git merge work
Updating 33cf254..b9cdb9f
Fast-forward
 a.txt | 1 +
 1 file changed, 1 insertion(+)
```

The line `Updating 33cf254..b9cdb9f` says `main` moves from `33cf254` to `b9cdb9f`. Since `main` had nothing that `work` lacked, Git did not need to tie two histories together; it just moved the `main` pointer forward. This is a {{< term "fast-forward" "fast-forward" >}}, and no merge commit was made. If we run `git log --oneline --graph --all`, we see a straight line: `third on work`, `second`, `first`. The next post is about the case where both sides have new commits and a fast-forward is not possible.

## Detached HEAD and getting a commit back

We said HEAD usually holds a branch name. If instead it holds a commit id directly, you are in a {{< term "detached-head" "detached HEAD" >}} state (HEAD is detached from every branch):

```text
$ git switch -q --detach HEAD~1
$ cat .git/HEAD
33cf25487ec218f465e614aa03dfb60f2827492f
```

`HEAD~1` means one commit before HEAD. The HEAD file no longer has `ref: …`; it is a bare hash. A commit made here is not added to any branch. To try it, I made a commit called "experiment" and then went back to `main`. Git warned:

```text
$ git switch main
Warning: you are leaving 1 commit behind, not connected to
any of your branches:

  936605f experiment

If you want to keep it by creating a new branch, this may be a good time
to do so with:

 git branch <new-branch-name> 936605f

Switched to branch 'main'
```

Git says you are leaving behind a commit that no branch is attached to, and it even gives you the command to keep it. If we had not read the warning, the commit would look lost to us. But the {{< term "reflog" "reflog" >}} (a notebook Git keeps of where HEAD has been) remembers it:

```text
$ git reflog -3
b9cdb9f HEAD@{0}: checkout: moving from 936605f9f7b2665e474a43782d150fd05721086d to main
936605f HEAD@{1}: commit: experiment
33cf254 HEAD@{2}: checkout: moving from main to HEAD~1
$ git branch rescue HEAD@{1}
$ git log --oneline -2 rescue
936605f experiment
33cf254 second
```

The lines go from newest to oldest. `HEAD@{2}` is when we moved to `HEAD~1`, `HEAD@{1}` is the "experiment" commit itself, and `HEAD@{0}` is the return to `main`. With `git branch rescue HEAD@{1}` we gave that commit a new ref, so now `rescue` holds it; `git log` shows the commit is back in place.

One new ref is enough to make the commit reachable again. But according to the Git docs, commits that no ref reaches are eventually removed by garbage collection, so do this soon.

## Tags are refs too

A tag, like a branch, is a name for an object. I made two tags, one with `git tag v1` and one with `git tag -a v2 -m "release two"`:

```text
$ cat .git/refs/tags/v1
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
$ cat .git/refs/tags/v2
676128add498eaa876a334d3006c831472d72d40
$ git cat-file -t v1
commit
$ git cat-file -t v2
tag
$ git rev-parse v2^{commit}
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
```

The `v1` file directly holds a commit hash (`b9cdb9f…`), and `git cat-file -t` says its type is `commit`. This is a lightweight tag: just a ref to a commit, exactly like a branch. The `v2` file has a different hash and its type is `tag`. This is an {{< term "annotated-tag" "annotated tag" >}}: a separate {{< term "git-object" "object" >}} that itself points at the commit and also keeps a message and information about who made it. The last command, `v2^{commit}`, follows the tag to the commit and gives the same `b9cdb9f…`.

The main difference from a branch: a tag does not move when you commit. A branch moves forward with every commit, but a tag stays where you put it.

## Remote-tracking branches

So far everything was local. What refs do we have when we work with a remote? Next to the demo I made a bare repository (one with no working tree), added it as `origin`, and pushed `main`. A second clone then pushed a branch called `topic` to it. The remote here was a directory on the same disk, so no network was involved.

```text
$ git push -u origin main
To ../remote.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
$ git fetch
From ../remote
 * [new branch]      topic      -> origin/topic
$ git branch -r
  origin/main
  origin/topic
$ cat .git/refs/remotes/origin/main
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
```

After the push, `origin/main` exists; after `git fetch` (which downloads the remote's new refs) `origin/topic` appeared too. `git branch -r` lists them, and the `origin/main` file in `.git/refs/remotes/` is an ordinary hash.

`origin/main` is a {{< term "remote-tracking-branch" "remote-tracking branch" >}}: a local ref that records where `main` was on the remote the last time we talked to it. Only `fetch` and `push` move it, not your own commits. `git for-each-ref` lists all refs in one place:

```text
$ git for-each-ref --format='%(refname)  %(objectname:short)'
refs/heads/feature  33cf254
refs/heads/main  b9cdb9f
refs/heads/other  33cf254
refs/heads/rescue  936605f
refs/heads/work  b9cdb9f
refs/remotes/origin/main  b9cdb9f
refs/tags/v1  b9cdb9f
refs/tags/v2  676128a
```

(This list was taken before the `git fetch`, so `origin/topic` is not in it.) They are all the same thing: a name and a hash. Only the directory differs: `heads` for local branches, `tags` for tags and `remotes` for remote-tracking branches.

## Deleting a branch

Last, what does deleting a branch do? I made a branch called `wip` with a commit that exists nowhere else, and went back to `main`:

```text
$ git branch -d wip
error: The branch 'wip' is not fully merged.
If you are sure you want to delete it, run 'git branch -D wip'.
$ git branch -D wip
Deleted branch wip (was 75edf86).
```

`-d` refuses, because deleting this pointer would leave the commit without an owner, and Git sees that the commit is not yet merged into the current branch. `-D` forces it. The id it prints (`75edf86`) is your way back: `git branch wip 75edf86` recreates the pointer. (This id also belongs to that run.)

## Where pointers bite

- **Deleting a branch deletes a pointer, not commits.** But commits nobody points at do not stay forever; garbage collection eventually removes them.
- **Do not commit in a detached HEAD without giving the work a branch name.** Once you move away, your commits have no owner and only the reflog remembers them.
- **`origin/main` can be stale.** It is a local ref that only `fetch` updates; run `git fetch` before judging it.
- **Do not edit files in `.git/refs/` by hand in a real repository.** We read them to understand; to change them use `git branch` or `git update-ref`.

## Exercise

In a fresh repository make three commits. Create a branch on the first commit with `git branch old HEAD~2` and read the file that was created. Then switch to `old`, force-delete `main` with `git branch -D main`, and get it back using only the id Git printed, or the reflog.

## What's next

Next is "Merge or rebase? Two real histories". Here we saw only a fast-forward; there both branches have new commits and Git has to decide how to join them.
