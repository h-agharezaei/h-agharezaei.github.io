+++
title = "AVL tree"
fa_title = "درخت AVL"
summary = "درخت جست‌وجوی دودویی که با rotation اختلاف ارتفاع دو زیردرخت هر node را حداکثر ۱ نگه می‌دارد."
category = "Algorithms"
related = ["binary-search-tree", "tree-rotation"]
posts = ["algo-trees-bst-btree"]
+++

قاعده‌ی تعادل ارتفاع را حدود 1.44 log2(n+2) محدود می‌کند، پس حتی با ورودی مرتب هر عملیات O(log n) است. بعد از هر درج یا حذف، عدم‌تعادل با [rotation](/fa/glossary/tree-rotation/) اصلاح می‌شود.
