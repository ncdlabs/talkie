# Code Quality & Cleanup Audit

Comprehensive search and cleanup of duplicate, unused, and inefficient code.

## 1. Duplicate Code Detection
- Search for duplicate functionality across `app/`, module servers (`modules/*/server.py`), and API clients (`modules/api/`)
- Identify duplicate business logic in `app/`, `modules/` (browser, rag, speech), `persistence/`, `llm/`, `profile/`, `curation/`, and `sdk/`
- Locate duplicate logic in `web/` assets and scripts (if any)
- Find duplicate persistence queries and repo patterns in `persistence/`
- Identify duplicate validation or parsing logic

## 2. Unused Code Identification
- Find dead code (never executed)
- Identify unused imports and dependencies (Pipfile / requirements)
- Locate unused entry points and module servers or endpoints
- Find unused web assets
- Identify unused schema or repo code (unused tables/columns)
- Find unused configuration options in `config.yaml` and module configs

## 3. Code Consolidation
- **SAFELY** consolidate duplicate functionality into `sdk/` or shared helpers in `app/`
- Create shared base classes for modules (e.g. `modules/speech/stt/base.py`) and consistent API client patterns in `modules/api/`
- Use shared abstractions in `app/abstractions.py` and `sdk/abstractions.py` instead of duplicating logic
- Consolidate common operations into utility modules where appropriate

## 4. Cleanup Actions
- Remove unused imports and dependencies
- Delete dead code and unreachable branches
- Remove unused entry points and module endpoints
- Clean up unused schema or repo code
- Remove unused configuration options
- Delete unused assets and files

## 5. Refactoring Opportunities
- Extract common patterns into base classes and ABCs in `sdk/` or module `base.py` files
- Implement clear inheritance and shared interfaces (e.g. `app/abstractions.py`, `sdk/abstractions.py`)
- Consolidate similar validation or parsing logic
- Align repo and client patterns across persistence and modules

## 6. Testing & Validation
```bash
# Run tests
pipenv run pytest tests/ -v

# Lint and format (optional)
pipenv run ruff check .
pipenv run ruff format .

# Type checking (optional, if used)
pipenv run mypy .
```

## 7. Documentation Update
- Update API documentation for removed or changed endpoints (e.g. `docs/MODULE_API.md`, `docs/SDK.md`)
- Document consolidated utilities and shared modules
- Update development guidelines and `MODULES.md` or `README.md` as needed
- Record cleanup actions in changelog

## Goals
- Reduce codebase size by removing duplicates
- Improve maintainability and readability
- Eliminate technical debt
- Maintain all existing functionality
- Establish code quality standards
