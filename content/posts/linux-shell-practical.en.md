+++
date = '2027-03-19T10:00:00+03:30'
draft = false
title = 'The practical shell: pipes, redirects and xargs'
description = 'Shell pipes, redirects and xargs with real runs: exit codes, pipefail, quoting pitfalls, find -print0 and process substitution, tested on macOS.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "shell", "bash", "pipes", "redirects", "xargs"]
cover = { image = "/images/covers/linux-shell-practical.png", alt = "The practical shell: pipes, redirects and xargs", hiddenInSingle = true }
+++

This is the first post of the Linux series, and it starts where I spend most of my day: the shell. Pipes, redirects and `xargs` turn small tools into one-off programs, and a few quoting rules decide whether they are safe. The same tools help when we debug sockets, as in [the TCP server post](/posts/net-sockets-tcp-from-scratch/).

> Honest disclaimer: I wrote this on **macOS**, which has a BSD userland and no Linux kernel. All output below is real macOS output (`/bin/sh`, and `/bin/bash` 3.2.57 for the bash parts). I did not run anything on Linux, and `shellcheck` is not installed here, so I did not run it. Where GNU differs I quote the man page or say so. Home paths were replaced by `<home>`.

## A log to play with

The demo log uses invented lines and documentation addresses (`203.0.113.x`, `198.51.100.x`). Each line is `client method path status`.

```sh
cut -d' ' -f1 access.log | sort | uniq -c | sort -rn | head -2
```
```
   4 203.0.113.7
   2 203.0.113.9
```

A {{< term "pipe" "pipe" >}} connects the output of one command to the input of the next, so each tool does one small job. `uniq` only collapses neighbours, which is why `sort` comes first.

## Redirects

Every process starts with three {{< term "file-descriptor" "file descriptors" >}}: 0 (stdin), 1 (stdout), 2 (stderr). Redirects rewire them.

```sh
echo one > out.txt; echo two >> out.txt    # > truncates, >> appends
ls nope 2> err.txt; echo "exit=$?"
ls nope out.txt > both.txt 2>&1            # stderr to wherever stdout goes
```
```
exit=1
ls: nope: No such file or directory
```

`both.txt` then held the error line and `out.txt`. Order matters: `2>&1` copies where stdout points *now*, so it must come after `> file`. The bash shortcut `&>` does the same (it ran under bash 3.2 here); it is not POSIX, so scripts for `/bin/sh` should use the long form.

A {{< term "here-document" "here-document" >}} feeds literal text to stdin. Unquoted, the shell expands variables inside it; with a quoted marker it does not. My run printed `literal $HOME` for the quoted `<<'EOT'`. The bash-only `<<<` passes a single string: `tr a-z A-Z <<< "hello"` printed `HELLO`.

## Exit codes, && and ||

Every command ends with an {{< term "exit-status" "exit status" >}}: 0 means success.

```sh
grep -q 404 access.log; echo "found=$?"      # found=0
grep -q 500 access.log; echo "notfound=$?"   # notfound=1
grep -q 500 access.log && echo yes || echo no   # no
```

`a && b` runs `b` only if `a` succeeded, `a || b` only if it failed. Command substitution captures output: `n=$(wc -l < access.log)` gave `lines:        8`. Those spaces are real: BSD `wc` pads its numbers. `tee` copies a stream to a file and onward: `... | tee status-counts.txt | wc -l` printed `3` and left the counts on disk.

## pipefail

A pipeline's status is normally the last command's, so a failure in the middle hides.

```sh
false | true; echo "default: $?"      # default: 0
set -o pipefail
false | true; echo "pipefail: $?"     # pipefail: 1
```

`set -e` aborts on the first failing command: in a subshell, `echo before; false; echo after` printed only `before` and exited 1. `set -u` makes an unset variable an error: `undefined_var: unbound variable`. `set -euo pipefail` is a decent bash header, but `-e` has known exceptions (for example inside `if` conditions), and I only tested `pipefail` in bash.

## Quoting

```sh
f="my report.txt"; touch "$f"
ls -1 $f
ls -1 "$f"
```
```
ls: my: No such file or directory
ls: report.txt: No such file or directory
my report.txt
```

Unquoted, the variable is split on spaces into two arguments. Quote every expansion unless you want splitting.

## xargs and names with spaces

{{< term "xargs" "`xargs`" >}} turns lines on stdin into arguments. With files named `a b.txt`, `c.txt`, `d e f.txt`:

```sh
find . -name '*.txt' | xargs ls -1
```
```
ls: ./a: No such file or directory
ls: ./d: No such file or directory
ls: b.txt: No such file or directory
...
```

The fix is NUL separators: `find . -name '*.txt' -print0 | xargs -0 ls -1` listed all three files correctly. Other forms I ran: `xargs -n 2 echo batch:` on `1..5` gave `batch: 1 2`, `batch: 3 4`, `batch: 5`; and `xargs -0 -I{} echo "file=[{}]"` ran once per file, spaces intact. The alternative `find . -name '*.txt' -exec echo {} +` batches arguments without xargs.

## Where Linux differs

- `find -printf` is not available here (`find: -printf: unknown primary or operator`). I did not run GNU find.
- `sed -i 's/x/y/' file` failed with `command c expects \ followed by text`, because BSD `sed` wants a suffix argument: `sed -i '' ...` worked. GNU `sed -i` takes the suffix attached, so portable scripts avoid `-i` or use a temp file.
- Empty input: per the macOS man page, GNU `xargs` runs the command once even with empty input and offers `-r` to stop that. Here `printf '' | xargs echo ran` printed nothing, and `-r` is accepted for compatibility.

## A few things to watch

- Quote `"$var"` and `"$@"` by default.
- Use `-print0`/`-0` for file names, never `find | xargs` bare.
- `2>&1` goes after the file redirect.
- Pipelines hide failures without `pipefail`; {{< term "process-substitution" "process substitution" >}} `<(cmd)` (bash/zsh, not POSIX) gives a command's output as a file name: `diff <(...) <(...)` exited 1 and showed `3d2`.
- Bash-isms (`&>`, `<<<`, `<()`) need `#!/bin/bash`.

## Exercise

Create `x y.log` and two more `.log` files. Count their lines with `find ... -print0 | xargs -0 wc -l`, then remove `-print0`/`-0` and read the error.

## What's next

The next post is “The filesystem and permissions”.
