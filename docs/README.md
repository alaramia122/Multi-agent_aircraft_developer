# Documentation / Документация

The repository uses English as the canonical language for detailed engineering contracts and Russian as a parallel onboarding and system-description language.

## Start here

| Document | Purpose |
|---|---|
| [`ru/system-overview.md`](ru/system-overview.md) | Краткая карта системы: что это, из чего состоит и где проходит граница Gateway |
| [`ru/onboarding.md`](ru/onboarding.md) | Пошаговое введение нового разработчика в проект |
| [`ru/architecture.md`](ru/architecture.md) | Русское описание архитектуры Engineering Gateway |
| [`ru/contracts-map.md`](ru/contracts-map.md) | Русская карта интерфейсных и поведенческих контрактов Gateway |
| [`architecture.md`](architecture.md) | English architecture reference |
| [`architecture/infrastructure-completion.md`](architecture/infrastructure-completion.md) | Frozen Gateway completion boundary |
| [`development/gateway-completion.md`](development/gateway-completion.md) | Gateway milestone, acceptance criteria and deferred work |
| [`development/contract-implementation-matrix.md`](development/contract-implementation-matrix.md) | Contract → implementation → tests verification matrix |
| [`verification-matrix.md`](verification-matrix.md) | Verification coverage and acceptance mapping |
| [`development/testing-strategy.md`](development/testing-strategy.md) | Test organization and verification approach |
| [`deployment/production-integration.md`](deployment/production-integration.md) | Post-Gateway production integration foundation and rollout order |
| [`deployment/production-configuration.md`](deployment/production-configuration.md) | Typed runtime configuration groups, environment variables, validation and secret handling |
| [`contracts/`](contracts/) | Stable interfaces and behavioral contracts |

## Documentation layers

```text
System overview
      ↓
Architecture
      ↓
Core concepts and functional flow
      ↓
Interfaces / contracts
      ↓
Governance and validation
      ↓
Development and testing
      ↓
Deployment and external integration
      ↓
AI Studio Agents / Workflows
```

The first three documents are intended to give a new contributor the project mental model before they read implementation details.

## Language policy

- English documents remain the canonical detailed contract where an existing document already defines an implementation interface or acceptance criterion.
- Russian documents provide equivalent explanations for onboarding, architecture and system usage concepts.
- When a contract is changed, its canonical English version and the corresponding Russian documentation must be kept synchronized.
- Russian documentation must not silently introduce behavior that is absent from the implementation or the English contract.
