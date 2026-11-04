+++
date = '2027-05-05T10:00:00+03:30'
draft = false
title = 'The supply chain and vulnerable dependencies'
description = 'Software supply chain security with real runs in Go, npm and Python: go.sum, npm audit, lockfile hashes, install scripts and pip-audit.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "supply-chain", "dependencies", "go", "npm", "python"]
cover = { image = "/images/covers/sec-supply-chain-vulns.png", alt = "The supply chain and vulnerable dependencies", hiddenInSingle = true }
+++

Open the `go.mod` file of a small orders service and you will find a handful of lines. Run `go list -m all` and you will find more. Each of those extra modules is code that was written by a stranger, pulled in by a library you chose, and it runs inside your service with the same rights as your own code. You never read it. Probably nobody on your team did.

That is what people call the {{< term "software-supply-chain" "software supply chain" >}}: everything that ends up in your program but was not written by you, plus the tools and servers that deliver it. Most of it is a {{< term "transitive-dependency" "transitive dependency" >}}, a package you did not ask for directly but that something you did ask for needs. If you built the orders service from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), this is already true for it.

The previous post, [Managing secrets and keys](/posts/sec-secrets-management/), protected credentials that you own. This post is about code you do not own. The question is small and practical: when I run `go build`, `npm ci` or `pip install` tomorrow, how do I know I get the same bytes I got today, and how do I find out that some of those bytes have a known security bug? The background posts are [Packages and modules](/posts/go-packages-modules/), [npm, package.json and lockfiles](/posts/node-npm-package-json/) and [The Python environment: venv and uv](/posts/py-environment-uv-venv/).

> This post is defensive only. Everything ran in throwaway projects with private caches that I deleted afterwards, nothing was published, and no third party was touched. The npm advisory text and the pip-audit rows are from the original run on 2026-10-27. I re-ran the Go, npm and uv `--require-hashes` demos for this rewrite with Go 1.27.3, npm 10.5.2 and uv, and the output matched, except where I say otherwise.

## The core idea: pin, verify, scan

All three ecosystems below use the same three ideas, with different file names.

1. **Pin.** Write down exactly which version, and which bytes, you use. A version number alone is a promise; a hash of the file is a check.
2. **Verify.** Every time the code is fetched, compare it with what you wrote down, and fail loudly if it differs.
3. **Scan.** Separately, ask a database of known vulnerabilities whether any pinned version appears in it.

Pinning and verifying protect you from a package that silently changes under you. Scanning protects you from a package that was already bad when you pinned it. You need both, because they answer different questions.

## Go: pin, verify, tamper

I made a small module called `example.com/orders` with two deliberately old dependencies, `uuid v1.3.0` and `yaml.v2 v2.2.2`. First, what does Go think the module depends on?

```
$ go list -m all
example.com/orders
github.com/google/uuid v1.3.0
gopkg.in/check.v1 v0.0.0-20161208181325-20d25e280405
gopkg.in/yaml.v2 v2.2.2
$ go mod graph | wc -l
       5
$ go mod why -m gopkg.in/yaml.v2
example.com/orders
gopkg.in/yaml.v2
$ go mod verify
all modules verified
```

Line by line:

- `go list -m all` lists the main module and every module in the build. I wrote two requirements, but there are three dependencies: `gopkg.in/check.v1` came in on its own, because `yaml.v2` needs it. That is a transitive dependency in the flesh.
- `go mod graph | wc -l` counts the edges of the dependency graph. There are 5 (my module to its two dependencies, the Go version lines, and `yaml.v2` to `check.v1`).
- `go mod why -m` answers "why is this module here?" by printing a path from your code to it. Here `yaml.v2` is imported directly by `main.go`.
- `go mod verify` re-hashes the modules in the local module cache and compares them with `go.sum`. All good.

Where does the "pinning" live? In `go.sum`. It holds an `h1:` hash for every module version. The first time a module is added to a project, Go also compares that hash with a public log, the {{< term "checksum-database" "checksum database" >}} at `sum.golang.org`, so that everybody in the world gets the same bytes for the same version and a package author cannot hand different people different code. Never turn that check off to "fix" an error. One more Go detail: Go picks the lowest version that satisfies every `go.mod`, which is called minimal version selection. A new release of a dependency does not enter your build until you ask for it.

