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
  +-- current Actor check
  +-- side-effect policy
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
- AI пытается понизить минимальный trust ниже SANDBOX;
- нарушена область проекта;
- операция не зарегистрирована;
- authorization level недостаточен;
- actor identity не совпадает с текущим request-scoped Actor;
- adapter отсутствует;
- инструмент объявлен как PHYSICAL.

## WRITE

Операции записи могут требовать L2. Это не даёт агенту возможности изменить baseline: Gateway governance остаётся отдельной границей.

## PHYSICAL

Физические операции намеренно блокируются общим механизмом. Для них потребуется отдельный safety gate с явным human authorization, ограничениями оборудования и аварийным поведением.

## MCP

MCP использует ToolInvocationService как единственную точку discovery/invocation. MCP handler не дублирует policy: он получает текущего Actor, формирует запрос и передаёт его сервису.

Доступны:

- `list_available_tools`;
- `invoke_engineering_tool`.

Наличие MCP-инструмента не означает наличие права на конкретную операцию: окончательное решение принимается непосредственно перед выполнением.
