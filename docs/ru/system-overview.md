# Обзор системы

## 1. Назначение проекта

**Multi-agent Aircraft Developer** — инфраструктура для мультиагентной системы поддержки системной инженерии беспилотного летательного аппарата.

Система должна позволять AI-агентам работать с инженерными артефактами и процессами, не превращая LLM в источник истины и не позволяя ей обходить инженерное управление.

Ключевой принцип:

> AI предлагает и выполняет разрешённые операции, а критические инженерные инварианты проверяются детерминированным кодом, а утверждение базовой линии остаётся за человеком.

## 2. Общая архитектура

```text
                    Yandex AI Studio
              ┌─────────┴─────────┐
              │ Agents / Workflows│
              │ Knowledge / UI    │
              └─────────┬─────────┘
                        │ MCP
                        ▼
              ┌───────────────────┐
              │ Engineering       │
              │ Gateway            │
              │                   │
              │ Validation        │
              │ Traceability      │
              │ Governance        │
              │ Workspace         │
              │ Reconciliation    │
              │ Audit             │
              └───────┬───────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
      Git         StrictDoc      Capella
        │             │             │
        └─────────────┼─────────────┘
                      ▼
                 OpenProject
                      │
                 PostgreSQL
```

На текущем этапе реализована нижняя часть схемы — **Engineering Gateway** и его границы интеграции. Настройка Yandex AI Studio, production-authentication, реальные bridge-процессы и эксплуатационная инфраструктура относятся к следующим этапам.

## 3. Роль Engineering Gateway

Gateway — не замена инженерным системам.

| Система | Роль |
|---|---|
| Git | Источник истины для своих артефактов, история, ancestry и immutable tags |
| StrictDoc | Авторитетное хранение требований |
| Capella | Авторитетное архитектурное/MBSE-хранилище |
| OpenProject | Управление Change Request / work package |
| PostgreSQL | Состояние Gateway, ссылки, workflow, provenance, validation/reconciliation evidence и audit |
| Object Storage | Крупные бинарные инженерные артефакты |
| Vector Store | Поиск/извлечение знаний; **не** источник истины |
| Engineering Gateway | Интеграция, трассируемость, детерминированная проверка и governance |

Gateway хранит ссылки и управляющее состояние, а не вторую копию инженерной модели.

## 4. Основные сущности

### EngineeringElement

Лёгкая каноническая ссылка на инженерный объект:

- стабильный UUID Gateway;
- тип/вид элемента;
- профильный type ID;
- имя;
- авторитетная внешняя система;
- внешний ID;
- source URI, если доступен.

### EngineeringRelation

Типизированная направленная связь между каноническими элементами.

Gateway использует граф связей для проверки и трассируемости, но не превращает его в копию модели StrictDoc или Capella.

### Standard Profile

Версионируемая конфигурация, описывающая:

- типы элементов;
- атрибуты и их схемы;
- допустимые отношения;
- lifecycle;
- требования к артефактам;
- правила трассируемости;
- правила verification.

Профиль активируется явно и используется ядром Gateway без hardcode вида `if arp4754a` / `if do_178c`.

### Change Request

Контролируемое изменение, связанное с OpenProject и workspace.

### Workspace

Изолированная область изменений относительно approved baseline. Изменения сначала попадают в workspace и только после проверок могут быть подготовлены к утверждению.

### Baseline

Неизменяемое утверждённое состояние инженерной системы с зафиксированным provenance, включая Git commit/tag и необходимые версии внешних систем.

## 5. Основной инженерный поток

```text
Approved Baseline
       ↓
Change Request
       ↓
Workspace
       ↓
L2 modifications
       ↓
Deterministic Validation
       ↓
Reconciliation
       ↓
READY_FOR_APPROVAL
       ↓
Human L3 Approval
       ↓
New immutable Baseline
```

Если validation или reconciliation устарели относительно change set, workspace нельзя перевести в утверждённую baseline.

## 6. Уровни полномочий

| Уровень | Операция | Кто может выполнять |
|---|---|---|
| L0 | READ | человек или AI |
| L1 | PROPOSE | AI или человек |
| L2 | MODIFY_WORKSPACE | авторизованный инженерный актор / AI-agent |
| L3 | APPROVE | только человек |

MCP annotations не являются механизмом безопасности. Authorization определяется Gateway.

Операции approve/reject намеренно не представлены как MCP tools.

## 7. Что уже реализовано

На текущей ветке завершена инфраструктурная фаза Gateway:

- каноническая модель инженерных ссылок и типизированных связей;
- PostgreSQL persistence;
- Standard Profile Engine;
- deterministic traceability и validation;
- Change Request / Workspace lifecycle;
- optimistic concurrency;
- human-only approval governance;
- immutable baseline provenance;
- audit;
- Git / StrictDoc / Capella / OpenProject adapter boundaries;
- retry-safe reconciliation;
- PostgreSQL coordination;
- MCP Streamable HTTP boundary с trusted ActorProvider;
- unit, contract и PostgreSQL-backed integration tests.

## 8. Что ещё не является частью Gateway

Следующие работы не следует искать как «недоделанные функции Gateway»:

1. настройка Yandex AI Studio Agents;
2. настройка Yandex AI Studio Workflows;
3. production identity provider и MCP authentication deployment;
4. конкретные production endpoints/bridge executables для StrictDoc и Capella;
5. deployment Object Storage;
6. knowledge retrieval / Vector Store;
7. production observability, backup и operations;
8. пользовательский интерфейс поверх AI Studio или отдельного приложения.

Это следующий слой системы.

## 9. Где искать детали

- Архитектура: [`../architecture.md`](../architecture.md)
- Граница завершённого Gateway: [`../architecture/infrastructure-completion.md`](../architecture/infrastructure-completion.md)
- Acceptance criteria: [`../development/gateway-completion.md`](../development/gateway-completion.md)
- Контракты: [`../contracts/`](../contracts/)
- Стратегия тестирования: [`../development/testing-strategy.md`](../development/testing-strategy.md)
- Верификация: [`../verification-matrix.md`](../verification-matrix.md)
