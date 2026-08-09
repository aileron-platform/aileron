---
title: Python Module and Filename Rules
---

# Python Module and Filename Rules

These rules apply to `workspace-manager` and `workspace-runtime`. A directory
expresses domain ownership first; a filename then expresses a role or concept
inside that module.

## Directory names

- Use lowercase `snake_case`.
- Use product vocabulary for domain directories, such as `knowledge_base/`,
  instead of abbreviations such as `kb/`.
- Place domain modules under `app/modules/<domain>/`.
- Place translation implementation and resources under
  `app/modules/localization/`; do not retain a global `translations/`.
- Do not create global horizontal `routers/`, `services/`, `models/`,
  `repositories/`, or `contracts/` taxonomies.
- Do not hide unclear ownership in `common/`, `shared/`, `helpers/`, or `utils/`.
- A shared module exists only when at least two domains own it and it passes the
  deletion test.

## Filenames inside a module

The parent directory already expresses the domain, so filenames do not repeat
the domain prefix:

| Purpose | Prefer | Avoid |
| --- | --- | --- |
| HTTP mapping | `router.py` | `workspace_router.py` |
| Persistence model | `models.py` | `workspace_models.py` |
| Request/response mapping | `schemas.py` | `workspace_schemas.py` |
| Repository implementation | `repository.py` | `workspace_repository_service.py` |
| Explicit domain behavior | `lifecycle.py`, `authorization.py` | `service.py`, `manager.py` |
| External adapter | `oidc_adapter.py`, `http_adapter.py` | `client_helper.py` |
| Module-private policy | `policy.py` or a more precise domain concept | `common.py`, `utils.py` |

A filename describes a role within its ownership instead of stacking technical
suffixes. If `router.py`, `models.py`, or `repository.py` grows too large,
split it by domain concept into a new deep module, not into `router_utils.py` or
`repository_helpers.py`.

## Interface and adapter naming

- Name an interface after its domain capability or port. Do not use vague names
  such as `IService`, `BaseService`, or `AbstractManager`.
- Name an adapter file after the dimension that varies, such as a transport or
  external system.
- Do not introduce a port for symmetry while only one adapter exists. Two
  adapters demonstrate that the seam is real.
- An internal seam may support the owning module's tests, but test convenience
  does not justify exposing it as an external interface.

## Import rules

A cross-domain import targets the owning module's interface. It never
deep-imports another domain's repository, model, or adapter implementation.

```python
# Good: caller depends on the owning module's interface.
from app.modules.workspace.availability import check_workspace_availability

# Avoid: caller assembles another domain's implementation.
from app.modules.workspace.repository import WorkspaceRepository
from app.modules.workspace.policy import WorkspacePolicy
```

`__init__.py` is not a broad re-export barrel. The owning module exposes an
interface from an explicit file.

## Test filenames and locations

```text
tests/
  unit/
    modules/<domain>/test_<behavior>.py
  integration/
    modules/<domain>/test_<behavior>.py
```

- The test tree mirrors domain ownership and follows the domain-module structure.
- A test name describes observable behavior, such as
  `test_start_rejects_stale_revision.py`; a tested class name alone is not
  sufficient information.
- Unit tests verify in-process domain rules. Integration tests verify
  repositories, adapters, local stand-ins, and cross-seam behavior.
- The interface is the test surface. If implementation rearrangement forces a
  test change, first check whether the test reached past the interface.
- Interface tests verify the current module contract. Do not create duplicate or
  unnecessary tests.

## Logs, comments, and i18n

- Python logs and code comments are always in English.
- User-visible messages use existing i18n keys and translation resources.
  Never hard-code Chinese or English in a router, domain implementation, or
  adapter.
- The Localization module owns translation implementation and resources. Other
  modules reference i18n keys; do not copy an identical message or create a
  global `translations/` directory.

## Review checklist

- Does the directory directly identify product ownership?
- Is the interface smaller than the implementation it hides, providing enough
  depth?
- Does the seam have two real adapters, or is it only a predicted replacement
  point?
- Is each dependency classified as in-process, local-substitutable, remote but
  owned, or true external?
- Does the deletion test show that the module provides leverage rather than
  pass-through?
- Do change, defects, knowledge, and tests have locality?
- Does the change retain only current imports, interfaces, necessary production
  code, and necessary tests?
