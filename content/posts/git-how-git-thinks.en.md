+++
date = '2026-10-28T10:00:00+03:30'
draft = false
title = 'How Git thinks: objects and hashes'
description = 'How Git stores data: blobs, trees and commits, content hashes, zlib-compressed loose objects, and a commit built by hand with plumbing commands.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "objects", "internals"]
cover = { image = "/images/covers/git-how-git-thinks.png", alt = "How Git thinks: objects and hashes", hiddenInSingle = true }
+++

Suppose you ask a colleague: "bring me `config.go` exactly as it was yesterday." How does Git find it? And why does a rebase give commits that look the same a different ID?

Most of us learn Git as a list of commands, and the first time a rebase goes wrong we get scared. But underneath those commands sits something very simple: a **key-value store**, a place where each value is saved under a key and read back with the same key. In Git the key is always a hash of the content itself. So the same content always gets the same key, and no commit ever changes once it is made. When you know these two sentences, `commit`, `branch` and `rebase` stop being magic. That is why this ten-post series starts here.

> Everything below was run with git 2.39.2 in a throwaway repository. The outputs are copied from those runs. I pinned the author and the date with environment variables so the commit hashes are reproducible. If you run it with your own name and time, commit hashes will differ; blob and tree hashes depend only on content, so they stay the same.

## Content-addressed storage

First, what does "a hash of the content" mean? A hash function takes any input and returns a fixed-length string that works like a fingerprint of that input. By default Git uses {{< term "sha-1" "SHA-1" >}}, whose output is 40 hex characters. The command `git hash-object` computes it for us. We run it three times, twice on `hello` and once on `hello!`:

```bash
echo 'hello'  | git hash-object --stdin
echo 'hello'  | git hash-object --stdin
echo 'hello!' | git hash-object --stdin
```

```text
ce013625030ba8dba906f756967f9e9ca394464a
ce013625030ba8dba906f756967f9e9ca394464a
4effa19f4f75f846c3229b9dbdbad14eff362f32
```

The first two lines are identical because the content was identical. The third, with one extra exclamation mark, is a completely different hash. So the hash is built from the content and depends on nothing else. Nothing has been stored yet; Git only computed the hash.

With the `-w` flag Git also writes the content into `.git/objects`. Then we can ask about it by its hash: `-t` gives the type, `-s` the size, and `-p` prints the content:

```bash
H=$(echo 'hello' | git hash-object -w --stdin)
git cat-file -t $H   # type
git cat-file -s $H   # size
git cat-file -p $H   # pretty-print
```

```text
blob
6
hello
```

The type is `blob` (I will explain that in a moment), the size is 6 bytes (five letters of `hello` and the newline that `echo` adds), and the content is `hello`.

## A loose object is a compressed file

Everything Git keeps is an **object**, and a freshly written object is an ordinary file on disk. The file name is the hash, except that the first two characters become a directory name and the rest is the file name:

```text
.git/objects/ce/013625030ba8dba906f756967f9e9ca394464a
```

(This spreads objects over several directories so they do not all sit in one.) Such a file is called a **loose object**. It is compressed with zlib, so a normal editor cannot read it. To see what is inside, I open it with a tiny Python snippet:

```bash
python3 -c "import zlib;print(repr(zlib.decompress(open('.git/objects/ce/013625030ba8dba906f756967f9e9ca394464a','rb').read())))"
```

```text
b'blob 6\x00hello\n'
```

This is the real format: the type (`blob`), a space, the size (`6`), a NUL byte (shown as `\x00`), and then the content (`hello\n`). The hash is computed over this whole string, header included. Notice what is missing: no file name and no date. Only the content decides the key. That is why two files with different names but the same content are one object in Git.

## Three kinds of object

We saw the type `blob`. Every {{< term "git-object" "Git object" >}} is one of a few types, and we need three for now:

- A **{{< term "blob" "blob" >}}** is just the content of one file, with no name and nothing else.
- A **{{< term "git-tree" "tree" >}}** is a directory: a list of names, modes and hashes, where each line points at a blob or at another tree. (The mode tells the kind of entry; for example `100644` is a normal file and `040000` is a directory.)
- A **{{< term "commit" "commit" >}}** points at one tree (a picture of the whole project at one moment, a snapshot), and also holds its parent or parents, the author, the committer and the message.

So a commit is really a small chain: the commit points at the root tree, that tree points at blobs and at the trees of subdirectories, and everything is linked by hashes.

## Building a commit by hand

The best way to believe this structure is to build a commit ourselves, without `git add` and `git commit`. The everyday commands are built from lower-level commands called **{{< term "plumbing" "plumbing" >}}**, and we will use only those. Say we have two files, `hello.txt` and `src/main.go`. First we put them in the index (the place the next commit is built from; the next post is about it). Then `git write-tree` writes a tree from the index:

