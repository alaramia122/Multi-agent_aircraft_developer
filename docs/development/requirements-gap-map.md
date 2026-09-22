# Карта соответствия ТЗ → текущая реализация → следующий этап

## Назначение

Документ фиксирует фактическую границу проекта относительно ТЗ «Мультиагентная система для разработки авиационных комплексов».

Карта разделяет:

- реализованный Engineering Gateway;
- production/deployment работы вокруг Gateway;
- ещё не реализованный AI Studio слой;
- внешние интеграции и эксплуатационную инфраструктуру.

Статус относится к текущей ветке `main`. Наличие Gateway-контракта не означает наличие подключённой production-системы.

## 1. Верхнеуровневая карта системы

```text
                           Yandex AI Studio
                    ┌──────────────────────────┐
                    │ Agents                   │
                    │ Workflows / Orchestration│
                    │ RAG / Knowledge          │
                    └────────────┬─────────────┘
                                 │ MCP
                                 ▼
                    ┌──────────────────────────┐
                    │ Engineering Gateway      │
                    │                          │
                    │ Identity / Authorization│
                    │ MCP Gateway               │
                    │ Standard Profile Engine  │
                    │ Validation / Traceability│
                    │ Change / Approval Gate    │
                    │ Workspace / Reconciliation│
                    │ Baseline / Audit          │
                    │ Cost / Budget              │
                    │ Adapters                   │
                    └──────┬────┬────┬────┬─────┘
                           │    │    │    │
                           ▼    ▼    ▼    ▼
                         Git StrictDoc Capella OpenProject
                           │
                           ▼
                    PostgreSQL / Object Storage
```

Важно: PostgreSQL хранит состояние Gateway, provenance, workflow и audit, а не вторую инженерную модель. Vector Store, когда будет добавлен, является retrieval-механизмом, а не Source of Truth.

## 2. Карта требований

| Область ТЗ | Требуемая функция | Текущее состояние | Статус | Следующий шаг |
|---|---|---|---|---|
| Gateway | Единая интеграционная точка для инженерных систем | Реализован Gateway boundary, application/domain/persistence/adapters/MCP | 🟢 | Стабилизация и production integration |
| Canonical Model | EngineeringElement / Relation / Graph без копирования внешних моделей | Реализовано | 🟢 | Поддерживать контракт |
| Standard Profiles | Конфигурируемая поддержка стандартов без ветвления Gateway core | Versioned profiles, validation, registration, activation, deterministic composition | 🟢 | Использовать при реальных профилях/интеграциях |
| Validation | Детерминированная проверка модели по профилю | Реализованы kind/type, identity, attributes, relations, traceability, verification, lifecycle, artifacts, fingerprint | 🟢 | Расширять только при появлении требований |
| Traceability | Анализ сквозных связей требований/архитектуры/verification | Реализован deterministic graph-based слой и gap diagnostics | 🟢 | Подключить к реальным источникам |
| Governance | L0/L1/L2/L3, human-only approval | Реализовано; MCP L3 отсутствует | 🟢 | Production IdP и эксплуатационная проверка |
| Workspace | Изменения только через workspace/change-set | Реализовано, baseline immutable | 🟢 | E2E с реальными адаптерами |
| Reconciliation | Детерминированная публикация, replay/idempotency, concurrency | Реализованы UoW, advisory lock, optimistic concurrency, evidence reuse | 🟢 | Реальные staging systems |
| Audit | Append-only audit и сохранение denial/failure evidence | Реализовано | 🟢 | Production retention/operations |
| Git | Snapshot, ancestry, immutable baseline tags | Реализован CLI adapter | 🟢 | Production credentials/policies |
| StrictDoc | Чтение требований | Реализован CLI JSON export boundary | 🟢 | Реальная установка; controlled write-back/ReqIF при необходимости |
| Capella | Архитектурные элементы/связи через bridge | Реализован versioned bridge boundary | 🟡 | Реальный headless bridge executable и deployment |
| OpenProject | Change Request / workflow | Реализован API v3 adapter, lockVersion, idempotency | 🟢 | Реальный instance и workflow configuration |
| MCP | Streamable HTTP + operation-scoped authorization | Реализовано; typed attributes/artifacts/lifecycle evidence доступно validation и approval preparation | 🟢 | Подключить AI Studio после external E2E |
| Identity | Trusted upstream claims → request-scoped Actor | Gateway contract и ASGI/MCP lifecycle проверены | 🟢 | Подключить реальный IdP/auth proxy |
| Production configuration | Typed settings, env groups, readiness | Реализовано | 🟢 | Staging deployment |
| Object Storage | Крупные бинарные артефакты | Контракт/архитектурная роль определены, production storage не подключён | 🟡 | Выбрать и подключить staging backend |
| Vector Store / RAG | Retrieval поверх инженерной базы | Не реализован | 🔴 | После стабилизации Gateway; не делать Source of Truth |
| AI Studio Agents | Chief Engineer, Requirements, System Architect, Safety, Software Architect, Verification, Configuration, Reviewer, Cost | Не реализованы | 🔴 | После Gateway E2E |
| AI Studio Workflows | Оркестрация агентных шагов | Не реализована | 🔴 | После определения agent contracts |
| Agent contracts | Контракты входов/выходов/границ ответственности агентов | Не реализованы | 🔴 | Спроектировать после фиксации Gateway API |
| Agent governance | AI не может обходить Gateway и выполнять L3 | Gateway-side invariant готов; AI layer отсутствует | 🟡 | Реализовать agent tools только через MCP |
| MVP-1 | Function → System Function → Requirement → Architecture → Allocation → Safety → Verification → Baseline | Полная versioned profile/test chain реализована в `arp4754a@2.0`; production E2E нет | 🟡 | E2E на реальных системах |
| MVP-2 | System Requirement → SW HLR → SW Architecture → SW LLR → Source → Verification → Evidence | Полная versioned profile/test chain реализована в `do-178c@2.0`; production E2E нет | 🟡 | E2E на реальных системах |
| Cost/Budget | Cost Agent / бюджетная модель | В текущем Gateway отсутствует | 🔴 | Отдельно определить контракт и границу ответственности |
| Observability / Operations | Production monitoring, backup, operational procedures | Не является завершённой частью текущего Gateway milestone | 🟡 | После staging E2E |
| Acceptance | Полный quality gate | Production Identity и lifecycle merge подтверждены успешными `quality` и `staging` на `main`; новые этапы требуют собственного CI | 🟢 | Сохранять gate для каждого PR |