Now let me break it. I edited one file of `uuid` inside my private module cache, as if something on the machine had modified downloaded code:

```
$ go mod verify
github.com/google/uuid v1.3.0: dir has been modified (<tmp>/gomod/github.com/google/uuid@v1.3.0)
exit=1
```

The hash of the directory no longer matches `go.sum`, so `go mod verify` names the module, says what is wrong, and exits with status 1, which makes a CI job fail.

The second experiment is the other direction: the bytes on the network are fine, but `go.sum` is wrong. I changed the first characters of the `uuid` hash in `go.sum` and built again with an empty cache:

```
verifying github.com/google/uuid@v1.3.0: checksum mismatch
	downloaded: h1:t6JiXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=
	go.sum:     h1:AAAAXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=

SECURITY ERROR
This download does NOT match an earlier download recorded in go.sum.
```

(The full Go message continues with a line about the origin server and `go help module-auth`; I cut it here.) Go refuses to build. It does not matter who is "right", the file or the download: the point is that a difference is a stop sign, and a human has to look.

To find out whether versions are old, `go list -m -u all` printed `uuid v1.3.0 [v1.6.0]` and `yaml.v2 v2.2.2 [v2.4.0]`; the bracket is the newest available version. It also lists a newer pseudo-version for `check.v1`, which I do not show. Old does not mean vulnerable, though. For that you need the vulnerability scanner, `govulncheck`. The original run could not use it (`fetching vulnerabilities: ... vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden`). When I tried again for this rewrite, the `govulncheck` binary I had installed was built with an older Go than the one on my path and refused to load the packages. So there are still no Go findings to show. Run it in CI, where the vulnerability database is reachable and the tool is built with your toolchain.

## npm: audit, integrity, ci and scripts

For npm I pinned `minimist@1.2.0` exactly in `package.json`, an old version with known advisories, and ran `npm audit`:

```
minimist  1.0.0 - 1.2.5
Severity: critical
Prototype Pollution in minimist - https://github.com/advisories/GHSA-vh95-rmgr-6w4m
Prototype Pollution in minimist - https://github.com/advisories/GHSA-xvch-5gv4-984h
fix available via `npm audit fix --force`
Will install minimist@1.2.8, which is outside the stated dependency range
```

(I left out the header and the summary lines; the real report also prints `node_modules/minimist` and "1 critical severity vulnerability".) The first line says which versions are affected, `1.0.0 - 1.2.5`, and my `1.2.0` is inside that range. The two links are public advisories for {{< term "prototype-pollution" "prototype pollution" >}}, a class of bug where an attacker-controlled key such as `__proto__` changes the shared prototype of every object in the process. The last two lines are npm offering a fix, with a warning: the fix is outside the version range I wrote.

The audit tells you about a bug. The {{< term "lockfile" "lockfile" >}}, `package-lock.json`, is what stops a surprise. For each package it records the version, the exact URL it came from, and an `integrity` hash of the tarball:

```
"node_modules/minimist": {
  "version": "1.2.0",
  "resolved": "https://registry.npmjs.org/minimist/-/minimist-1.2.0.tgz",
  "integrity": "sha512-7Wl+Jz+IGWuSdgsQEJ4JunV0si/iMhg42MnQQG6h1R6TNeVenp4U9x5CC5v/gYqz/fENLQITAWXidNtVL0NNbw=="
}
```

`npm ci` installs exactly what the lockfile says, checks the integrity hashes, and refuses to continue when `package.json` and the lock disagree. To see that, I changed `package.json` to `1.2.8` without touching the lock:

```
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync. Please update your lock file with `npm install` before continuing.
npm ERR! Invalid: lock file's minimist@1.2.0 does not satisfy minimist@1.2.8
```

Use `npm ci` in CI, and `npm install` only on the day you mean to change dependencies. Otherwise "install" quietly rewrites the lock and your pinning is gone.

