# Введение нового разработчика

Этот документ рассчитан на человека, который впервые открыл репозиторий и должен быстро понять, что здесь построено и где продолжать разработку.

## 1. Что это за проект

Это не готовый AI-продукт и не отдельная MBSE/requirements-management система.

Репозиторий содержит инфраструктурное ядро **Engineering Gateway** — слой между AI-агентами и авторитетными инженерными системами.

На текущем этапе завершена реализация Gateway. Следующий этап начинается с интеграции Gateway с Yandex AI Studio и реальными deployment-окружениями.

## 2. Ментальная модель

Запомните четыре слоя:

```text
AI / orchestration
    ↓ MCP
Engineering Gateway
    ↓ adapters
Authoritative engineering systems

PostgreSQL = state of the Gateway, not a second engineering model
```

AI Studio отвечает за агентов и workflow.
Gateway отвечает за детерминированные правила, traceability, validation, governance и controlled changes.
Инженерные системы остаются источниками истины.

## 3. Что читать сначала

Рекомендуемый порядок:

1. [`../README.md`](../../README.md) — текущая стадия и архитектурные ограничения.
2. [`system-overview.md`](system-overview.md) — карта системы и основные сущности.
3. [`architecture.md`](../architecture.md) — детальная архитектура Gateway.
4. [`../architecture/infrastructure-completion.md`](../architecture/infrastructure-completion.md) — точная граница уже завершённой инфраструктуры.
5. [`../development/gateway-completion.md`](../development/gateway-completion.md) — acceptance criteria и явно отложенные работы.
6. [`../contracts/`](../contracts/) — поведение конкретных интерфейсов.
7. [`../verification-matrix.md`](../verification-matrix.md) — как требования сопоставлены с проверками.
8. [`../development/testing-strategy.md`](../development/testing-strategy.md) — организация тестов.

После этого имеет смысл читать код.

## 4. Структура кода

```text
src/engineering_gateway/
├── api/             MCP/HTTP boundary
├── application/     use cases и orchestration
├── domain/          модели, правила, порты и governance
└── infrastructure/  PostgreSQL, adapters, reconciliation и composition
```

### `domain/`

Здесь находятся правила и контракты Gateway, которые не должны зависеть от конкретного HTTP framework или SDK внешней системы.

Основные области:

- canonical engineering model;
- relations;
- profiles;
- traceability;
- change control;
- baselines;
- workspaces;
- reconciliation;
- audit;
- adapter ports.

### `application/`

Здесь находятся сценарии использования Gateway:

- работа с канонической моделью;
- profile operations;
- deterministic validation;
- governed operations;
- Change Request;
- workspace lifecycle;
- reconciliation.

### `infrastructure/`

Здесь находятся реализации портов:

- SQLAlchemy/PostgreSQL;
- Git;
- StrictDoc;
- Capella bridge;
- OpenProject;
- workspace changes;
- reconciliation;
- transaction boundaries;
- adapter composition.

### `api/`

Здесь находится MCP surface. MCP предоставляет интерфейс для AI Studio, но не должен становиться отдельным источником governance rules.

## 5. Как проходит изменение

Для понимания большей части системы достаточно проследить один сценарий:

```text
1. Есть approved baseline
2. Создаётся Change Request
3. Создаётся workspace
4. В workspace вносятся L2 изменения
5. Формируется canonical change set
6. Запускается deterministic validation
7. Изменения reconciled во внешние workspace'ы
8. Проверяются свежесть validation/reconciliation evidence
9. Workspace становится READY_FOR_APPROVAL
10. Человек выполняет L3 approval
11. Формируется новая immutable baseline
```

Ключевой момент: **AI не может перескочить с изменения workspace к утверждённой baseline.**

## 6. Где находятся стандарты

Профили находятся в `profiles/`.

Сейчас репозиторий содержит минимальные executable slices для:

- ARP4754A;
- DO-178C.

Это не копии нормативных документов. Профиль содержит машиночитаемые правила, необходимые Gateway для validation/governance.

Новые стандарты должны добавляться как конфигурация профиля, а не через hardcoded ветвления в агенте или Gateway core.

## 7. Как Gateway взаимодействует с внешними системами

Gateway использует adapter contracts.

| Adapter | Ответственность |
|---|---|
| Git | snapshot, ancestry, immutable tags |
| StrictDoc | чтение/version operations и mutation bridge contract |
| Capella | headless bridge contract |
| OpenProject | Change Request / work-package operations |

Concrete production bridge executables/endpoints пока не входят в завершённый Gateway milestone.

## 8. MCP

MCP — внешний интерфейс Gateway для AI Studio.

L0/L1 read/propose операции и L2 workspace operations могут быть доступны через MCP в соответствии с authorization.

L3 approval/rejection через MCP не предоставляются.

Identity transport-level пользователя/агента преобразуется deployment-слоем в Gateway Actor через `ActorProvider`. MCP annotations сами по себе полномочия не дают.

## 9. Где хранится состояние

PostgreSQL содержит:

- Gateway references;
- workflow state;
- profile provenance;
- baseline provenance;
- validation evidence;
- reconciliation evidence;
- audit;
- coordination state.

PostgreSQL **не должен превращаться в копию** содержимого StrictDoc/Capella/Git.

Vector Store также не является источником инженерной истины.

## 10. Как безопасно продолжать разработку

Перед изменением архитектурно значимого поведения:

1. Найдите соответствующий contract в `docs/contracts/`.
2. Проверьте, не входит ли изменение в frozen Gateway boundary.
3. Проверьте domain/application/infrastructure разделение.
4. Добавьте или измените тесты соответствующего уровня.
5. Для governance/compliance не переносите критическое правило в LLM prompt или Agent Workflow.
6. Не добавляйте approval capability AI-актору.
7. Для внешних side effects сохраняйте deterministic identity и idempotency.
8. Не переносите authoritative engineering data в PostgreSQL без отдельного архитектурного решения.

## 11. Следующая большая фаза

После завершения Gateway логичный порядок работ:

```text
Gateway complete
      ↓
Documentation / onboarding
      ↓
Deployment foundation
      ↓
Real Git / StrictDoc / Capella / OpenProject integration
      ↓
Yandex AI Studio MCP integration
      ↓
Agents + Workflows
      ↓
Knowledge / Object Storage / retrieval
      ↓
User interface
      ↓
End-to-end validation
```

Важно: это порядок **разработки системы**, а не перечень недостающих функций Gateway.
