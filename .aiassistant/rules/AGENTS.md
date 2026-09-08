---
apply: always
---

### Project Overview
Book fair Telegram bot (`bot/`) and admin console (`admin/`) sharing persistent data in `./assets/`.

### Architecture & Style
- Modular OOP: ~1 class per file, group by domain in packages.
- Prefer existing libraries to custom implementations.
- Code & internal constants: English only (`en`).
- UI & user-facing messages: Russian only (`ru`).
- Avoid overriding the developer's latest changes, unless really needed.
- Avoid implementing code which the prompt does not specify.

### Testing & Logs
- Write `pytest` unit tests for new features in `tests/`.
- Log all handled exceptions with traceable context.