# Canonical model contract

## Engineering Element

Every canonical element has:

- stable Gateway identifier;
- profile-controlled `type_id`;
- canonical category (`ElementKind`);
- display name;
- source system identifier;
- external identifier;
- optional source URI.

The model intentionally does not copy the complete source object. Source systems remain authoritative for their respective engineering content.

## Planned typed relations

Relations will be implemented as first-class canonical graph edges with:

- relation type;
- source element;
- target element;
- source-system reference when applicable;
- profile provenance;
- lifecycle/validity metadata;
- audit information for changes.

The relation vocabulary is profile-controlled rather than hardcoded to one standard.
