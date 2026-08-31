# 016. POSIX/WSL is the mutation support contract

Status: Accepted
Extends: ADR 006

## Context

v0.2.1 already fails closed when `fcntl.flock` is unavailable
(`WriteRefused`). A native-Windows lock backend was deferred. CI is
Linux-only.

## Decision

POSIX and WSL are the mutation support contract for 0.2.2. Native Windows
without `fcntl` refuses mutation. CI adds a Windows (or `fcntl`-missing)
job that **asserts the refusal**, not a lock implementation.

A real native-Windows lock backend is out of 0.2.2.

## Alternatives

- **portalocker / msvcrt.** Rejected: zero-runtime-deps.
- **Continue without a lock on Windows.** Rejected: that was the pre-0.2.1 bug.

## Consequences

Positive: the support matrix matches the code.

Negative: native Windows users cannot enroll/pull/promote until a later
backend.

## Revisit trigger

Reopen if a supported Windows-native path is required (ADR 006).
