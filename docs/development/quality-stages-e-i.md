# Контракты качества E–I

Этот документ фиксирует результат этапов E–I для Gateway. Он не расширяет
доменную модель и не заменяет внешние инженерные системы.

## E — API contract hardening

Публичные HTTP-границы используют HTTP-семантику:
- 401 — отсутствует или недействителен human bearer token;
- 403 — identity аутентифицирована, но недостаточно полномочий;
- 404 — объект не принадлежит текущему пользователю или не существует;
- 409 — операция Gateway отклонена из-за состояния, конфликта или нарушения governance-контракта;
- 413 — контекст превышает ограничение операции;
- 429 — превышен лимит обращения к ассистенту;
- 502 — внешний AI/интеграционный сервис вернул неприемлемый результат;
- 503 — требуемая интеграция не сконфигурирована.

Необработанные GatewayServiceError не должны выходить наружу как 500 из human API.
MCP transport authentication и Gateway authorization остаются отдельными границами.

## F — bridge contracts

StrictDoc/Capella используют единый versioned JSON envelope v1.
Успешный ответ обязан содержать protocol, точное operation и boolean ok=true.
Ошибка обязана содержать непустой error. error запрещён в успешном ответе.
Неверный JSON, неизвестная версия, неправильная операция, неверный тип ok, пустая
ошибка, timeout и ненулевой exit code являются отказом.

Native bridges нормализуют ответ до этого envelope до передачи в общий validator.
Gateway не интерпретирует EMF/Capella или SDoc как собственную модель.

## G — configuration/deployment

Все runtime-настройки проходят через Settings и вложенные Pydantic-модели.
Переменные окружения используют GROUP__FIELD: DATABASE__URL,
OPENPROJECT__API_TOKEN, STRICTDOC__PROJECT_PATH и т. д.

Включённая интеграция без обязательных параметров должна завершаться fail-closed.
Секреты представлены SecretStr и не должны попадать в repr/config dump.
L3 нельзя выдать AI/service-token конфигурацией.

## H — real integrations

Локальные integration/contract tests доказывают программный контракт и retry/idempotency,
но не доказывают наличие конкретной staging-инсталляции. Реальный OpenProject,
StrictDoc и Capella подтверждаются отдельным deployment verification на staging.
Capella остаётся отключённым до предоставления контролируемой целевой UAV-модели.

## I — final quality gate

Финальный gate: Ruff, mypy, полный pytest, PostgreSQL integration, migration bootstrap,
staging compose smoke test и governed E2E. Статус CI считается доказательством только
для конкретного commit SHA. Реальный staging verification фиксируется отдельно.