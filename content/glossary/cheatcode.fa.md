+++
title = "Cheatcode"
fa_title = "cheatcode"
summary = "فراخوانی ویژه در تست Foundry که EVM تست را دست‌کاری می‌کند: تنظیم موجودی، جا زدن فرستنده، انتظار revert یا رویداد."
category = "Blockchain"
related = ["foundry", "invariant-testing"]
posts = ["bc-foundry-testing-fuzzing"]
+++

cheatcodeها روی شیء `vm` صدا زده می‌شوند، مثل `vm.deal`، `vm.prank`، `vm.expectRevert` و `vm.expectEmit`. فقط در محیط تست [Foundry](/fa/glossary/foundry/) وجود دارند، نه روی زنجیره‌ی واقعی.
