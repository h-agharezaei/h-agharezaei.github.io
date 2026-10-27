+++
title = "Dynamic programming"
fa_title = "برنامه‌ریزی پویا"
summary = "حل مسئله با ترکیب جواب زیرمسئله‌های کوچک‌تر که هر کدام یک بار حل و ذخیره می‌شود."
category = "Algorithms"
related = ["memoization", "overlapping-subproblems", "optimal-substructure"]
posts = ["algo-dynamic-programming-1", "algo-dynamic-programming-2", "algo-greedy-backtracking"]
+++

حل مسئله با ترکیب جواب زیرمسئله‌های کوچک‌تر که هر کدام یک بار حل و ذخیره می‌شود.

مسئله وقتی مناسب است که [زیرساخت بهینه](/fa/glossary/optimal-substructure/) و [زیرمسئله‌های تکراری](/fa/glossary/overlapping-subproblems/) داشته باشد. یک state، یک transition، حالت‌های پایه و یک ترتیب تعریف می‌کنید و جدول را پر می‌کنید یا بازگشت را memoize می‌کنید.
