# Карта контрактов Engineering Gateway

Этот документ — русскоязычная карта каталога `docs/contracts/`. Он не заменяет нормативные англоязычные контракты: они остаются каноническим описанием интерфейсов и инвариантов. Цель карты — быстро понять, **какой контракт за что отвечает, где проходит граница ответственности и в каком порядке читать документацию**.

## 1. Как читать контракты

Рекомендуемый порядок:

1. `canonical-model.md` — что Gateway считает инженерным объектом и связью.
2. `ports.md` — какие абстрактные порты используются между application/domain и инфраструктурой.
3. `standard-profiles.md` — как описываются стандарты и правила без зашивания стандартов в код.
4. `traceability-validation.md` — как проверяется трассируемость.
5. `change-control-audit.md` — как устроены изменения, права и аудит.
6. `reconciliation-coordination.md` и `transaction-boundary.md` — как безопасно сохраняются изменения и координируется публикация во внешние системы.
7. `strictdoc-adapter.md`, `capella-adapter.md`, `openproject-adapter.md` — контракты конкретных внешних систем.
8. `mcp-gateway.md` и `mcp-actor-provisioning.md` — внешний MCP-интерфейс и получение доверенной идентичности.

Контракты следует читать вместе с [обзором системы](system-overview.md), [архитектурой](architecture.md) и [описанием завершения Gateway](../development/gateway-completion.md).

---

## 2. Каноническая инженерная модель

### `canonical-model.md`

**Отвечает на вопрос:** что хранит и предоставляет сам Gateway?

Основные сущности:

- `EngineeringElement` — стабильная Gateway-идентичность инженерного объекта и ссылка на его authoritative external object;
- `EngineeringRelation` — типизированное направленное ребро между элементами;
- `TraceabilityGraph` — запросный слой над элементами и связями.

Ключевой принцип: Gateway **не является второй системой управления инженерными моделями**. Содержимое объекта остаётся у исходной системы. PostgreSQL хранит ссылки, отношения и состояние самого Gateway.

Для трассируемости определены детерминированные категории диагностик: отсутствующая обязательная связь, запрещённая связь, неправильный тип связи, неправильный тип цели и dangling endpoints.

**Связи с другими контрактами:** модель используется профилями, Validation Engine, traceability и persistence.

---

## 3. Порты и границы приложения

### `ports.md`

**Отвечает на вопрос:** через какие интерфейсы application/domain-код обращается к инфраструктуре?

Это основной контракт Dependency Inversion: бизнес-логика не должна зависеть непосредственно от Git, PostgreSQL, StrictDoc, Capella или OpenProject.

Практически порт можно рассматривать как точку, в которой Gateway говорит: «мне нужна такая операция», а инфраструктурный адаптер решает, как выполнить её в конкретной системе.

**Читать этот файл вместе с adapter-контрактами:** конкретный адаптер должен реализовать соответствующий порт, не меняя application-level семантику.

---

## 4. Standard Profile Engine

### `standard-profiles.md`

**Отвечает на вопрос:** как сделать требования стандартов конфигурируемыми?

Профиль — декларативное описание:

- типов инженерных элементов и атрибутов;
- допустимых отношений;
- жизненных циклов и переходов;
- требуемых артефактов;
- правил трассируемости;
- требований верификации;
- метаданных.

Важный инвариант: в ядре Gateway не должно появляться ветвлений вида `if standard == ...`. Профили регистрируются как неизменяемые `(id, version)`, проходят семантическую проверку и отдельно активируются.

Профили можно композиционировать по стабильным идентификаторам определений. Конфликтующие определения отклоняются детерминированно; неявного порядка переопределения нет.

**Граница ответственности:** Profile Engine проверяет корректность самого профиля. Он **не определяет соответствие конкретного проекта стандарту** — это делает Deterministic Validation Engine.

---

## 5. Трассируемость и детерминированная валидация

### `traceability-validation.md`

**Отвечает на вопрос:** как проверяется, что необходимые инженерные связи существуют и корректны?

Контракт задаёт границу между декларативными правилами трассируемости и их детерминированной оценкой на каноническом графе.

Результат должен быть пригоден для воспроизводимого процесса: одинаковое состояние проекта, профиль и входные данные дают одинаковые диагностические результаты.

Это часть более широкого Deterministic Validation Engine, который также проверяет типы элементов, внешние идентификаторы, атрибуты, отношения, lifecycle, artifact evidence и verification requirements.

---

## 6. Изменения, полномочия и аудит

### `change-control-audit.md`

**Отвечает на вопрос:** кто и на каких этапах может менять инженерное состояние?

Модель полномочий:

| Уровень | Назначение |
|---|---|
| L0 | READ — чтение |
| L1 | PROPOSE — предложение изменения |
| L2 | MODIFY_WORKSPACE — изменение рабочего пространства |
| L3 | APPROVE — утверждение человеком |

Критическое правило: **AI не получает L3**. Approval/rejection не предоставляются через MCP.

