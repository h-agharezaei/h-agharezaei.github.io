+++
date = '2027-03-19T10:00:00+03:30'
draft = false
title = 'The practical shell: pipes, redirects and xargs'
description = 'Shell pipes, redirects and xargs with real runs: exit codes, pipefail, quoting pitfalls, find -print0 and process substitution, tested on macOS.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "shell", "bash", "pipes", "redirects", "xargs"]
cover = { image = "/images/covers/linux-shell-practical.png", alt = "The practical shell: pipes, redirects and xargs", hiddenInSingle = true }
+++

Here is a small puzzle. You have a file called `my report.txt`, you store its name in a variable `f`, and you run `ls -1 $f`. It fails, and it fails *twice*, with two different error messages. Then you run `false | true` and the shell tells you everything went fine, even though `false` is a command whose only job is to fail.

Neither of these is a bug in the shell. They are rules, and most of us learned them by getting burned once. A shell command typed by hand and a shell script left to run unattended at night follow the same rules, but the script has nobody watching it. So I want to start the Linux series by going through these rules slowly: how data flows between commands, how success and failure are reported, and why a space in a file name can break a pipeline. The same tools help when we debug a server, as in [the TCP server post](/posts/net-sockets-tcp-from-scratch/).

> Honest disclaimer: I ran everything here on **macOS**, which has a BSD userland and no Linux kernel. All output below is real macOS output (`/bin/sh`, and `/bin/bash` 3.2.57 for the bash parts). I did not run anything on Linux, and `shellcheck` is not installed on this machine, so I did not run it. Where GNU tools behave differently I quote the man page or say that I did not check.

## A log to play with

We need some data to work on. The demo uses a small web-server access log with invented lines and the documentation addresses `203.0.113.x` and `198.51.100.x`. Each line has four fields separated by spaces: `client method path status`, for example `203.0.113.7 POST /login 401`.

Our first question is: which clients send the most requests?

```sh
cut -d' ' -f1 access.log | sort | uniq -c | sort -rn | head -2
```
```
   4 203.0.113.7
   2 203.0.113.9
```

This is one {{< term "pipe" "pipe" >}} of five commands. The `|` character connects the output of the command on its left to the input of the command on its right, so each tool does one small job:

- `cut -d' ' -f1` keeps only the first field (the client address).
- `sort` puts equal lines next to each other.
- `uniq -c` collapses neighbouring equal lines and puts a count in front of each.
- `sort -rn` sorts by that count, largest first.
- `head -2` keeps the first two lines.

The first `sort` is not decoration. `uniq` only merges lines that are *neighbours*, so without sorting first the same address could appear several times. The output reads: client `203.0.113.7` sent four requests and `203.0.113.9` sent two. The idea behind the whole post is already in this one line: small programs that read text and write text, glued together.

## Redirects

A pipe moves output from one command to another. A *redirect* moves it to or from a file. To understand it, we need one fact: every process starts with three open channels called {{< term "file-descriptor" "file descriptors" >}}, numbered 0, 1 and 2. They are **stdin** (0, where input comes from), **stdout** (1, where normal output goes) and **stderr** (2, where error messages go). By default all three are your terminal. A redirect simply points one of them somewhere else.

```sh
echo one > out.txt; echo two >> out.txt    # > truncates, >> appends
ls nope 2> err.txt; echo "exit=$?"; cat err.txt
ls nope out.txt > both.txt 2>&1; cat both.txt   # stderr to wherever stdout goes
```
```
exit=1
ls: nope: No such file or directory
ls: nope: No such file or directory
out.txt
```

Here is what happened, line by line:

