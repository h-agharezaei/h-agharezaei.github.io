+++
title = 'monkeypatch'
summary = 'temporarily replacing an attribute, env var or dict item during a test'
category = 'Python'
related = ["fixture", "test-double"]
posts = ["py-testing-pytest"]
+++

**monkeypatch** is a pytest fixture that changes things like environment variables, attributes or dictionary items for the duration of one test and undoes every change afterwards. It keeps tests from leaking state into each other.
