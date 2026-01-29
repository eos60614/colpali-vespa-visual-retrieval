# Machine-Verifiable Acceptance Criteria — Centralized Logging & Error Handling

> **Blocking Rule:** The LLM must not stop or declare completion until **all checks evaluate to `true`**. Any check that cannot be verified must be marked `false` with a reason.

This checklist is intentionally structured so it can be parsed, evaluated, or audited programmatically.

---

## Verification Schema

All checks must be reported using the following schema **before completion**:

```json
{
  "check": "string",
  "status": true | false,
  "evidence": "string",
  "notes": "string | null"
}
```

---

## 1. Logging Centralization

```json
[
  {"check": "single_backend_logger_exists", "status": false, "evidence": "", "notes": null},
  {"check": "single_frontend_logger_exists", "status": false, "evidence": "", "notes": null},
  {"check": "no_print_or_console_outside_logger", "status": false, "evidence": "", "notes": null},
  {"check": "all_logs_route_through_central_logger", "status": false, "evidence": "", "notes": null}
]
```

---

## 2. Structured Logging Compliance

```json
[
  {"check": "logs_are_structured_objects", "status": false, "evidence": "", "notes": null},
  {"check": "logs_include_required_fields", "status": false, "evidence": "timestamp, level, service, context, correlationId", "notes": null},
  {"check": "error_logs_include_stacktrace", "status": false, "evidence": "", "notes": null},
  {"check": "no_string_only_logs_exist", "status": false, "evidence": "", "notes": null}
]
```

---

## 3. Log Level Enforcement

```json
[
  {"check": "errors_not_logged_as_info_or_debug", "status": false, "evidence": "", "notes": null},
  {"check": "log_levels_normalized", "status": false, "evidence": "debug, info, warn, error, fatal", "notes": null},
  {"check": "fatal_used_only_for_unrecoverable_states", "status": false, "evidence": "", "notes": null}
]
```

---

## 4. Error Propagation & Safety

```json
[
  {"check": "no_empty_catch_blocks", "status": false, "evidence": "", "notes": null},
  {"check": "no_swallowed_errors", "status": false, "evidence": "", "notes": null},
  {"check": "errors_rethrown_or_intentionally_handled", "status": false, "evidence": "", "notes": null},
  {"check": "stack_traces_preserved", "status": false, "evidence": "", "notes": null}
]
```

---

## 5. Frontend Async Guarantees (TypeScript / Next.js)

```json
[
  {"check": "no_unhandled_promise_rejections", "status": false, "evidence": "", "notes": null},
  {"check": "all_async_calls_awaited_or_caught", "status": false, "evidence": "", "notes": null},
  {"check": "api_failures_logged_centrally", "status": false, "evidence": "", "notes": null},
  {"check": "react_error_boundary_present", "status": false, "evidence": "", "notes": null},
  {"check": "nextjs_server_errors_logged", "status": false, "evidence": "", "notes": null}
]
```

---

## 6. Backend Error Boundaries (Python)

```json
[
  {"check": "backend_entrypoints_have_error_boundaries", "status": false, "evidence": "", "notes": null},
  {"check": "backend_logs_full_error_details", "status": false, "evidence": "", "notes": null},
  {"check": "backend_returns_sanitized_errors", "status": false, "evidence": "", "notes": null}
]
```

---

## 7. Correlation ID Integrity

```json
[
  {"check": "correlation_header_standardized", "status": false, "evidence": "x-correlation-id", "notes": null},
  {"check": "frontend_generates_correlation_id", "status": false, "evidence": "", "notes": null},
  {"check": "frontend_attaches_correlation_id", "status": false, "evidence": "", "notes": null},
  {"check": "backend_logs_include_correlation_id", "status": false, "evidence": "", "notes": null},
  {"check": "backend_returns_correlation_id", "status": false, "evidence": "", "notes": null}
]
```

---

## 8. 48-Hour Log Retention Enforcement

```json
[
  {"check": "retention_mechanism_exists", "status": false, "evidence": "", "notes": null},
  {"check": "retention_enforced_at_48_hours", "status": false, "evidence": "", "notes": null},
  {"check": "retention_logic_documented_in_code", "status": false, "evidence": "", "notes": null},
  {"check": "no_logs_persist_beyond_48_hours", "status": false, "evidence": "", "notes": null}
]
```

---

## 9. Environment-Aware Behavior

```json
[
  {"check": "development_fails_loudly", "status": false, "evidence": "", "notes": null},
  {"check": "production_logs_full_errors", "status": false, "evidence": "", "notes": null},
  {"check": "production_returns_safe_responses", "status": false, "evidence": "", "notes": null}
]
```

---

## 10. Security & Data Hygiene

```json
[
  {"check": "no_secrets_logged", "status": false, "evidence": "", "notes": null},
  {"check": "client_error_payloads_sanitized", "status": false, "evidence": "", "notes": null}
]
```

---

## 11. Refactor Discipline

```json
[
  {"check": "business_logic_unchanged", "status": false, "evidence": "", "notes": null},
  {"check": "no_unnecessary_abstractions", "status": false, "evidence": "", "notes": null},
  {"check": "changes_limited_to_logging_and_errors", "status": false, "evidence": "", "notes": null}
]
```

---

## 12. Mandatory Completion Report

Before stopping, the LLM must output a **single JSON array** containing **all checks above**, with:
- `status = true` only when verifiably satisfied
- concrete `evidence` (file paths, symbols, or patterns)
- `notes` explaining assumptions or limitations

**Completion is invalid unless this report is produced.**

---

> **Guiding Principle:** If it cannot be verified, it does not exist.