1. `>` writes stdout to a file and empties the file first. `>>` appends instead. After the two `echo`s, `out.txt` holds `one` and `two`.
2. `ls nope 2> err.txt` lists a file that does not exist. The error message goes into the file instead of the screen. `echo "exit=$?"` prints `exit=1`: `$?` is the exit status of the previous command, and 1 means `ls` failed. Then `cat err.txt` shows the error that was caught in the file.
3. The last line lists both a missing file and an existing one. `> both.txt` sends the normal output (`out.txt`) to the file, and `2>&1` sends the error there too. So `cat both.txt` shows the error line and the name `out.txt`, and nothing was printed on the screen by `ls` itself.

The order of redirects matters. `2>&1` means "make stderr point to wherever stdout points *right now*". So it must come after `> file`. If you write `2>&1 > file`, stderr is attached to the terminal before stdout is moved to the file, and the errors stay on the screen. Bash has a shortcut, `&>`, that does the same as `> file 2>&1` (it worked under bash 3.2 here), but it is not POSIX, so a script run by `/bin/sh` should use the long form.

Two more ways to feed input. A {{< term "here-document" "here-document" >}} (`<<EOT ... EOT`) gives literal lines of text to a command's stdin. If the marker is unquoted, the shell expands variables inside the text. If the marker is quoted, as in `<<'EOT'`, it does not. In my run, the quoted form printed `literal $HOME` exactly as written, while the unquoted form with an unset variable printed `user is ` followed by nothing: the variable was expanded to an empty string. The bash-only `<<<` passes a single string as input: `tr a-z A-Z <<< "hello"` printed `HELLO`.

## Exit codes, && and ||

We have used `$?` twice already, so let me say plainly what it is. Every command, when it ends, hands back a number to the shell: its {{< term "exit-status" "exit status" >}}. By convention 0 means success and anything else means some kind of failure. Every automatic decision in a shell script is based on this number, not on the text a command prints.

```sh
grep -q 404 access.log; echo "found=$?"      # found=0
grep -q 500 access.log; echo "notfound=$?"   # notfound=1
grep -q 500 access.log && echo yes || echo no   # no
```

`grep -q` prints nothing; it only reports through its exit status whether the pattern was found. There is a `404` in the log, so the status is 0. There is no `500`, so the status is 1. In the third line, `a && b` means "run `b` only if `a` succeeded", and `a || b` means "run `b` only if `a` failed". The log has no `500`, so `echo yes` is skipped and `echo no` runs.

Two related tools came up in my run. *Command substitution*, `$(...)`, captures what a command prints so you can store it: `n=$(wc -l < access.log)` followed by `echo "lines: $n"` gave `lines:        8`. Those wide spaces are real: BSD `wc` pads its numbers, and the shell kept them. And `tee` copies a stream into a file while passing it on: `... | tee status-counts.txt | wc -l` left the status counts in the file and printed the number of lines, which is 3 (also padded, as `       3`).

## pipefail

Now back to the puzzle from the beginning. A pipeline has one exit status, and by default it is the status of the *last* command. A failure in the middle is silently lost.

```sh
false | true; echo "default: $?"      # default: 0
set -o pipefail
false | true; echo "pipefail: $?"     # pipefail: 1
```

`false` always fails and `true` always succeeds. By default the pipeline reports the last one, 0. After `set -o pipefail`, the pipeline reports failure if *any* command in it failed, so we get 1. Think of `curl ... | jq ... | sort`: without `pipefail`, a failed download looks like success as long as `sort` is happy.

Two more switches belong in the same family. `set -e` makes the script stop at the first failing command: in a subshell, `echo before; false; echo after` printed only `before` and the subshell exited with status 1. `set -u` makes an unset variable an error instead of an empty string: bash printed `undefined_var: unbound variable`. Putting `set -euo pipefail` at the top of a bash script is a common habit, and a decent one, but `-e` has documented exceptions (for example, it does not trigger inside the condition of an `if`), so it is a safety net and not a guarantee. I only tested `pipefail` in bash.

## Quoting

The first half of the puzzle is quoting. Here is the exact example:

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

