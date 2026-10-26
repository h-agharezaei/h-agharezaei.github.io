+++
date = '2026-10-28T10:00:00+03:30'
draft = false
title = 'How Git thinks: objects and hashes'
description = 'How Git stores data: blobs, trees and commits, content hashes, zlib-compressed loose objects, and a commit built by hand with plumbing commands.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "objects", "internals"]
cover = { image = "/images/covers/git-how-git-thinks.png", alt = "How Git thinks: objects and hashes", hiddenInSingle = true }
+++

Most of us learn Git as a list of commands and then get scared the first time a rebase goes wrong. This opens a ten-post Git series, and it starts at the bottom: how Git stores things. Once you know that, `commit`, `branch` and `rebase` stop being magic. The blog already has other series (Go, Rust, NATS JetStream), but this one is about the tool we all use every day.

> Everything below was run with git 2.39.2 in a throwaway repository. The outputs are copied from those runs. The author and date were pinned with environment variables so the hashes are reproducible.

## Content-addressed storage

Git is, at its core, a key-value store. The value is some content, and the key is a hash of that content (by default {{< term "sha-1" "SHA-1" >}}). Same content gives the same key, different content gives a different one:

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

Add `-w` and Git writes the content into `.git/objects`. Then you can ask what it is:

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

## A loose object is a compressed file

The object landed in a file whose name is the hash, split after the first two characters:

```text
.git/objects/ce/013625030ba8dba906f756967f9e9ca394464a
```

The file is zlib-compressed. Decompressing it with a tiny Python snippet shows the real format: a type, a space, the size, a NUL byte, then the content.

```bash
python3 -c "import zlib;print(repr(zlib.decompress(open('.git/objects/ce/013625030ba8dba906f756967f9e9ca394464a','rb').read())))"
```

```text
b'blob 6\x00hello\n'
```

The hash is computed over that whole thing, header included. Notice what is missing: no file name, no date. The content alone decides the key.

## Three kinds of object

A {{< term "git-object" "Git object" >}} is one of a few types, and three matter now:

- A {{< term "blob" "blob" >}} is file content, nothing else.
- A {{< term "git-tree" "tree" >}} is a directory: a list of names, modes and hashes pointing at blobs or other trees.
- A {{< term "commit" "commit" >}} points at one tree (the snapshot) plus its parents, author, committer and message.

## Building a commit by hand

The everyday commands (`add`, `commit`) are built from lower-level {{< term "plumbing" "plumbing" >}} commands. We can use only those. After putting `hello.txt` and `src/main.go` in the index:

```bash
git update-index --add hello.txt src/main.go
T=$(git write-tree)
git cat-file -p $T
```

```text
100644 blob ce013625030ba8dba906f756967f9e9ca394464a	hello.txt
040000 tree b9270df7070cc6a5e7dbdec610a7ce4f54c47b20	src
```

The tree id was `337d9a8`. Now a commit, and a branch that points to it:

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

A branch is just a file holding a commit hash. That is why creating one is instant. The index and `update-index` are the next post.

## History is a graph

I made a second commit on `main` with `-p $C1` as its parent, and a third on a branch `side` from the same parent:

```text
* 66ddd7b second commit
| * 8798212 side work
|/  
* c6c5da0 first commit
```

Each commit points to its parents, never the other way. Following those pointers gives a {{< term "dag" "DAG" >}}: a directed graph with no cycles. A merge commit is simply one with two parents.

## Why history is immutable

A commit contains its parent's hash, so changing anything upstream changes everything downstream. I built two commits with the same tree and message for the second one, then rebuilt the first with a different message:

```text
original:  A=5dbfa36  B=dc8cab0
rewritten: A=2cfd71a  B=23bdee6
```

`B` has the same content and message in both runs, yet its hash changed because its parent did. So "rewriting history" never edits anything. It creates new commits and moves a branch to them; the old ones stay in the object database until garbage collection. This is also why rebase changes every hash after the edit.

## SHA-1 and SHA-256

By default Git uses SHA-1 (40 hex characters). My git supports `git init --object-format=sha256`, and the same `hello\n` blob gets a 64-character id there:

```text
2cf8d83d9ee29543b34a87727421fdecb7e3f3a183d337639025de576db9ebb4
```

According to the Git docs, SHA-256 repositories are not interoperable with SHA-1 ones, so I would not rely on them for normal work yet. I did not test pushing or hosting.

## A few things to watch

- The hash covers the header and content, so the same bytes always mean the same object, on any machine.
- A commit stores a snapshot (a tree), not a diff. Diffs are computed when you ask.
- File names live in trees, not blobs, so two files with identical content share one blob.
- Branches and tags are just pointers to commits, which is why they are cheap.
- Do not edit `.git/objects` by hand outside a throwaway repo.

## Exercise

In a temp directory run `git init`, then create a blob with `git hash-object -w`, a tree with `git mktree` or the index, and a commit with `git commit-tree`. Point a branch at it with `git update-ref` and check `git log`. Then decompress one object with Python and find its header.

## What's next

Next is "The index and staging: Git's three areas", where we see what `git add` really does.
