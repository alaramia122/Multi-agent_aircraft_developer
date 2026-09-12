# OpenProject adapter contract

## Role

OpenProject is the authoritative external system for change-management work packages.
The Gateway stores only the canonical change element, external identifier, references,
and Gateway state required for governance.

## API boundary

`LocalOpenProjectAdapter` uses OpenProject API v3 over HTTPS. The adapter does not
implement a second project-management model.

Supported operations in the current vertical slice:

- read a work package by external ID;
- read the OpenProject instance version;
- create a change-request work package in a configured project and work-package type;
- update a work-package status using OpenProject optimistic locking.

OpenProject API v3 requires `lockVersion` on work-package PATCH operations. The
adapter therefore reads the current work package before changing its status.

## Configuration

- `base_url`: OpenProject instance URL;
- `api_token`: API token used for HTTP Basic authentication with the `apikey` username;
- `project_id`: target OpenProject project;
- `change_request_type_id`: work-package type used for Gateway change requests;
- `timeout_seconds`: HTTP request timeout.

The adapter performs no authorization or approval decision. Those decisions remain
Gateway responsibilities.
