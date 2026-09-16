# Архитектура Engineering Gateway

## Назначение

Engineering Gateway — детерминированный слой интеграции и governance между AI-агентами и авторитетными инженерными системами.

Gateway координирует Git, StrictDoc, Capella и OpenProject, не превращая PostgreSQL или собственный граф в ещё одну авторитетную инженерную модель.

Текущая реализация построена слоями:

1. application services;
2. canonical engineering model и traceability graph;
3. PostgreSQL metadata/workflow state;
4. Standard Profile Engine;
5. deterministic validation;
6. change, reconciliation, approval и baseline gates;
7. external-system adapters;
8. MCP boundary для AI Studio.

## Каноническая модель

`EngineeringElement` содержит:

- стабильный Gateway UUID;
- semantic element kind и profile type ID;
- человекочитаемое имя;
- authoritative external system и external ID;
- source URI, если доступен.

`EngineeringRelation` соединяет канонические ссылки на элементы.

Gateway не превращает эти ссылки в копию модели StrictDoc, Capella или Git.

## Standard Profile Engine

Standard Profile — исполняемая конфигурация, описывающая:

- типы элементов;
- атрибуты;
- допустимые отношения;
- lifecycle;
- требования к артефактам;
- traceability rules;
- verification rules.

Профили версионируются и активируются явно. Ядро Gateway не содержит standard-specific ветвлений вроде `if arp4754a` или `if do_178c`.

Профили можно композиционно расширять или заменять без изменения core governance implementation.

В репозитории есть минимальные executable slices для ARP4754A и DO-178C. Они не являются воспроизведением текста нормативных документов.

## Deterministic Validation

`DeterministicValidationEngine` проверяет canonical graph и явные authoritative evidence относительно активного профиля.

Результат содержит стабильные issue codes и SHA-256 hash validation graph.

Проверяются:

- согласованность element type/kind;
- duplicate IDs и external identities;
- наличие и типы атрибутов;
- dangling и запрещённые отношения;
- duplicate relations;
- обязательная/запрещённая traceability;
- verification requirements;
- lifecycle state и transition;
- required artifact evidence.

LLM может предложить evidence или анализ, но не является источником compliance truth.

## Traceability

`TraceabilityGraph` предоставляет детерминированные graph queries и diagnostics.

Основные типы gap:

- `missing_required`;
- `forbidden_present`;
- `wrong_relation_type`;
- `wrong_target_type`;
- `dangling_source`;
- `dangling_target`.

Диагностический слой не зависит от конкретного инженерного инструмента.

## Change / approval flow

```text
Approved Baseline
      |
      v
Change Request (OpenProject)
      |
      v
Workspace
      |
      v
L2 modifications
      |
      v
Deterministic validation
      |
      v
Reconciliation
      |
      v
READY_FOR_APPROVAL
      |
      v
Human L3 approval
      |
      v
New immutable Baseline
```

Перед approval validation/reconciliation evidence должны соответствовать текущему change set. Устаревшее состояние не может быть promoted в baseline.

Approved baseline неизменяем. Следующее изменение создаёт новый controlled flow.

## Authorization

| Уровень | Значение | Предполагаемый актор |
|---|---|---|
| L0 | READ | человек или AI |
| L1 | PROPOSE | AI или человек |
| L2 | MODIFY_WORKSPACE | авторизованный инженерный актор / AI-agent |
| L3 | APPROVE | только человек |

Authorization проверяется Gateway независимо от MCP annotations.

MCP не предоставляет operations approve/reject.

## Transaction boundary

Governed application operations используют unit-of-work transaction:

- успешная операция → commit;
- exception → rollback.

Audit для failure/denial может записываться независимой сессией, чтобы rollback бизнес-транзакции не удалил доказательство отказа или сбоя.

## External adapters

- **Git** — snapshot, ancestry, immutable tag operations.
- **StrictDoc** — read/version operations через CLI и отдельный mutation bridge contract.
- **OpenProject** — Change Request/work-package operations через HTTP API с idempotency protection.
- **Capella** — headless bridge protocol; EMF/Capella-specific APIs остаются внутри bridge.

Composition layer различает read capabilities и workspace-mutation capabilities и отклоняет конфликтующие registrations.

Relations reconciled в authoritative system target element. Это важно для cross-tool traceability: например, связь requirement → architecture применяется к архитектурной системе, а не автоматически к системе источника связи.

## MCP / AI Studio boundary

MCP server предоставляет read-only tools для:

- получения инженерного элемента;
- получения его relations;
- deterministic graph validation.

При L2 authorization доступны workspace mutation и governed reconciliation/preparation operations.

Approval/rejection намеренно отсутствуют в MCP.

Deployment layer отвечает за привязку identity пользователя/agent к Gateway Actor через `ActorProvider`. Gateway остаётся ответственным за authorization и governance.

## Reproducibility

Baseline содержит Git repository/commit/tag и необходимые версии внешних систем. Перед созданием baseline проверяется Git ancestry.

Validation hashes включают profile definition, canonical elements/relations и validation evidence, чтобы approval мог обнаружить устаревшие результаты.
