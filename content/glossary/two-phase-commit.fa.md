+++
title = "Two-phase commit (2PC)"
summary = "پروتکلی که در آن coordinator از همه‌ی participantها می‌خواهد prepare کنند و بعد به همه می‌گوید commit کنید یا همه abort."
category = "Distributed"
fa_title = "commit دو فازی (2PC)"
related = ["saga", "prepared-transaction", "atomic-commit"]
posts = ["ds-saga-vs-2pc"]
+++

در فاز اول هر participant کارش را durable می‌کند و رأی yes یا no می‌دهد. در فاز دوم coordinator پس از ثبت تصمیم در log به همه می‌گوید commit یا abort. این روش atomicity بین چند سیستم می‌دهد، اما participantی که prepared شده باید منتظر coordinator بماند و در این مدت lockهایش را نگه می‌دارد.
