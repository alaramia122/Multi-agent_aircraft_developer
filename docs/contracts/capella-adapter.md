# Capella adapter contract

## Role

Capella is the authoritative source for architecture-model elements. The Gateway must
not implement a second Capella/EMF parser or duplicate the Arcadia model.

## Integration boundary

`LocalCapellaAdapter` delegates model access to a configured headless bridge. The bridge
is expected to use Capella's native APIs and expose the following JSON protocol over
stdin/stdout:

### Request

```json
{
  "protocol": 1,
  "operation": "get_element | get_version | create_workspace | apply_element | apply_relation",
  "project_path": "...",
  "payload": {}
}
```

### Successful response

```json
{
  "protocol": 1,
  "ok": true
}
```

`get_element` additionally returns `element`, and `get_version` returns `version`.

### Failed response

```json
{
  "protocol": 1,
  "ok": false,
  "error": "..."
}
```

The protocol is intentionally small. It keeps Capella-specific EMF/Arcadia semantics
inside the external bridge while exposing only the Gateway canonical model at the
application boundary.

## Workspace operations

Workspace creation and model mutations are exposed only through the explicit
`WorkspaceAdapter` boundary. Authorization, change gates, approval, and audit remain
Gateway responsibilities; the adapter does not decide whether a mutation is allowed.

Capella is a Java/Eclipse RCP modeling workbench implementing Arcadia. Its official
project documentation describes native model APIs and extension/bridge mechanisms;
the Gateway therefore uses the bridge boundary rather than parsing `.aird` files itself.
