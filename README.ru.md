# Team Orchestrator для Claude Code

[English version](README.md)

Плагин Claude Code, который превращает нетривиальный запрос в план, раздаёт шаги ролевым субагентам (архитектор,
разработчики, ревьюеры, безопасность, QA и др.) на подходящей модели и с подходящим усилием, проверяет результат и
отчитывается — при этом следит за лимитами подписки и за собственным контекстом.

## Зачем

- **Дороже всего контекст.** Длинная сессия, в которой модель сама читает файлы, быстро выедает окно контекста.
  Оркестратор отдаёт чтение и правки субагентам и работает с короткими отчётами вида `file:line — факт`.
- **Не та модель для задачи.** Поиск по репозиторию на самой сильной модели и проектирование протокола на самой
  дешёвой — одинаково плохо. У каждой роли есть модель и усилие по умолчанию; повышать их оркестратор начинает только
  после неудачи.
- **Лимит посреди задачи.** Перед каждой волной агентов оркестратор запускает «ворота лимитов» (`scripts/limits.py`) и
  при необходимости переходит в экономный режим, прекращает запуск агентов или переводит роли Fable на Opus с
  `effort: max`.
- **Потеря состояния при `/compact`.** В файле плана есть раздел `## Checkpoint`; хук `SessionStart` возвращает его
  в контекст после `/compact`, `/clear` и resume, так что работа продолжается по фактам, а не по сжатому пересказу.

## Возможности

