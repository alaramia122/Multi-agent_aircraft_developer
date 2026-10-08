# Политика вызова внешних инструментов

Вызов инструмента выполняется в два этапа: выбор из Tool Registry и повторная авторизация непосредственно перед выполнением.

## Граница вызова

```
Agent
  |
  | tool_id + operation + arguments
  v
ToolInvocationService
  |
  +-- registry lookup
  +-- enabled check
  +-- trust-level check
  +-- project scope check
  +-- operation lookup
  +-- Actor authorization check
  +-- physical side-effect safety gate
  |
  v
ToolExecutionAdapter
  |
  v
external tool
```

Агент не получает ссылку на исполняемый объект. Он передаёт только идентификатор инструмента и операции.

## Fail-closed

Вызов отклоняется, если:

- инструмент отсутствует;
- инструмент отключён;
- trust level ниже требуемого;
- нарушена область проекта;
- операция не зарегистрирована;
- authorization level недостаточен;
- adapter отсутствует;
- инструмент объявлен как PHYSICAL.

## WRITE

Операции записи могут требовать L2. Это не даёт агенту возможности изменить baseline: Gateway governance остаётся отдельной границей.

## PHYSICAL

Физические операции пока намеренно полностью блокируются этим общим механизмом. Для них потребуется отдельный safety gate с явным human authorization, ограничениями оборудования и аварийным поведением.

## Следующий слой

После стабилизации этого контракта можно добавить MCP-инструмент discovery/invocation. Он должен использовать тот же сервис, а не дублировать policy в MCP handler.