There is one more thing a package manager does that people forget: it can run code during installation. My own throwaway package had `"postinstall": "echo postinstall ran on this machine"` in its `package.json`. Installing it with the script output shown (`--foreground-scripts`) printed:

```
> hook-demo@1.0.0 postinstall
> echo postinstall ran on this machine

postinstall ran on this machine
```

The first two lines are npm announcing the script it is about to run, and the last one is the script's own output. With `--ignore-scripts` none of these lines appeared. Here it is a harmless `echo`, but the same hook could run any command with your rights, on your laptop or on your CI runner. So in CI, use `--ignore-scripts` unless a package really needs a build step.

## Python: audit and hashes

With `jinja2==2.11.2` pinned, `pip-audit` (version 2.9.0, in the original run) printed:

```
Found 5 known vulnerabilities in 1 package
jinja2 2.11.2  PYSEC-2021-66   2.11.3
jinja2 2.11.2  PYSEC-2026-1473 3.1.3
(three more rows, fixes 3.1.4 to 3.1.6)
```

Each row is: the package and my version, the advisory id, and the first version where it is fixed. The post shows two rows and summarises the other three as they were in the original run. I could not re-run `pip-audit` for this rewrite, because installing it did not finish before my time limit, so treat those rows as a snapshot of that day; advisory databases grow over time.

For pinning, `uv pip compile requirements.in --generate-hashes` writes `requirements.txt` with a `--hash=sha256:...` line for every downloadable file of every package. When you install with `--require-hashes`, pip or uv refuses any file whose hash is not in the list. To see it fail, I used a file where the hash for `markupsafe==1.1.1` is all zeros:

```
× Failed to download and build `markupsafe==1.1.1`
╰─▶ Hash mismatch for `markupsafe==1.1.1`
    Expected: sha256:0000...0000
    Computed: sha256:29872e92839765e546828bb7754a68c418d927cd064fd4708fab9fe9c8bb116b
```

`Expected` is what the file said, `Computed` is the hash of what was downloaded. (The real output prints the long hashes on separate lines; I put them on one line.) I re-ran this with `uv pip install --require-hashes`, and the computed hash was the same as in the original run.

## Concepts I did not run

These are part of the picture, but I did not demonstrate them, so I only describe them.

- {{< term "typosquatting" "Typosquatting" >}} is a malicious package with a name close to a popular one, hoping someone mistypes. A related trick, dependency confusion, is a public package whose name matches one of your internal packages. The defence is boring: look at new package names before adding them, and configure private registries so internal names never resolve to the public one.
- An {{< term "sbom" "SBOM" >}} (software bill of materials, in formats such as CycloneDX or SPDX) is a list of everything you ship. When a new vulnerability is announced, it lets you answer "are we affected?" by searching a file. I did not generate one.
- A GitHub Actions workflow that uses a movable tag can change under you. Pinning an action to a full commit SHA fixes that. Dependabot or Renovate can open pull requests that bump pinned versions. I ran neither.
- Reproducible builds mean the same source gives the same bytes, so someone else can check your binary. See also the CI/CD pipeline design post in the roadmap.

| Ecosystem | Pin | Verify | Scan |
|---|---|---|---|
| Go | `go.mod` + `go.sum` | `go mod verify` | `govulncheck` |
| npm | exact version + lockfile | `npm ci` | `npm audit` |
| Python | `--generate-hashes` | `--require-hashes` | `pip-audit` |

## What a scanner does not tell you

- A scanner reports known advisories only. No findings is not proof that the code is safe, only that nobody has filed an advisory yet.
- `npm audit fix --force` can jump a major version and break your app. Read what it will install before you accept.
- Updating blindly is also a risk. When the lockfile changes, review its diff the way you review code.
- The registry and the CI system are part of the chain too. A stolen publish token or CI token lets someone change what you ship, so protect them like any other secret (see the previous post).

## Exercise

Take one of your own services and run the scanner of its ecosystem. Then write a one-page policy: who updates dependencies, how often, and what finding blocks a release.

## What's next

The next post is "SSRF and unsafe deserialization". We stop looking at code you did not write and look at input you did not write: a URL a user hands to your server, and a blob of bytes your server turns back into objects.