Контракт также связывает изменение с Change Request, Workspace, baseline provenance и аудитом. Утверждённое состояние не должно изменяться обычной операцией workspace.

---

## 7. Reconciliation и транзакционные границы

### `reconciliation-coordination.md`

**Отвечает на вопрос:** как несколько процессов безопасно публикуют один и тот же change set во внешние системы?

Ключевые механизмы:

- детерминированная идентичность change set;
- идемпотентность адаптеров;
- координация через PostgreSQL advisory lock;
- безопасный повтор после частичной публикации;
- повторное использование уже зафиксированного reconciliation evidence.

Цель — не допустить двойного применения одного изменения и обеспечить предсказуемое поведение после ошибок или повторного запуска.

### `transaction-boundary.md`

**Отвечает на вопрос:** где проходит граница SQL-транзакции Gateway?

Операции Gateway должны использовать operation-scoped transaction boundary. Состояние Gateway фиксируется атомарно внутри PostgreSQL-транзакции там, где это предусмотрено контрактом; внешние системы не становятся частью SQL-транзакции.

Поэтому согласование с Git/StrictDoc/Capella/OpenProject строится через явное reconciliation evidence и retry/idempotency semantics, а не через попытку сделать распределённую ACID-транзакцию.

---

## 8. Внешние адаптеры

### `strictdoc-adapter.md`

**Граница:** requirements / verification domain через StrictDoc.

Адаптер отделяет Gateway от конкретного CLI/API способа работы со StrictDoc. Чтение и изменение должны соответствовать явно определённому versioned mutation bridge.

### `capella-adapter.md`

**Граница:** архитектурная модель через Capella.

Адаптер отвечает за взаимодействие с headless Capella bridge. Gateway получает/публикует данные через контракт адаптера, не превращая внутреннюю модель Gateway в копию Capella.

### `openproject-adapter.md`

**Граница:** Change Request / change-management через OpenProject.

Адаптер инкапсулирует API v3, optimistic locking и idempotency semantics. Gateway использует его для управления процессом изменений, а не как замену собственному governance state.

---

## 9. MCP

### `mcp-gateway.md`

**Отвечает на вопрос:** что Gateway предоставляет агентам через MCP?

MCP является внешним интерфейсом Gateway, а не отдельным бизнес-слоем. Доступ разделяется по capability level:

- L0/L1 — чтение и подготовка предложений;
- L2 — операции рабочего пространства и reconciliation;
- L3 — отсутствует в MCP.

Используется trusted `ActorProvider`; MCP annotations сами по себе не являются механизмом авторизации.

### `mcp-actor-provisioning.md`

**Отвечает на вопрос:** откуда Gateway получает доверенную идентичность вызывающего субъекта?

Контракт отделяет identity/authentication от MCP business operations. Production identity provider и конкретная схема развёртывания остаются инфраструктурной задачей, а не частью Gateway completion boundary.

---

## 10. Сводная карта ответственности

| Область | Канонический контракт | Основная ответственность |
|---|---|---|
| Инженерные объекты и связи | `canonical-model.md` | Identity, graph, relations, external references |
| Архитектура зависимостей | `ports.md` | Application/domain ↔ infrastructure boundaries |
| Стандарты | `standard-profiles.md` | Declarative profiles, composition, activation |
| Трассируемость | `traceability-validation.md` | Deterministic traceability evaluation |
| Governance | `change-control-audit.md` | Authorization, CR/workspace, audit, immutable baseline |
| Reconciliation | `reconciliation-coordination.md` | Concurrency, replay, idempotency, publication coordination |
| SQL-транзакции | `transaction-boundary.md` | Unit of Work and transaction scope |
| Requirements | `strictdoc-adapter.md` | StrictDoc integration boundary |
| Architecture model | `capella-adapter.md` | Capella integration boundary |
| Change management | `openproject-adapter.md` | OpenProject integration boundary |
| Agent interface | `mcp-gateway.md` | MCP operations and capability boundary |
| Identity | `mcp-actor-provisioning.md` | Trusted actor provisioning |

---

## 11. Главное архитектурное правило

Если при реализации новой функции возникает желание:

- добавить в Gateway копию данных StrictDoc/Capella/OpenProject;
- зашить конкретный стандарт в Python-код;
- дать агенту возможность самостоятельно выполнить L3 approval;
- обойти порт и напрямую вызвать внешний сервис из domain/application;
- сделать внешний side effect частью обычной SQL-транзакции;

сначала нужно проверить соответствующий контракт в `docs/contracts/`. В текущей архитектуре эти решения противоречат установленным границам.

## 12. Следующий уровень документации

После этой карты для работы с кодом достаточно перейти к конкретному контракту, а затем к его реализации в `src/` и тестам.

Для нового разработчика рекомендуемый маршрут:

`docs/ru/onboarding.md`
→ `docs/ru/architecture.md`
→ `docs/ru/contracts-map.md`
→ конкретный `docs/contracts/*.md`
→ соответствующие `src/domain`, `src/application`, `src/infrastructure` и `tests`.