- Один скилл (`team-orchestrator`) и 15 ролевых субагентов (`orch-*`) — см. [Роли](#роли).
- Оценка размера задачи: маленькие задачи делаются напрямую, оркестрируются только M и L.
- Планы в `.claude/plans/` по шаблону: роль, модель/усилие, критерии приёмки и команда проверки на каждый шаг.
- Лестница проверок: build-verifier, adversarial-ревьюер, ревьюер протоколов/крипто, security, QA; для критичных
  находок — панель из трёх независимых ревьюеров.
- Ворота лимитов: 5-часовая сессия, скользящие 7 дней и статус по моделям, автоматический откат Fable -> Opus
  (`effort: max`).
- Управление контекстом: чекпоинт при 50 % окна и просьба сделать `/compact` при 75 %.
- Параллельная работа без конфликтов: один писатель на файл, git worktree для параллельных писателей в одном дереве
  сборки.
- Гейт на прод: ничего не деплоится, не пушится и не удаляется без вашего явного «да» на конкретный шаг.
- Агенты в отдельных процессах с чистым контекстом: `spawn.sh` / `collect.sh`.
- Необязательная строка состояния: `model · ctx 41% · 5h 63% ↻14:50 · 7d 22%`.

## Как это работает

```
 вы: "/team-orchestrator <задача>"
   |
   v
 скилл-оркестратор ---- размер: S -> делает сам
   |                     M/L -> дальше
   v
 ворота лимитов (scripts/limits.py)  -> режим / статус моделей / заполнение контекста / действия
   |
   v
 план (.claude/plans/<дата>-<slug>.md, с разделом ## Checkpoint)
   |
   v
 ролевые агенты (orch-scout, orch-dev-*, orch-architect, ...)  <- брифы по templates/brief.md
   |                                                              (ворота лимитов перед каждой волной)
   v
 проверка (build-verifier, reviewer, protocol-reviewer, security, qa)
   |
   v
 гейт на прод (только с вашим явным «да»)  ->  отчёт: что изменено, чем проверено, что осталось
```

## Быстрый старт

В сессии Claude Code:

```
/plugin marketplace add newzealandgrom/claude-orchestrator
/plugin install team-orchestrator@team-orchestrator
```

Либо одной командой (Claude Code 2.1.275 и новее):

```
/plugin install team-orchestrator --marketplace newzealandgrom/claude-orchestrator
```

Из шелла:

```bash
claude plugin marketplace add newzealandgrom/claude-orchestrator
claude plugin install team-orchestrator@team-orchestrator            # при необходимости --scope user|project|local
# вариант одной командой (Claude Code 2.1.292 и новее):
claude plugin install team-orchestrator --marketplace newzealandgrom/claude-orchestrator
```

Плагин не может поставлять строку состояния, поэтому её включают отдельно (необязательно, но полезно):

```bash
git clone https://github.com/newzealandgrom/claude-orchestrator.git
cd claude-orchestrator
./install.sh --statusline-only
```

Скрипт копирует `limits.py`, `statusline.py` и `checkpoint.py` в `~/.claude/team-orchestrator/` и правит
`~/.claude/settings.json` (сначала делается копия `settings.json.bak-<timestamp>`). Уже настроенная строка
состояния сохраняется и дописывается через `ORCH_STATUSLINE_NEXT`.

Первый запуск:

```
/team-orchestrator fix the failing tests in api/ and add coverage
```

Скилл доступен как `/team-orchestrator:team-orchestrator`; короткое `/team-orchestrator` работает, если другая
команда не занимает это имя. Агенты вызываются как `team-orchestrator:orch-<role>`. Продолжить незаконченный
план: `/team-orchestrator resume`.

## Ручная установка (без системы плагинов)

```bash
git clone https://github.com/newzealandgrom/claude-orchestrator.git
cd claude-orchestrator
./install.sh                          # скилл + агенты для пользователя (~/.claude)
./install.sh --project <dir>          # скилл + агенты для одного проекта (<dir>/.claude)
```

Флаги: `--statusline` (дополнительно включить строку состояния), `--hooks` (дополнительно зарегистрировать три хука —
для установки плагином не нужно), `--statusline-only` (для пользователей плагина), `--dry-run` (показать, что
изменится). Перед любой правкой `settings.json` делается резервная копия. Учитывается `CLAUDE_CONFIG_DIR`.

Требования:

- Claude Code; рекомендуется 2.1.292 или новее (переопределение `effort` в каждом вызове нужно для отката Fable -> Opus).
- Python 3.9+, только стандартная библиотека.
- macOS или Linux. Режимы `terminal` и `interactive` у `spawn.sh` требуют macOS Terminal, режим `tmux` — tmux.
- Доступ к Fable необязателен: у агентов с `model: best` это Fable, если он есть у аккаунта, иначе Opus.

## Роли

Значения по умолчанию заданы во frontmatter агентов (`agents/orch-*.md`); `best` = Fable, если доступен, иначе Opus.

| Роль | Агент | Модель / усилие | Назначение |
|---|---|---|---|
| Архитектор / техлид | `orch-architect` | best / high | Ревью плана или спеки для крупных задач, второе мнение, судья. Только чтение. |
| Аналитик | `orch-analyst` | sonnet / high | Размытый запрос -> требования и критерии приёмки; расхождения документации и кода. Только чтение. |
| Senior-разработчик | `orch-dev-senior` | opus / high | Сквозные, протокольные, чувствительные к безопасности и многомодульные изменения. |
| Middle-разработчик | `orch-dev-middle` | sonnet / medium | Чётко описанное изменение внутри одного модуля. |
| Junior-разработчик | `orch-dev-junior` | haiku / medium | Механика по точной инструкции: применить diff, переименовать, поправить импорты. |
| DevOps / SRE | `orch-devops` | opus / medium | Снимки прода, планы деплоя с откатом; действует только при `OWNER_APPROVED: yes`. |
| Безопасность / пентест | `orch-security` | best / high | Модель угроз, auth, периметр, rate limits; неразрушающие проверки ваших собственных систем. Только чтение. |
| Ревьюер протоколов / крипто | `orch-protocol-reviewer` | best / high | Схемы ключей, wire-форматы, версионирование, кросс-платформенные тест-векторы. Только чтение. |
| Adversarial-ревьюер | `orch-reviewer` | opus / high | Пытается опровергнуть «готово» по шагу разработки; запускает сборку. Только чтение. |
| QA / голос пользователя | `orch-qa` | sonnet / medium | Сценарии, smoke-чеклисты, UX-ловушки; собирает и запускает, код не правит. |
| Build verifier | `orch-build-verifier` | haiku / low | Запускает перечисленные команды, возвращает PASS/FAIL со строками ошибок. |
| Scout | `orch-scout` | haiku / low | Карты `file:line — что`; навигация по большим документам. Только чтение. |
| Дизайнер / frontend | `orch-designer` | opus / medium | Дизайн-токены, экраны, компоненты, доступность, микротексты. |
| Технический писатель | `orch-tech-writer` | sonnet / medium | README, changelog, runbook; каждое утверждение сверяется с кодом. |
| Toolsmith | `orch-toolsmith` | sonnet / medium | Ищет и проверяет плагины/скиллы/MCP/LSP; возвращает команды установки, сам ничего не ставит. |

Типовые команды и детали: `skills/team-orchestrator/references/roles.md`.

## Лимиты и контекст

Подробнее: [docs/ru/limits-and-context.md](docs/ru/limits-and-context.md).

`python3 skills/team-orchestrator/scripts/limits.py` (около 1 с, локально, только чтение) печатает состояние для
маршрутизации. Оркестратор запускает его первым делом и перед каждой волной агентов.

| Уровень | Условие | Что меняется |
|---|---|---|
| normal | ниже 60 % самого тесного окна | до 4 тяжёлых (Opus/Fable) агентов параллельно, полная лестница проверок |
| economy | от 60 % | до 2 тяжёлых агентов, без панелей опровержения, Haiku для поиска и сборок, Sonnet для анализа |
| critical | от 80 % | новых Opus/Fable агентов нет; завершить начатое, чекпоинт, сообщить, что сделано/осталось и когда сброс |
| exhausted | от 95 % или активная ошибка лимита | ничего не запускать; чекпоинт; после сброса возобновить агентов через `SendMessage` |

До первого реального срабатывания лимита потолок — лишь предположение (самый большой прошлый блок), поэтому уровни,
выведенные из него, понижаются на одну ступень (от 80 % — `economy`, от 95 % — `critical`); настоящая ошибка лимита
всегда означает `exhausted`.

- **Откат Fable:** если Fable «выключен» (собственная ошибка лимита, недельная доля 85 % от его потолка или
  сессия в `critical`/`exhausted`), все роли Fable/`best` работают на Opus с `effort: max`.
- **Контекст:** при 50 % окна переписывается `## Checkpoint` плана; при 75 % оркестратор просит вас выполнить
  `/compact keep: plan <path>, running agents, next step`.
- **Строка состояния** показывает модель, заполнение контекста и — только для подписчиков Pro/Max — официальные
  проценты за 5 часов и 7 дней со временем сброса. Процент контекста доступен всем.
- **Конфиг:** `~/.claude/team-orchestrator/limits.json` (см. [Конфигурация](#конфигурация)).

## Хуки

Лежат в `hooks/hooks.json`, при установке плагином активны сразу:

| Событие | Команда | Эффект |
|---|---|---|
| `SessionStart` (matcher `compact\|resume\|clear`) | `checkpoint.py --hook` | Возвращает в контекст `## Checkpoint` активного плана и строку о лимитах. |
| `PostToolUse` (matcher `Agent`) | `limits.py --hook PostToolUse` | После вызова агента — указание, только если состояние ухудшилось или изменилось. |
| `UserPromptSubmit` | `limits.py --hook UserPromptSubmit --cache-sec 120` | То же, один раз на запрос. |

Хуки лимитов молчат, пока ничего не изменилось; отчёты кэшируются на 60–120 с; ошибка хука не ломает сессию
(код возврата 0).

## Агенты с чистым контекстом

Для длинной или независимой работы агента можно запустить в отдельном процессе `claude` без истории текущего чата.
Результаты лежат в `<project>/.claude/runs/<run-id>/`.

```bash
S=~/.claude/skills/team-orchestrator/scripts   # ручная установка; для плагина — каталог skills/team-orchestrator/scripts внутри плагина

# бриф из файла, фоновый headless-процесс
"$S/spawn.sh" orch-scout brief.md --mode headless --id scout-api

# бриф из stdin, переопределить модель и усилие (например, Fable выключен)
echo "Review api/auth.py:10-120 ..." | "$S/spawn.sh" orch-reviewer - --model opus --effort max

# видимые режимы: terminal (macOS Terminal), tmux (сессия "orch"), interactive (macOS)
"$S/spawn.sh" orch-dev-middle brief.md --mode tmux

# статус и результаты
"$S/collect.sh"                       # 20 последних запусков
"$S/collect.sh" scout-api --wait      # дождаться завершения
"$S/collect.sh" scout-api --full      # полный результат вместо первых 60 строк
```

Опции `spawn.sh`: `--mode headless|terminal|tmux|interactive`, `--id`, `--model`, `--effort`, `--max-turns`
(по умолчанию 60), `--schema <file>`, `--perm acceptEdits|default|plan|auto|dontAsk|bypass` (по умолчанию
`acceptEdits`), `--cwd`. Переменные окружения: `ORCH_RUNS`, `ORCH_PERM`, `ORCH_WAIT_MAX`. Прокси и переменные
`ANTHROPIC_*` текущего шелла передаются дочернему процессу через файл с правами `0600`, который удаляется после старта.

## Конфигурация

`~/.claude/team-orchestrator/limits.json` (либо путь из `$ORCH_LIMITS_CONFIG`, либо `--config <file>`; базовый каталог
определяется `CLAUDE_CONFIG_DIR`). Все ключи необязательны; вложенные объекты сливаются со значениями по
умолчанию. Шаблон: `examples/limits.example.json`.

| Ключ | По умолчанию | Смысл |
|---|---|---|
| `session_cap_units` | `null` | Задать потолок 5-часового окна вручную (условные единицы). |
| `weekly_cap_units` | `null` | Задать недельный потолок вручную. |
| `model_weekly_cap_units` | `{}` | Недельный потолок по семейству моделей, например `{"fable": 5000000, "opus": null}`. |
| `model_weights` | fable 2.0, opus 1.0, sonnet 0.6, haiku 0.2, other 1.0 | Относительный вес стоимости семейства. |
| `thresholds` | economy 0.60, critical 0.80, exhausted 0.95 | Уровни для сессии и недели. |
| `model_thresholds` | economy 0.60, off 0.85 | Недельные уровни по моделям. |
| `context_window` | `null` | Токены. Авто: 200k, либо 1M, если когда-либо наблюдалось больше или в id модели есть `[1m]`. |
| `context_thresholds` | checkpoint 0.50, compact 0.75 | Уровни заполнения контекста. |

Пример: зафиксировать потолок 5 часов и сделать оркестратор осторожнее.

```json
{
  "session_cap_units": 40000000,
  "thresholds": { "economy": 0.50, "critical": 0.70, "exhausted": 0.90 }
}
```

## Обновление и удаление

```bash
claude plugin marketplace update team-orchestrator
claude plugin update team-orchestrator@team-orchestrator

claude plugin uninstall team-orchestrator
```

Ручная установка: `./uninstall.sh` (или `./uninstall.sh --project <dir>`) удаляет скилл, агентов `orch-*`,
`~/.claude/team-orchestrator/` и записи строки состояния и хуков, упоминающие `team-orchestrator`; делает копию
`settings.json` и восстанавливает строку состояния, которая была до `install.sh`. Если при установке плагином вы
включали строку состояния через `--statusline-only`, запустите и `./uninstall.sh` — `claude plugin uninstall` ваши
настройки не трогает.

## FAQ

**У меня нет Fable.** Ничего делать не нужно: `model: best` превращается в Opus. Откат Fable -> Opus важен только
тем, у кого Fable есть.

**Данные уходят куда-нибудь?** В скриптах (`limits.py`, `statusline.py`, `checkpoint.py`) нет сетевого кода; они читают
локальные транскрипты в `~/.claude/projects/` (счётчики использования, id моделей, время, тексты ошибок лимитов) и
пишут небольшие файлы состояния в `~/.claude/team-orchestrator/`. Сами агенты — обычные субагенты Claude Code: они
обращаются к API Anthropic как любая сессия, а `orch-toolsmith` / `orch-security` могут пользоваться веб-инструментами,
если это указано в брифе.

**Linux? Windows?** Поддерживаются macOS и Linux. Скрипты написаны на bash и Python; нативной поддержки Windows нет,
WSL не проверялся.

**Насколько точны оценки лимитов?** Приблизительны. Точные потолки Anthropic не публикует; скрипт переводит счётчики
токенов во взвешенные единицы и калибрует потолки по ошибкам лимитов из ваших транскриптов. Реальные числа
(`rate_limits`) используются только при включённой строке состояния и подписке Pro/Max. Относитесь к уровням как
к страховке, а не как к учёту.

**Почему оркестратор не может сам выполнить `/compact`?** `/compact` и `/clear` — команды пользователя, модель их
вызвать не может. Оркестратор записывает чекпоинт и просит вас; потом хук `SessionStart` его возвращает.

## Участие в разработке

Issue и pull request приветствуются. Перед отправкой:

```bash
claude plugin validate --strict .
```

Для любого заметного пользователю изменения увеличьте `version` в `.claude-plugin/plugin.json` и добавьте строку в
`CHANGELOG.md`. Скрипты должны оставаться на стандартной библиотеке (Python 3.9+).

## Документация

- [Руководство по использованию](docs/ru/usage-guide.md)
- [Лимиты и контекст](docs/ru/limits-and-context.md)

## Лицензия

MIT, см. [LICENSE](LICENSE).
