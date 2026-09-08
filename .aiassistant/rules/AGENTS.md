---
apply: always
---

### Project Overview
Book fair Telegram bot (`bot/`) and admin console (`admin/`) sharing persistent data in `./assets/`.

### Architecture & Style
- Modular OOP: ~1 class per file, group by domain in packages.
- Prefer existing libraries to custom implementations.
- Focus on the given task. Do not implement code which is not asked for. Do not change the existing code if it's not necessary for the task
- Code, internal constants, reasoning and chat messages: English only.
- Bot and Admin UI: Russian only.
- Avoid overriding the developer's latest changes, unless really needed.
- Avoid implementing code which the prompt does not specify.
- Minimize token consumption. Do not to work unless it is really needed.

### Behaviour 
- Focus on the given task. Do not implement code which is not asked for. Do not change the existing code if it's not necessary for the task
- Code, internal constants, reasoning and chat messages: English only.
- Bot and Admin UI: Russian only. NEVER reason, switch context or respond in chat in Russian. 

### Testing & Logs
- Write `pytest` unit tests for new features in `tests/`. Do not write too much.
- Log all handled exceptions with traceable context.