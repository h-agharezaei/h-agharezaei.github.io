+++
title = "Upcasting"
summary = "Converting an old stored event shape to the current one while reading, instead of editing stored events."
category = "Distributed"
related = ["event-sourcing"]
posts = ["ds-cqrs-event-sourcing"]
+++

A v1 payload with amount 5 is read as amount_cents 500 plus a currency; the stored row stays untouched.
