---
name: error-handling-patterns
description: Master error handling patterns across languages including exceptions, Result types, error propagation, and graceful degradation to build resilient applications. Use when implementing error handling, designing APIs, or improving application reliability.
---

# Error Handling Patterns

## When to use this skill
- Implementing error handling in new features
- Designing error-resilient APIs
- Debugging production issues
- Improving application reliability
- Creating better error messages for users and developers
- Implementing retry and circuit breaker patterns
- Handling async/concurrent errors
- Building fault-tolerant distributed systems

## Core Concepts

### 1. Error Handling Philosophies
**Exceptions vs Result Types:**
- **Exceptions**: Traditional try-catch, disrupts control flow. Use for unexpected errors or exceptional conditions.
- **Result Types**: Explicit success/failure, functional approach. Use for expected errors or validation failures.
- **Panics/Crashes**: Unrecoverable errors, programming bugs.

### 2. Error Categories
**Recoverable Errors:**
- Network timeouts
- Missing files
- Invalid user input
- API rate limits

**Unrecoverable Errors:**
- Out of memory
- Stack overflow
- Programming bugs (null pointer, etc.)

## Instructions

### Best Practices
- **Fail Fast**: Validate input early, fail quickly.
- **Preserve Context**: Include stack traces, metadata, and timestamps.
- **Meaningful Messages**: Explain what happened and how to fix it.
- **Log Appropriately**: Log errors, but don't spam logs for expected failures.
- **Clean Up Resources**: Use try-finally, context managers, or defer.
- **Don't Swallow Errors**: Log or re-throw, don't silently ignore.
- **Type-Safe Errors**: Use typed errors/custom classes when possible.

### Common Pitfalls
- **Catching Too Broadly**: `except Exception` hides bugs.
- **Empty Catch Blocks**: Silently swallowing errors is dangerous.
- **Logging and Re-throwing**: Creates duplicate log entries.
- **Returning Error Codes**: Use exceptions or Result types instead of C-style `-1`.

## Resources
- [Language-Specific Patterns (Python, TS, Rust, Go)](resources/language-specific-patterns.md)
- [Universal Patterns (Circuit Breaker, Aggregation, Degradation)](resources/universal-patterns.md)

### Additional References
- `references/exception-hierarchy-design.md`: Designing error class hierarchies
- `references/error-recovery-strategies.md`: Recovery patterns for different scenarios
- `references/async-error-handling.md`: Handling errors in concurrent code
- `assets/error-handling-checklist.md`: Review checklist for error handling
- `assets/error-message-guide.md`: Writing helpful error messages
- `scripts/error-analyzer.py`: Analyze error patterns in logs
