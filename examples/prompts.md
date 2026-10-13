# Prompts

Copy-paste prompts for Claude Orchestrator, grouped by task type. Each one works as `/orchestrator:orchestrator <prompt>` (manual install: `/orchestrator <prompt>`). Plain words work too: "Use the orchestrator to …" or «Оркестратор, …» — Claude loads the skill when the request matches. The orchestrator answers in the language you write in. The italic line under each prompt says what it will do; the full recipes are in the [playbooks](../skills/orchestrator/references/playbooks.md).

What makes a prompt work harder: say what "done" means, name constraints ("don't deploy", "only in `api/`"), add a budget ("keep it under 15% of my 5-hour limit" becomes the plan's `Budget:`), and give paths when you know them. Adjust the paths and numbers below to your project.

## Bugs

**1. Crash from a stack trace**
- 🇬🇧 `Users get HTTP 500 on POST /api/orders when the cart is empty (stack trace in logs/error.log, last entry). Find the root cause, fix it and add a regression test.`
- 🇷🇺 `Пользователи получают HTTP 500 на POST /api/orders при пустой корзине (стектрейс в logs/error.log, последняя запись). Найди причину, исправь и добавь регрессионный тест.`

*Bugfix playbook: scout maps the failing path, test-engineer writes the failing test first, dev-middle fixes, build-verifier and reviewer check in parallel. Walkthrough: [sessions/01-bugfix.md](sessions/01-bugfix.md).*

**2. Flaky test**
- 🇬🇧 `The test checkout.spec fails in about one CI run out of five. Find out whether the flakiness is in the test or in the code, and fix the right one.`
- 🇷🇺 `Тест checkout.spec падает примерно в одном запуске CI из пяти. Выясни, нестабилен тест или код, и исправь то, что нужно.`

*build-verifier reruns it and records failures, test-engineer finds the cause (timing, shared state, order); a product race goes to dev-middle, a test fault is fixed in the test; reviewer checks.*

**3. Regression after a release**
- 🇬🇧 `Since Tuesday's release PDF exports are blank in Safari. Find the commit that broke it and fix it. Do not touch production without asking me.`
- 🇷🇺 `После релиза во вторник PDF-экспорт в Safari пустой. Найди коммит, который это сломал, и исправь. Ничего не трогай на проде без моего разрешения.`

*scout narrows the suspect commits with `git log`, build-verifier runs the repro per commit, dev fixes with a regression test, reviewer checks; a production fix waits for your yes (devops snapshot → plan with rollback → yes).*

## Features

**4. A full-stack feature with a budget**
- 🇬🇧 `Add "forgot password" by e-mail: a link valid for 30 minutes and a new page to set the password. Backend API, DB migration, web client, e-mail template. Keep it under 25% of my 5-hour limit and don't deploy anything without asking me.`
- 🇷🇺 `Добавь «забыли пароль» по e-mail: ссылка на 30 минут и новая страница для смены пароля. Backend API, миграция БД, веб-клиент, шаблон письма. Уложись в 25% моего 5-часового лимита и ничего не выкатывай без моего разрешения.`

*Feature playbook, size L: scouts → security reviews the design → migration, backend and web (one writer per file) → tests → reviewer, security, accessibility, qa → docs; deploy only after your yes. Walkthrough: [sessions/02-feature.md](sessions/02-feature.md), plan: [plan-feature.md](plan-feature.md).*

**5. A smaller feature**
- 🇬🇧 `Add a CSV export to the Reports page: current filters, up to 100k rows, streamed, with a progress indicator. Keep it under 10% of my 5-hour limit.`
- 🇷🇺 `Добавь экспорт в CSV на страницу Reports: с текущими фильтрами, до 100 тысяч строк, потоком, с индикатором прогресса. Уложись в 10% моего 5-часового лимита.`

*analyst fixes the acceptance criteria, api-designer drafts the endpoint, dev-middle builds the stream while frontend builds button, progress and error states, test-engineer covers big inputs, reviewer and qa check.*

**6. A feature with authorisation rules**
- 🇬🇧 `Add team invitations: an admin creates an invite link with a role (member or admin), it expires in 7 days, and the invitee joins after signing up. Include the migration and the admin UI.`
- 🇷🇺 `Добавь приглашения в команду: администратор создаёт ссылку с ролью (участник или админ), она действует 7 дней, приглашённый вступает после регистрации. Включи миграцию и интерфейс администратора.`

*analyst and api-designer first (roles, expiry, abuse cases), db-engineer for the migration, dev-senior for the backend, frontend for the admin UI, security checks the authorisation, qa walks the invite lifecycle.*

## Refactoring

**7. Split a monolith file**
- 🇬🇧 `Split OrdersController (about 3,000 lines) into services without changing behaviour. The public API must stay identical.`
- 🇷🇺 `Раздели OrdersController (около 3000 строк) на сервисы без изменения поведения. Публичный API должен остаться тем же.`

*Refactor playbook: scouts list the callers, test-engineer adds a safety net first, architect cuts small steps, dev-senior does one at a time with a build-verifier run after each, reviewer checks the whole diff.*

**8. Modernise a module**
- 🇬🇧 `Convert the callback code in src/db/ to async/await, file by file, with no behaviour changes and green tests after every file.`
- 🇷🇺 `Переведи callback-код в src/db/ на async/await, файл за файлом, без изменений поведения и с зелёными тестами после каждого файла.`

*test-engineer pins current behaviour, dev-middle converts file by file (one writer per file), build-verifier runs after each file, reviewer checks the full diff.*

## Tests

**9. Raise coverage where it matters**
- 🇬🇧 `Raise the test coverage of the billing module, focusing on proration and refunds. Report the bugs you find, but do not fix them in this task.`
- 🇷🇺 `Подними покрытие тестами модуля billing, упор на пропорциональный расчёт и возвраты. О найденных багах сообщи, но в этой задаче их не чини.`

*Test-coverage playbook: build-verifier records the baseline, scout ranks untested paths by risk, test-engineer writes deterministic tests (edges first); bugs stay as expected-fail tests and become separate bugfix steps.*

**10. A slow e2e suite**
- 🇬🇧 `Our e2e suite takes 25 minutes. Find the slowest tests, make them faster or run them in parallel, and keep them stable.`
- 🇷🇺 `Наш e2e-набор идёт 25 минут. Найди самые медленные тесты, ускорь их или запусти параллельно и сохрани стабильность.`

*build-verifier collects timings, performance and test-engineer look for waits, shared fixtures and serial setup and change one thing at a time; reviewer checks that nothing became flaky.*

## Performance

**11. A slow endpoint**
- 🇬🇧 `The /reports endpoint takes 8 seconds for 1M rows. Profile it and bring p95 under 1 second. Show before and after numbers.`
- 🇷🇺 `Эндпоинт /reports отвечает 8 секунд на 1 млн строк. Профилируй и сведи p95 до 1 секунды. Покажи цифры до и после.`

*Performance playbook: performance builds the baseline first and ranks hypotheses by profile evidence, db-engineer takes queries and indexes, one change at a time with the same measurement, reviewer checks cache and race risks.*

**12. A heavy web bundle**
- 🇬🇧 `The web bundle is 4 MB and the first load is slow on mobile. Find out why and cut it without removing features.`
- 🇷🇺 `Веб-бандл весит 4 МБ, и первая загрузка на мобильных медленная. Выясни причину и уменьши бандл, не убирая функциональность.`

*performance measures with a bundle analyzer, frontend applies code splitting and lazy routes, build-verifier enforces the size, qa checks the main flows.*

## Security

**13. An audit of your own system**
- 🇬🇧 `Audit the authentication and file-upload code of this API. We own it; production is read-only for you. Confirmed findings only, each with file:line, a scenario and a fix.`
- 🇷🇺 `Проведи аудит аутентификации и загрузки файлов в этом API. Он наш; прод только для чтения. Только подтверждённые находки: file:line, сценарий и исправление.`

*Security-audit playbook: scouts map the attack surface; security, protocol-reviewer, privacy-compliance and dependency-auditor work in parallel; criticals go through a refute panel of three. Walkthrough: [sessions/03-security-audit.md](sessions/03-security-audit.md).*

**14. A threat model before building**
- 🇬🇧 `Make a threat model for the new payments webhook before we build it: abuse cases, what must be authenticated, what to log and what never to log. No code.`
- 🇷🇺 `Составь модель угроз для нового webhook платежей до начала разработки: сценарии злоупотребления, что должно быть аутентифицировано, что логировать и что нельзя. Без кода.`

*security works on the spec (with api-designer for the contract): trust boundaries, signature and replay checks, idempotency, logging rules; the result is a checklist that later briefs quote.*

**15. Rate limits and proxy trust**
- 🇬🇧 `Check whether our login endpoint can be brute-forced and whether the rate limit can be bypassed with X-Forwarded-For. Non-destructive checks only, on a local instance.`
- 🇷🇺 `Проверь, можно ли перебирать пароли на нашем login и обходится ли rate limit через X-Forwarded-For. Только неразрушающие проверки, только на локальном экземпляре.`

*security reads the limiter and proxy-trust code, devops (read-only) the proxy config, tests run against a local instance; each finding has a scenario and a fix, and every fix gets a second look.*

**16. Clean-context reviews**
- 🇬🇧 `Review the payments, auth and uploads modules for security problems. Run each review as a separate headless process with a clean context so my main context stays small.`
- 🇷🇺 `Проверь модули payments, auth и uploads на проблемы безопасности. Запусти каждую проверку отдельным headless-процессом с чистым контекстом, чтобы мой основной контекст не разрастался.`

*the briefs go to `scripts/spawn.sh orch-security <brief> --mode headless` (three runs), results come back through `scripts/collect.sh`; with Fable off the runs get `--model opus --effort max`.*

## Privacy

**17. A data map**
- 🇬🇧 `Map what personal data the app collects, where it is stored and logged, and where it is sent. Compare it with our privacy policy and list the mismatches.`
- 🇷🇺 `Составь карту персональных данных: что приложение собирает, где хранит и логирует, куда отправляет. Сравни с нашей политикой конфиденциальности и перечисли расхождения.`

*privacy-compliance with scout maps (engineering findings, not legal advice): a data-map table, PII in logs and analytics, third-party SDKs, mismatches with `file:line`, risk-ranked fixes.*

**18. Account deletion and export**
- 🇬🇧 `Add account deletion and data export for users. First find every place where user data lives, then implement and test it.`
- 🇷🇺 `Добавь удаление аккаунта и экспорт данных пользователя. Сначала найди все места, где хранятся данные пользователя, затем реализуй и протестируй.`

*analyst and privacy-compliance build the data map, api-designer the contract, db-engineer and dev-senior implement deletion (cascades, backups, logs), test-engineer covers it, privacy-compliance verifies nothing is left behind.*

## Accessibility

**19. A WCAG audit**
- 🇬🇧 `Audit the checkout flow against WCAG 2.2 AA: keyboard, screen reader, contrast, text scaling. Fix what is easy and list the rest.`
- 🇷🇺 `Проверь оформление заказа на соответствие WCAG 2.2 AA: клавиатура, скринридер, контраст, масштаб текста. Исправь простое, остальное перечисли.`

*accessibility audits read-only with concrete fixes, frontend applies the easy ones, accessibility re-checks them; a manual screen-reader pass is listed as "not verified" for you.*

**20. Small screens and zoom**
- 🇬🇧 `Make the dashboard usable at 320 px width and at 200% text zoom without horizontal scrolling.`
- 🇷🇺 `Сделай дашборд пригодным для ширины 320 px и масштаба текста 200% без горизонтальной прокрутки.`

*scout finds fixed widths and overflow, frontend fixes layout and breakpoints, accessibility re-checks reflow and focus order, qa gets the viewport list.*

## Dependencies

**21. Reachable vulnerabilities only**
- 🇬🇧 `Fix every npm audit finding that is actually reachable from our code. Do not upgrade anything else.`
- 🇷🇺 `Исправь все находки npm audit, которые реально достижимы из нашего кода. Больше ничего не обновляй.`

*dependency-auditor checks reachability and returns a table, dev-middle upgrades per package group, build-verifier compares against the baseline, reviewer reads the lockfile diff.*

**22. A major upgrade**
- 🇬🇧 `Upgrade React 17 to 18, one major step at a time. Tests must stay green, and I want the breaking changes summarised with sources.`
- 🇷🇺 `Обнови React 17 до 18 по одному мажорному шагу. Тесты должны оставаться зелёными, а breaking changes нужны с источниками.`

*Dependency-upgrade playbook: baseline first, researcher collects breaking changes with URLs, dev-middle migrates, test-engineer covers gaps the upgrade exposes, reviewer checks the diff; deploy waits for your yes.*

## Database

**23. A migration without downtime**
- 🇬🇧 `Add deleted_at to orders (20M rows) and switch queries to soft delete without downtime. Show me the migration plan before running anything.`
- 🇷🇺 `Добавь deleted_at в orders (20 млн строк) и переведи запросы на мягкое удаление без простоя. Покажи план миграции до запуска чего-либо.`

*Migration playbook: db-engineer designs expand → batched backfill → switch → contract with a rollback, tested on a disposable copy; reviewer checks; devops snapshot and plan; your yes before anything touches production.*

**24. An index review**
- 🇬🇧 `Find the slowest queries in the app and propose indexes. Check the query plans; do not guess.`
- 🇷🇺 `Найди самые медленные запросы в приложении и предложи индексы. Проверяй планы запросов, не гадай.`

*db-engineer collects candidates, runs EXPLAIN on a disposable database, proposes indexes only for real predicates and sort orders with before/after plans and the write cost; reviewer checks the migration.*

## API design

**25. A new public API**
- 🇬🇧 `Design a public REST API for invoices (list, create, void) with pagination, idempotency keys, an error model and versioning. Spec only, no code.`
- 🇷🇺 `Спроектируй публичный REST API для счетов (список, создание, аннулирование) с пагинацией, ключами идемпотентности, моделью ошибок и версионированием. Только спецификация, без кода.`

*api-designer writes the contract with examples and the deprecation path; architect gives a second opinion because a public contract is hard to undo; no code is written.*

**26. A breaking rename**
- 🇬🇧 `We want to rename userId to user_id in the API. Which clients break, and what is the safe rollout?`
- 🇷🇺 `Хотим переименовать userId в user_id в API. Какие клиенты сломаются и как безопасно выкатить?`

*scouts find every client usage, api-designer classifies breaking and non-breaking changes with the affected callers and proposes a dual-field rollout with a deprecation date.*

## Mobile

**27. The same feature on iOS and Android**
- 🇬🇧 `Add biometric unlock to the iOS and Android apps. Behaviour must be identical on both platforms; secrets stay in Keychain and Keystore.`
- 🇷🇺 `Добавь разблокировку по биометрии в приложения iOS и Android. Поведение на платформах должно совпадать; секреты остаются в Keychain и Keystore.`

*two mobile agents, one per platform, in parallel (separate worktrees if they share a build tree; one heavy build at a time), a parity check between them, security reviews secure storage, qa gets an on-device checklist.*

**28. A lifecycle crash**
- 🇬🇧 `The Android app crashes on resume after the system killed the process. Reproduce and fix it.`
- 🇷🇺 `Android-приложение падает при возврате после того, как система убила процесс. Воспроизведи и исправь.`

*scout maps state restoration, mobile reproduces it by killing the process in the background and fixes the lifecycle handling, a test covers it, reviewer checks; the on-device check is listed for you.*

## Frontend

**29. A page from a spec**
- 🇬🇧 `Build the "Team settings" page from this spec: members table, role dropdown, invite modal, with loading, empty and error states. Use our design tokens.`
- 🇷🇺 `Собери страницу «Настройки команды» по этой спецификации: таблица участников, выбор роли, модальное окно приглашения, состояния загрузки, пустоты и ошибки. Используй наши дизайн-токены.`

*frontend builds the components with all four states, keyboard and focus handling, then runs type-check, lint and build; accessibility, reviewer and qa check; designer joins only if tokens are missing.*

**30. A render storm**
- 🇬🇧 `The product list re-renders on every keystroke in the search box. Find the cause and fix it, with a before/after render count.`
- 🇷🇺 `Список товаров перерисовывается при каждом нажатии клавиши в поиске. Найди причину и исправь, покажи число рендеров до и после.`

*performance measures render counts with the profiler, frontend applies memoisation or moves state closer to where it is used, one change at a time; reviewer checks behaviour is unchanged.*

## DevOps and incidents

**31. Production is broken**
- 🇬🇧 `Checkout returns 502 since 14:20. Find out why and propose the safest fix. Do not change anything on the server without asking me.`
- 🇷🇺 `Оформление заказа отдаёт 502 с 14:20. Выясни причину и предложи самое безопасное исправление. Ничего не меняй на сервере без моего разрешения.`

*Incident playbook: incident-responder, a read-only devops snapshot and a scout run in parallel; ranked hypotheses; a mitigation plan with rollback; your yes; devops runs only the approved actions; a postmortem afterwards.*

**32. A runbook and a rollback**
- 🇬🇧 `Write a deploy runbook and a rollback script for the web service. Dry run only; do not connect to any server.`
- 🇷🇺 `Напиши runbook деплоя и скрипт отката для веб-сервиса. Только пробный прогон, ни к какому серверу не подключайся.`

*devops writes the steps and scripts in the repo and tests them locally, tech-writer turns them into a runbook, reviewer checks every command for safety; production is not touched.*

**33. CI for pull requests**
- 🇬🇧 `Set up CI that runs lint, tests and a Docker build on every pull request, with dependency caching.`
- 🇷🇺 `Настрой CI, который на каждый pull request запускает линтер, тесты и сборку Docker-образа, с кэшем зависимостей.`

*devops writes the workflow, build-verifier runs the same commands locally, reviewer checks permissions and secret handling; pushing the workflow is outward-facing, so it waits for you.*

## Release

**34. Prepare a release**
- 🇬🇧 `Prepare release 2.4.0: version bump, changelog, migration notes and checks. Show me the publish commands but do not run them.`
- 🇷🇺 `Подготовь релиз 2.4.0: повышение версии, changelog, заметки по миграции и проверки. Покажи команды публикации, но не запускай их.`

*Release playbook: release-manager drafts version, changelog and notes, build-verifier runs the full matrix, dependency-auditor checks licences and CVEs, qa smoke-tests; you get exact commands and a rollback, publishing needs your yes.*

**35. A hotfix**
- 🇬🇧 `Cut a hotfix 2.3.1 for the PDF bug and show me the rollback plan.`
- 🇷🇺 `Выпусти хотфикс 2.3.1 для бага с PDF и покажи план отката.`

*bugfix first (test, fix, review), then the release steps: patch bump, changelog line, rollback plan; nothing is tagged or pushed before your yes.*

## Docs

**36. A README that is true**
- 🇬🇧 `Write a README for this repo: install, configuration, common errors. Every command in it must be checked.`
- 🇷🇺 `Напиши README для этого репозитория: установка, настройка, частые ошибки. Каждая команда в нём должна быть проверена.`

*Docs playbook: scout lists what is real, tech-writer writes only what the code supports, build-verifier runs every command, reviewer tries to refute a sample of the claims.*

**37. Docs that drifted**
- 🇬🇧 `Find places where the docs contradict the code and fix the docs.`
- 🇷🇺 `Найди места, где документация противоречит коду, и исправь документацию.`

*analyst lists the contradictions with `file:line`, tech-writer fixes the docs (not the code), build-verifier checks commands and links, reviewer checks the claims.*

## Research

**38. Compare options**
- 🇬🇧 `Compare Postgres full-text search, Meilisearch and Elasticsearch for our 2M-document catalog. I need a recommendation with sources.`
- 🇷🇺 `Сравни полнотекстовый поиск Postgres, Meilisearch и Elasticsearch для нашего каталога на 2 млн документов. Нужна рекомендация с источниками.`

*researcher (web, read-only) compares them in a table against your constraints (fit, maturity, licence, cost, lock-in) with a URL for every fact; architect can judge if the choice is hard to reverse.*

**39. Pick a library**
- 🇬🇧 `Which OAuth library should we use for a Python FastAPI service? Check maintenance status and licences.`
- 🇷🇺 `Какую OAuth-библиотеку взять для Python-сервиса на FastAPI? Проверь, поддерживается ли она, и лицензии.`

*researcher compares candidates (maintenance, licence, security history) with sources; dependency-auditor can vet the finalists; no code changes.*

## Onboarding

**40. An inherited repo**
- 🇬🇧 `I inherited this repository. Explain what it does, how to run it and what is risky. Do not change anything.`
- 🇷🇺 `Мне достался этот репозиторий. Объясни, что он делает, как его запустить и что в нём рискованно. Ничего не меняй.`

*Onboarding playbook: build-verifier tries the commands, scouts map each area in parallel, analyst lists contradictions and questions, tech-writer writes `.claude/orchestrator/project-map.md`.*

**41. Tools for an unfamiliar stack**
- 🇬🇧 `Which plugins, LSP servers or MCP servers would help with this Rust codebase? Recommend at most three with install commands, but do not install anything.`
- 🇷🇺 `Какие плагины, LSP- и MCP-серверы помогут с этим Rust-проектом? Предложи не больше трёх с командами установки, но ничего не устанавливай.`

*toolsmith checks the official marketplace first, then reputable sources, vets maintenance, permissions and context cost, and returns at most three candidates with exact commands; it never installs.*

## Commands

**42. Status**
- 🇬🇧 `/orchestrator:status` — or in words: `Where are we with the plan?`
- 🇷🇺 `/orchestrator:status` — или словами: `Что с планом?`

*a dashboard of at most 12 lines: plan progress, agents in flight, next step, decisions waiting for you, limits and spend against the budget ([sample](outputs/status.txt)).*

**43. Limits**
- 🇬🇧 `/orchestrator:limits` — or: `How much of my limits is left?`
- 🇷🇺 `/orchestrator:limits` — или: `Сколько у меня осталось лимитов?`

*explains `limits.py` in a few lines: mode, per-model status, context fill, reset time and the actions the orchestrator will take ([sample](outputs/limits.txt)). Pro and Max get exact numbers through the status line; otherwise they are estimates from local transcripts.*

**44. Costs**
- 🇬🇧 `/orchestrator:costs` — or: `What did this task cost?`
- 🇷🇺 `/orchestrator:costs` — или: `Сколько стоила эта задача?`

*tokens and share of the 5-hour limit per role and per agent, top consumers, the plan budget and one saving tip ([sample](outputs/costs.txt)).*

**45. Resume**
- 🇬🇧 `/orchestrator:resume` — after /compact, /clear, a restart or a limit reset.
- 🇷🇺 `/orchestrator:resume` — после /compact, /clear, перезапуска или сброса лимита.

*loads the checkpoint of the in-progress plan, re-reads it, runs the limits gate and continues; finished or failed agents are resumed with `SendMessage`, nobody is re-briefed.*

**46. Setup**
- 🇬🇧 `/orchestrator:setup` (once) — and `/orchestrator:setup remove` to undo it.
- 🇷🇺 `/orchestrator:setup` (один раз) — и `/orchestrator:setup remove`, чтобы отменить.

*turns on the status line: copies the scripts to `~/.claude/claude-orchestrator/` and adds a `statusLine` entry to `~/.claude/settings.json` (backup first, an existing status line is kept). `remove` removes the status line and hooks entries again, keeping your data and `limits.json`.*