```bash
git update-index --add hello.txt src/main.go
T=$(git write-tree)
git cat-file -p $T
```

```text
100644 blob ce013625030ba8dba906f756967f9e9ca394464a	hello.txt
040000 tree b9270df7070cc6a5e7dbdec610a7ce4f54c47b20	src
```

There is one line for each entry of the root directory. `hello.txt` is a blob, and its hash is the same `ce0136…` we saw before, because its content is the same `hello`. `src` is another tree, which means it has its own list with `main.go` in it. The id of this root tree was `337d9a8…`.

Now `git commit-tree` makes a commit pointing at this tree, and `git update-ref` attaches the name `main` to it:

```bash
C1=$(echo 'first commit' | git commit-tree $T)
git update-ref refs/heads/main $C1
git cat-file -p $C1
git log --oneline
```

```text
tree 337d9a8168ca5a97d9d3d9e24a6fe18e4a5cf75c
author Roham <roham@example.com> 1793169000 +0330
committer Roham <roham@example.com> 1793169000 +0330

first commit
c6c5da0 first commit
```

The first part of the output is the commit itself. Its first line is `tree`, the snapshot. Then come the author and committer with a time (seconds since 1970, plus the time zone offset), and after a blank line, the message. There is no `parent` line because this is the first commit. The last line comes from `git log --oneline`: the short hash of the commit and its message.

The key point is that the branch in this example was just a small file with a commit hash written in it. That is why creating a branch is instant. How that works is the topic of the third post in this series.

## History is a graph

Let us add more commits to see the shape of the history. I made a second commit on `main` with `-p $C1` as its parent, and a third commit on a branch called `side` that also grows from the first one. `git log --graph --oneline --all` draws it:

```text
* 66ddd7b second commit
| * 8798212 side work
|/  
* c6c5da0 first commit
```

Each `*` is a commit. Both top commits grow from `first commit`, so the history splits into two lines at that point.

Each commit points to its parents, never the other way. So from any commit you can walk backwards, but an old commit knows nothing about the ones after it. Following these pointers gives a {{< term "dag" "DAG" >}}, a directed graph with no cycles. Directed because every pointer has a direction (child to parent), and no cycles because walking to parents never brings us back to where we started. A merge commit is nothing special: it is a commit with two parents instead of one.

## Why history is immutable

Now we can return to the first question: why do IDs change after a rebase? Every commit contains the hash of its parent, and the commit's hash is computed over all of its content. So if something upstream changes, that commit's hash changes; its child contains that hash, so the child's hash changes too, and so on to the end.

To see it, I made two commits, `A` and then `B` whose parent is `A`. Then I did it again, except that this time I changed the message of `A` from `first` to `first!`. I kept the tree and the message of `B` the same:

```text
original:  A=5dbfa36  B=dc8cab0
rewritten: A=2cfd71a  B=23bdee6
```

The hash of `A` changed, which we expected. But the hash of `B` changed too, even though its tree and message are exactly the same. The only difference is that its parent is a different `A`. So "rewriting history" in Git never edits anything. It creates new commits and moves the branch to them. The old commits stay in the object database until Git later cleans up unused objects. This is also why a rebase changes the hash of every commit after the edited point.

## SHA-1 and SHA-256

By default Git uses SHA-1, with 40 hex characters. My Git also has the option `git init --object-format=sha256`, and there the same `hello\n` blob gets a 64-character id:

```text
2cf8d83d9ee29543b34a87727421fdecb7e3f3a183d337639025de576db9ebb4
```

According to the Git docs, SHA-256 repositories are not interoperable with SHA-1 ones. So I do not rely on them for normal work yet. I did not test pushing or hosting such a repository.

## What this model implies

This model has several practical consequences that we will meet again and again:

- **The hash covers the header and the content together.** So the same bytes always mean the same object, on any machine.
- **A commit stores a snapshot, not a diff.** That is a full tree. When you run `git diff` or `git show`, Git computes the difference at that moment.
- **File names live in trees, not in blobs.** So two files with identical content share one blob.
- **Branches and tags are just pointers to commits.** That is why they are cheap.
- **Do not edit `.git/objects` by hand outside a throwaway repository.** Git manages that directory, and touching it can corrupt the repository.

## Exercise

In a temp directory run `git init`. Create a blob with `git hash-object -w`, a tree with `git mktree` or through the index, and a commit with `git commit-tree`. Point a branch at it with `git update-ref` and check `git log`. Then decompress one of the objects with Python and find its header.

## What's next

Next is "The index and staging: Git's three areas". In this post we used the index once without explaining it; there we see what `git add` really does.
