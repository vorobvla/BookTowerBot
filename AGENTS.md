---
apply: always
---

### Project Overview
Book fair Telegram bot (`bot/`) and admin console (`admin/`) sharing persistent data in `./assets/`.

### Architecture & Style
- Modular OOP: ~1 class per file, group by domain in packages.
- Prefer existing libraries to custom implementations.
- Avoid overriding the developer's latest changes unless necessary.

### Behaviour & Scope
- Focus strictly on the given task. Do not implement unrequested features or refactor unrelated code.
- Code, internal constants, reasoning, and chat messages: English only.
- Bot and Admin UI strings: Russian only. NEVER reason or respond in Russian in chat.
- Minimize credit consumption: provide direct, concise responses without preamble. NEVER REASON AND ANSWER IN ANOTHER LANGUAGE THEN ENGLISH EVEN IF THERE IS ANOTHER LANGUAGE IN PROMPT.

### Testing & Logs
- Write focused `pytest` unit tests for new features in `tests/` without excessive coverage boilerplate.
- Log all handled exceptions with traceable context.