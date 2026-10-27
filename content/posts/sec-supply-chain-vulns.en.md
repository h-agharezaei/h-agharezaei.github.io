+++
date = '2027-05-05T10:00:00+03:30'
draft = false
title = 'The supply chain and vulnerable dependencies'
description = 'Software supply chain security with real runs in Go, npm and Python: go.sum, npm audit, lockfile hashes, install scripts and pip-audit.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "supply-chain", "dependencies", "go", "npm", "python"]
cover = { image = "/images/covers/sec-supply-chain-vulns.png", alt = "The supply chain and vulnerable dependencies", hiddenInSingle = true }
+++

The previous post, [Managing secrets and keys](/posts/sec-secrets-management/), kept your own credentials safe. This one is about code you did not write. Most of what an orders service runs, like the one in [Building an API with net/http in Go](/posts/go-http-api-stdlib/), is a {{< term "transitive-dependency" "transitive dependency" >}} you never read. That is the {{< term "software-supply-chain" "software supply chain" >}}. Background: [Packages and modules](/posts/go-packages-modules/), [npm, package.json and lockfiles](/posts/node-npm-package-json/) and [The Python environment: venv and uv](/posts/py-environment-uv-venv/).

> Defensive only. Everything ran in throwaway projects with private caches, which I deleted afterwards. No exploit details and nothing against third parties. Advisory output is as returned on 2026-10-27.

## Go: pin, verify, tamper

A module with two deliberately old dependencies (`uuid v1.3.0`, `yaml.v2 v2.2.2`):

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

`go.sum` holds an `h1:` hash for each module version. The first time you add one, Go also checks that hash against the {{< term "checksum-database" "checksum database" >}} at `sum.golang.org`, so everybody gets the same bytes. Never turn that off to "fix" an error. Go uses minimal version selection: it picks the lowest version that satisfies every `go.mod`, so upgrades happen only when you ask.

Then I edited one file in my private module cache:

```
$ go mod verify
github.com/google/uuid v1.3.0: dir has been modified (<tmp>/gomod/github.com/google/uuid@v1.3.0)
exit=1
```

I also corrupted a hash in `go.sum` and rebuilt from a clean cache:

```
verifying github.com/google/uuid@v1.3.0: checksum mismatch
	downloaded: h1:t6JiXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=
	go.sum:     h1:AAAAXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=

SECURITY ERROR
This download does NOT match an earlier download recorded in go.sum.
```

Outdated check: `go list -m -u all` shows `uuid v1.3.0 [v1.6.0]` and `yaml.v2 v2.2.2 [v2.4.0]`. I tried `govulncheck` (v1.9.0) and it failed here: `fetching vulnerabilities: ... vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden`. So I have no Go findings to show. Run it in CI where the database is reachable.

## npm: audit, integrity, ci, scripts

I pinned `minimist@1.2.0` exactly. `npm audit` reported:

```
minimist  1.0.0 - 1.2.5
Severity: critical
Prototype Pollution in minimist - https://github.com/advisories/GHSA-vh95-rmgr-6w4m
Prototype Pollution in minimist - https://github.com/advisories/GHSA-xvch-5gv4-984h
fix available via `npm audit fix --force`
Will install minimist@1.2.8, which is outside the stated dependency range
```

See {{< term "prototype-pollution" "prototype pollution" >}} for the class of bug. The {{< term "lockfile" "lockfile" >}} records where each package came from and its hash:

```
"node_modules/minimist": {
  "version": "1.2.0",
  "resolved": "https://registry.npmjs.org/minimist/-/minimist-1.2.0.tgz",
  "integrity": "sha512-7Wl+Jz+IGWuSdgsQEJ4JunV0si/iMhg42MnQQG6h1R6TNeVenp4U9x5CC5v/gYqz/fENLQITAWXidNtVL0NNbw=="
}
```

`npm ci` installs exactly the lockfile and refuses drift. I changed `package.json` to `1.2.8` without updating the lock:

```
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync.
npm ERR! Invalid: lock file's minimist@1.2.0 does not satisfy minimist@1.2.8
```

Use `npm ci` in CI; use `npm install` only to change dependencies on purpose.

Install-time code also runs. My own package had `"postinstall": "echo postinstall ran on this machine"`. Installing its tarball with `--foreground-scripts`:

```
> hook-demo@1.0.0 postinstall
> echo postinstall ran on this machine
```

With `--ignore-scripts` the line did not appear. A harmless echo here, but it could be any command, so use `--ignore-scripts` in CI unless a package truly needs a build step.

## Python: audit and hashes

With `jinja2==2.11.2` pinned, `pip-audit 2.9.0` printed:

```
Found 5 known vulnerabilities in 1 package
jinja2 2.11.2  PYSEC-2021-66   2.11.3
jinja2 2.11.2  PYSEC-2026-1473 3.1.3
(three more rows, fixes 3.1.4 to 3.1.6)
```

`uv pip compile requirements.in --generate-hashes` writes a `--hash=sha256:...` line for every file of every package. The installs used `--require-hashes`; with a deliberately zeroed hash for `markupsafe==1.1.1`:

```
× Failed to download and build `markupsafe==1.1.1`
╰─▶ Hash mismatch for `markupsafe==1.1.1`
    Expected: sha256:0000...0000
    Computed: sha256:29872e92839765e546828bb7754a68c418d927cd064fd4708fab9fe9c8bb116b
```

## Concepts I did not run

- {{< term "typosquatting" "Typosquatting" >}}: a malicious package named like a popular one. Dependency confusion: a public package that shadows an internal name. Review new names and scope private registries.
- {{< term "sbom" "SBOM" >}} (CycloneDX, SPDX): a list of what you ship. I did not generate one.
- Pin GitHub Actions to a full commit SHA, not a movable tag. Dependabot or Renovate open update pull requests. Neither was run.
- Reproducible builds: the same source gives the same bytes. Related: the planned CI/CD pipeline design post.

| Ecosystem | Pin | Verify | Scan |
|---|---|---|---|
| Go | `go.mod` + `go.sum` | `go mod verify` | `govulncheck` |
| npm | exact + lockfile | `npm ci` | `npm audit` |
| Python | `--generate-hashes` | `--require-hashes` | `pip-audit` |

## A few things to watch

- A scanner shows known advisories only; no findings is not proof of safety.
- `npm audit fix --force` can cross a major version. Read before applying.
- Updating blindly is a risk too: review lockfile diffs.
- The registry and CI are part of the chain too: protect their tokens (see the secrets post).

## Exercise

Take one of your services, run its ecosystem's scanner, and write a one-page policy: who updates, how often, and what blocks a release.

## What's next

The next post is SSRF and unsafe deserialization.
