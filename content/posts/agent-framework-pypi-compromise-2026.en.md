+++
date = '2026-11-19T10:00:00+03:30'
draft = false
title = "Microsoft's agent-framework Package Compromised on PyPI to Steal Cloud Credentials"
seoTitle = 'Compromised agent-framework on PyPI: What to Do'
description = 'Compromised agent-framework on PyPI (1.26.1 and 1.26.2) stole cloud credentials through a .pth file: who is affected, how it works, what to do.'
contentType = 'analysis'
categories = ["Security"]
tags = ["pypi", "python", "supply-chain", "azure", "ci-cd", "security"]
keywords = ["agent-framework", "Microsoft Agent Framework", "PyPI compromise", "malicious PyPI package", ".pth file", "Python supply chain attack", "Azure credentials theft", "GitHub Actions OIDC"]
cover = { image = "/images/agent-framework-cover.png", alt = "agent-framework PyPI package compromised, malicious versions 1.26.1 and 1.26.2, supply chain attack of November 17, 2026", hiddenInSingle = true }
+++

Imagine you never import a package, never call it, never even run the script that uses it. You only run `pip` to install something else. And a credential stealer runs anyway.

That is what the compromised `agent-framework` release on {{< term "pypi" "PyPI" >}} did on 17 November 2026. It is the meta-package of Microsoft Agent Framework, an open-source Python framework for building AI agents. According to [The Hacker News](https://thehackernews.com/2026/11/attackers-compromise-microsofts-agent.html), two malicious versions, 1.26.1 and 1.26.2, were published 33 minutes apart and were later quarantined. The article gives the package about 190,000 downloads a month.

This is a {{< term "software-supply-chain" "software supply chain" >}} attack: nobody broke into your code, they changed a package you trust. If you want the general picture of why this class of attack works, read [the supply chain post](/posts/sec-supply-chain-vulns/) first. Here I look at this one incident.

Everything below comes from that single article and the vendor reports it links. I did not download the malicious packages and I did not run the malware. The one thing I ran myself is a harmless demo of the Python feature the attack relies on, described below.

## What happened

The facts, as the article reports them:

- **Affected versions:** 1.26.1 and 1.26.2 of `agent-framework`. The article calls 1.26.0 "the most recent safe version". It names no fixed release, only the advice to pin to 1.26.0.
- **Exposure window:** between 8:35 and roughly 9:20 p.m. UTC on 17 November 2026.
- **Identifiers:** there is no CVE and no CVSS score. This is a malicious package, not a bug in the framework's code.
- **Attacker:** not named. The article mentions the group TeamPCP only as the group behind a May 2026 compromise of another Microsoft package, `durabletask`. It does not attribute this incident to them.
- **Root cause:** unknown. The article says it is unclear how the attacker got publishing access. OX Security's view, quoted there, is that the attackers appear to have hijacked the wheel creation flow to add malicious logic, instead of publishing an obviously separate package.

## Why it ran without being imported

The two malicious {{< term "wheel" "wheels" >}} each add one extra file to `site-packages`: a {{< term "pth-file" ".pth file" >}}. Version 1.26.1 adds `agent_framework_meta.pth`, version 1.26.2 adds `af_runtime_diag.pth` plus a new module `af_runtime_diag.py`.

A `.pth` file was designed to add directories to Python's import path. The [Python documentation](https://docs.python.org/3/library/site.html) says that a line in it that starts with `import` is executed. That is the whole trick: one line, `import agent_framework_meta`, and the payload module runs every time Python starts. Endor Labs, quoted in the article, says it runs on any Python launch, "including pip itself, whether or not anything imports Agent Framework."

To check that this really works the way I describe, I made a throwaway virtual environment, dropped a harmless `.pth` file in it that only prints one line, and started Python in several ways. The paths are replaced with `<tmp>`.

```text
$ cat <tmp>/venv/lib/python3.14/site-packages/demo_hook.pth
import sys; print("[demo.pth] ran at startup, argv =", sys.argv)

$ venv/bin/python -c "print(1+1)"
[demo.pth] ran at startup, argv = ['-c']
[demo.pth] ran at startup, argv = ['-c']
2

$ venv/bin/python -S -c "print(1+1)"
2

$ venv/bin/python -I -c "print(1+1)"
[demo.pth] ran at startup, argv = ['-c']
[demo.pth] ran at startup, argv = ['-c']
2

$ venv/bin/pip --version
[demo.pth] ran at startup, argv = ['venv/bin/pip', '--version']
[demo.pth] ran at startup, argv = ['venv/bin/pip', '--version']
pip 25.2 from <tmp>/venv/lib/python3.14/site-packages/pip (python 3.14)
```

Read it line by line. The hook prints before the program's own code, so it runs at interpreter start. It also runs for `pip --version`, which never imports anything of mine, and `pip` is itself a Python script, so installing a package starts the hook. `python -I` (isolated mode) does not stop it. Only `python -S`, which skips the `site` module entirely, does.

The hook printed twice in my run. I did not investigate why. It does not change the point, but I will not pretend I can explain it. I ran this with Python 3.14.0 on macOS. The malware's own code was never in this test.

## What the stealer collects

The article describes a stealer that does two different things. It reads what is already on the machine, and it asks the platform for more.

**Reading what is on disk and in the environment:**

- environment variables whose names match credential-like patterns (version 1.26.2 widened the patterns)
- Azure CLI files, `.npmrc`, `pip.conf`, `.netrc`, `.git-credentials` and `.docker/config.json`
- Hugging Face and Azure DevOps agent credentials, plus `.env` and JSON files

**Asking for new tokens:**

- In Azure DevOps, it uses `SYSTEM_ACCESSTOKEN` and `SYSTEM_OIDCREQUESTURI` to request a federated token for `api://AzureADTokenExchange`. Version 1.26.2 also collects GitHub Actions {{< term "oidc" "OIDC" >}} tokens.
- On Azure compute, it calls the {{< term "managed-identity" "managed identity" >}} endpoint for each resource, using `IDENTITY_ENDPOINT` or `MSI_ENDPOINT` on App Service and Functions, and `169.254.169.254` elsewhere. It also reads the {{< term "imds" "instance metadata" >}} and keeps up to 8,000 characters of the answer.

Everything is collected into JSON, compressed with zlib, encoded in Base64 and sent by HTTPS POST to a hard-coded `webhook.site` URL.

The second group is the dangerous one. SafeDep says it in one sentence: besides reading credentials already on disk, the code asks the platform to issue new ones. That has a practical consequence. Rotating the secrets you stored does not cover tokens that were created during the attack.

## Am I affected, and what to do

You were exposed if a machine or CI runner installed `agent-framework` 1.26.1 or 1.26.2 in the window above. The article's advice, in the order I would do it:

1. **Find out.** Check lock files, `pip freeze` output and build logs for those two versions, around 8:35 to 9:20 p.m. UTC on 17 November. If a runner or developer machine resolved an unpinned `agent-framework` in that period, treat it as affected.
2. **Isolate and rebuild.** Isolate the affected hosts and runners. Pin to 1.26.0 and restore from a clean environment instead of cleaning the old one.
3. **Look for the exfiltration.** Search proxy and DNS logs for requests to the `webhook.site` address from the article: `webhook[.]site/d381fd80-ec62-42ad-8f5c-d1b15103c9bb` (written defanged here, remove the brackets only in a log search).
4. **Rotate from a clean system.** Rotate every credential that machine could reach, and do it from a machine that is not affected.
5. **Audit Azure.** Review the identities, sign-in logs and activity logs. Remember that stolen tokens may have been issued, not just copied.
6. **Audit your pipelines.** Check GitHub Actions workflows that deploy to Azure, because an OIDC token from a job can be as powerful as a stored secret.

## What this tells us

- **Pin and review dependencies in CI.** Here the bad versions were live for under an hour, per the article. A build that resolves "latest" at the wrong minute gets them. A {{< term "lockfile" "lock file" >}} with hashes turns "whatever is newest" into "exactly what I reviewed". The [packaging post](/posts/py-packaging-publishing/) and the [uv post](/posts/py-environment-uv-venv/) show the tools.
- **Install is code execution.** The danger was not the framework's API. It was the file installed next to it. Wheels can place files that run on every interpreter start, so "I never imported it" is not a defence.
- **Short-lived tokens are not safe if the job can request them.** Managed identity and OIDC remove stored passwords, which is good. But whatever runs inside the job can ask for the same tokens, so CI jobs should hold only the permissions they need. This is the same lesson as in the [secrets management post](/posts/sec-secrets-management/).
- **Do not run unknown installs on machines with cloud access.** Where possible, build in an environment that has no cloud credentials, and give the deploy step only the access it needs.

## What is known and what is not

- **From the article:** the affected versions, the time window, the `.pth` mechanism, the list of collected data, the token requests, the exfiltration method and the mitigation advice. I read the article, not the individual vendor reports it links (Aikido, Chainguard, Endor Labs, OX Security, SafeDep, Socket, StepSecurity and Wiz).
- **From me:** only the harmless `.pth` demo, run with Python 3.14.0 on macOS. It shows that `.pth` import lines run at start and for `pip`. It says nothing about the real payload.
- **Not verified here:** the malicious package contents, the exact file names beyond what the article states, and whether a given PyPI mirror or cache served those versions.
- **Open:** how the attacker got publishing access, who they are, and whether 1.26.0 stays the right pin. The article was published on 18 November, so details may change.

## References

- [The Hacker News: Attackers Compromise Microsoft's Agent Framework PyPI Package to Steal Cloud Credentials](https://thehackernews.com/2026/11/attackers-compromise-microsofts-agent.html)
- [Python documentation: the site module and .pth files](https://docs.python.org/3/library/site.html)