The file `my report.txt` exists, but the first `ls` could not find it. The reason is that the shell does {{< term "word-splitting" "word splitting" >}}: after it replaces `$f` with its value, it cuts the result at every space. So `ls` received two arguments, `my` and `report.txt`, and complained about each one. That explains the two errors. With double quotes, the shell keeps the value as a single argument, and the third line shows `ls` finding the file. Quote every variable expansion unless you really want splitting.

## xargs and names with spaces

The same problem appears with `xargs`. This tool reads lines from stdin and turns them into *arguments* of another command, which is useful when a command does not read from stdin. {{< term "xargs" "`xargs`" >}} splits its input on whitespace by default, so file names with spaces break it in the same way. Take three files named `a b.txt`, `c.txt` and `d e f.txt`:

```sh
find . -name '*.txt' | xargs ls -1
```
```
ls: ./a: No such file or directory
ls: ./d: No such file or directory
ls: b.txt: No such file or directory
...
```

The names were cut at the spaces, and `ls` was asked about pieces that do not exist. (The real run printed five errors and the one intact name, `./c.txt`; I cut the output here, and the order depends on `find`.) The fix is to avoid whitespace as the separator. Files cannot have a NUL byte in their names, so `find` can print names separated by NUL and `xargs` can read them that way:

```sh
find . -name '*.txt' -print0 | xargs -0 ls -1
```

This listed all three files correctly. Other forms I ran: `xargs -n 2 echo batch:` on the numbers 1 to 5 printed `batch: 1 2`, `batch: 3 4` and `batch: 5` (at most two arguments per run), and `xargs -0 -I{} echo "file=[{}]"` ran the command once per file, replacing `{}` with the name, spaces intact. You can also skip `xargs` completely: `find . -name '*.txt' -exec echo {} +` makes `find` itself pass the names to the command in batches.

## Where Linux differs

Everything above ran on macOS, whose tools come from BSD. On a Linux server you will most likely meet the GNU versions of these tools, and the differences cause real surprises. This is what I saw on macOS; I did not run the GNU versions:

- `find -printf` is not available here (`find: -printf: unknown primary or operator`).
- `sed -i 's/x/y/' file` failed with `command c expects \ followed by text`, because BSD `sed` wants a suffix argument after `-i`; `sed -i '' ...` worked. GNU `sed -i` takes the suffix attached to the option, so a portable script avoids `-i` or uses a temporary file.
- Empty input: according to the macOS man page, GNU `xargs` runs the command once even if the input is empty, and offers `-r` to stop that. Here `printf '' | xargs echo ran` printed nothing, and the man page says `-r` is accepted only for compatibility.

## Common shell traps

- Quote `"$var"` and `"$@"` by default. An unquoted variable is split on spaces and expanded by globbing, so it breaks the day a file name has a space in it.
- For file names, use `-print0` with `-0`. A bare `find | xargs` works until the first name with a space.
- Put `2>&1` after the file redirect, not before. Otherwise the errors still go to the terminal.
- A pipeline hides failures without `pipefail`. Also useful: {{< term "process-substitution" "process substitution" >}}, `<(cmd)`, which gives the output of a command as if it were a file name (bash and zsh, not POSIX). In my run, `diff <(...) <(...)` compared two commands' outputs directly, exited with status 1 and showed `3d2`: the second line of the first list was missing from the second.
- Bash-only features (`&>`, `<<<`, `<()`) need `#!/bin/bash`. Under plain `sh` they are syntax errors; running my demo with `sh` instead of `bash` failed exactly at the `<(` line.

## Exercise

Create `x y.log` and two more `.log` files. Count their lines with `find ... -print0 | xargs -0 wc -l`. Then remove `-print0` and `-0` and read the error. Finally, try `false | true` with and without `set -o pipefail`.

## What's next

Next: “The filesystem and permissions”, because every script touches files, and the first thing that goes wrong with files is that someone is not allowed to read them.