## 3. Что уже можно считать закрытым

### Gateway core

Закрыта основная инженерная инфраструктура:

```text
Canonical Model
      +
Profiles
      +
Deterministic Validation
      +
Traceability
      +
Governance
      +
Workspace
      +
Reconciliation
      +
Audit
      +
MCP
      +
Adapter boundaries
      +
Persistence
```

Это соответствует замыслу ТЗ, в котором Gateway является обязательным backend-компонентом, через который проходят управляемые изменения.

### Что принципиально не следует добавлять в Gateway

Не нужно превращать Gateway в:

- LLM runtime;
- вторую систему требований;
- вторую архитектурную модель;
- замену StrictDoc/Capella/OpenProject;
- RAG-хранилище инженерных артефактов.

## 4. Что является главным разрывом

Текущий разрыв находится уже не в базовой архитектуре Gateway, а выше него:

```text
             СЕЙЧАС
                 │
                 ▼
        ┌─────────────────┐
        │ Gateway готов   │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Staging E2E     │  ← следующий инфраструктурный этап
        │ Git/StrictDoc   │
        │ Capella/OP      │
        │ IdP             │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ AI contracts    │
        │ Agents          │
        │ Workflows       │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ RAG / Object    │
        │ Storage / Ops   │
        └─────────────────┘
```

## 5. Цепочки приемки из ТЗ

### MVP-1 — системный уровень

```text
Aircraft Function
        ↓
System Function
        ↓
System Requirement
        ↓
Architecture
        ↓
Allocation
        ↓
Safety
        ↓
Verification
        ↓
Baseline
```

Gateway уже содержит механизмы, необходимые для управления такой цепочкой: canonical graph, profiles, traceability, validation, workspace, reconciliation, approval и baseline.

Не закрыто: доказательство всей цепочки на реальных подключённых системах и через будущий AI orchestration layer.

### MVP-2 — software уровень

```text
System Requirement
        ↓
SW HLR
        ↓
SW Architecture
        ↓
SW LLR
        ↓
Source
        ↓
Verification
        ↓
Evidence
```

В репозитории уже есть DO-178C profile и vertical integration slice.

Не закрыто: production E2E через реальные engineering systems и будущих software/verification agents.

## 6. Приоритет следующей реализации

Порядок не менять без отдельного решения:

1. **Production Identity deployment contract** — завершено
2. **HTTP/ASGI + MCP lifecycle verification** — завершено
3. **Identity documentation** — завершено
4. **Полный quality gate** — подтверждён на `main`
5. **Реальные staging-интеграции Git / StrictDoc / Capella / OpenProject**
6. **Gateway E2E**
7. **Yandex AI Studio Agent contracts**
8. **Agents**
9. **Workflows / orchestration**
10. **RAG / Object Storage / production operations**
11. **Cost/Budget subsystem**

## 7. Критерий перехода к агентам

Переходить к проектированию и реализации агентов следует после выполнения:

```text
Gateway quality gate
        +
production identity boundary
        +
real staging adapters
        +
Gateway E2E
        +
stable MCP contracts
        ↓
AI Agent contracts
```

Иначе агентный слой будет проектироваться поверх неподтверждённого integration boundary.

## 8. Итоговая карта зрелости

```text
                    Архитектура ТЗ
                          │
          ┌───────────────┴───────────────┐
          │                               │
     Gateway layer                   AI layer
          │                               │
       ██████████                     ░░░░░░░░░░
       ██████████                     ░░░░░░░░░░
       ██████████                     ░░░░░░░░░░
       implemented                    planned
          │                               │
          ▼                               ▼
     staging E2E                    agents/workflows
          │                               │
          └───────────────┬───────────────┘
                          ▼
                    Full system E2E
                          │
                          ▼
                       MVP-1/2
```

### Обозначения

- 🟢 — реализовано на уровне текущего Gateway-контракта;
- 🟡 — контракт/часть реализации есть, но production/E2E не завершён;
- 🔴 — ещё не реализовано;
- ⚪ — сознательно вынесено за текущую границу Gateway.
