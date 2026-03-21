# Test Suite Mocking Refactoring Progress

## Overview
This document tracks progress on refactoring nbchat test suite to use appropriate mocking patterns. The goal is to replace incorrect `sys.modules.setdefault()` mocks that block imports with proper mocking techniques.

---

## Task Status

### Task 1: Analyze All Test Files for Mocking Usage
**Status**: ✅ **COMPLETE**

**Description**: Reviewed all test files to identify where mocking is appropriate vs. where it is incorrectly implemented.

**Findings**:
- 7 test files analyzed
- 2 files correctly implemented (no mocking needed)
- 1 file correctly implemented (proper Playwright mocking)
- 4 files have problematic `sys.modules.setdefault()` mocks

**Files Identified**:
| File | Mocking Status | Issue |
|------|----------------|-------|
| `test_simple_import.py` | ✅ Correct | None - no mocking needed |
| `test_debug_path.py` | ✅ Correct | None - debug script, no mocking |
| `test_browser.py` | ✅ Correct | Proper `@patch` usage, mock factories |
| `test_chat_builder.py` | ❌ Incorrect | `sys.modules.setdefault()` blocks imports |
| `test_context_manager.py` | ⚠️ Mixed | `sys.modules.setdefault()` + proper `@patch` |
| `test_compressor.py` | ⚠️ Mixed | `sys.modules.setdefault()` + proper client mocks |
| `test_monitoring.py` | ⚠️ Mixed | `sys.modules.setdefault()` + proper patches |

**Root Cause Pattern**:
```python
# INCORRECT - blocks imports
sys.modules.setdefault("nbchat", MagicMock())
sys.modules.setdefault("nbchat.ui", MagicMock())
sys.modules.setdefault("nbchat.core", MagicMock())

from nbchat.ui.chat_builder import build_messages
```

**Correct Pattern**:
```python
# CORRECT - import normally, mock specific behaviors
from nbchat.ui.chat_builder import build_messages

# Then use @patch for specific methods if needed
with patch.object(SomeClass, 'some_method'):
    # test code
```

**Notes for Future Implementation**:
- The `sys.modules.setdefault()` approach should be avoided entirely
- Module-level mocks prevent real imports from occurring
- Comments in `test_chat_builder.py` even stated "The module has no heavyweight dependencies so we can import directly"
- The underlying nbchat packages function correctly when tested without excessive mocking
- `test_simple_import.py` proved that simple direct tests work perfectly
- `test_browser.py` demonstrates proper mocking via `@patch` and mock factories

---

### Task 2: Fix test_chat_builder.py
**Status**: ⏳ **PENDING**

**Description**: Remove `sys.modules.setdefault()` mocks and verify imports work correctly.

**Planned Changes**:
1. Remove lines 23-24:
   ```python
   sys.modules.setdefault("nbchat", MagicMock())
   sys.modules.setdefault("nbchat.ui", MagicMock())
   ```
2. Import directly without mocks:
   ```python
   from nbchat.ui import chat_builder
   ```
3. Run tests to verify functionality

**Verification Command**:
```bash
cd /content && python3 -m pytest tests/test_chat_builder.py -v
```

**Expected Outcome**: All tests should pass without import errors.

---

### Task 3: Fix test_context_manager.py
**Status**: ⏳ **PENDING**

**Description**: Remove `sys.modules.setdefault()` mocks, keep proper `@patch` decorators.

**Planned Changes**:
1. Remove lines 18-22:
   ```python
   sys.modules.setdefault("nbchat", MagicMock())
   sys.modules.setdefault("nbchat.core", MagicMock())
   sys.modules.setdefault("nbchat.core.utils", MagicMock())
   ```
2. Keep the `@patch` decorators which are correct
3. Keep the `FakeChat` class which provides the test host

**Verification Command**:
```bash
cd /content && python3 -m pytest tests/test_context_manager.py -v
```

**Expected Outcome**: Tests should run with proper isolation via `@patch` decorators.

---

### Task 4: Fix test_compressor.py
**Status**: ⏳ **PENDING**

**Description**: Remove `sys.modules.setdefault()` mocks, keep config mock and client mocks.

**Planned Changes**:
1. Remove lines 15-18:
   ```python
   _config_mock = MagicMock()
   sys.modules.setdefault("nbchat", MagicMock())
   sys.modules.setdefault("nbchat.core", MagicMock())
   sys.modules["nbchat.core.config"] = _config_mock
   ```
2. Keep the `_mock_client()` factory function for LLM mocking
3. Keep proper `@patch` decorators if any

**Verification Command**:
```bash
cd /content && python3 -m pytest tests/test_compressor.py -v
```

**Expected Outcome**: Tests should run with proper isolation for LLM calls and config.

---

### Task 5: Fix test_monitoring.py
**Status**: ⏳ **PENDING**

**Description**: Remove `sys.modules.setdefault()` mocks, keep file I/O patches and tmp_path usage.

**Planned Changes**:
1. Remove lines 17-19:
   ```python
   sys.modules.setdefault("nbchat", MagicMock())
   sys.modules.setdefault("nbchat.core", MagicMock())
   ```
2. Keep `@patch` decorators for file I/O
3. Keep `tmp_path` fixtures

**Verification Command**:
```bash
cd /content && python3 -m pytest tests/test_monitoring.py -v
```

**Expected Outcome**: Tests should run with proper isolation for file operations and LLM calls.

---

### Task 6: Verify Complete Test Suite
**Status**: ⏳ **PENDING**

**Description**: Run the full test suite to confirm all tests pass.

**Verification Command**:
```bash
cd /content && python3 -m pytest -v
```

**Expected Outcome**: All tests should pass without import errors.

---

## Notes Section

### Important Findings

1. **The `sys.modules.setdefault()` Anti-Pattern**:
   - This pattern was consistently used across 4 test files
   - It replaces actual modules with MagicMock objects **before** imports
   - This causes imports to fail or return Mock objects instead of real modules
   - The fix is to simply remove these lines and import normally

2. **What Works Correctly**:
   - `test_simple_import.py` proves that direct imports work when /content is in sys.path
   - `test_browser.py` demonstrates proper use of `@patch` decorators
   - `@patch` decorators are the correct way to mock specific methods/behaviors
   - Mock factory functions (like `_mock_client()`) are good practice
   - Using `tmp_path` for file I/O tests is correct

3. **Underlying Code Quality**:
   - The nbchat packages themselves are not broken
   - The issue was purely with incorrect test setup
   - Comments in test files often stated the code could import directly
   - Tests were over-mocked, not under-mocked

4. **Test File Purposes**:
   - `test_simple_import.py`: Verification that imports work (no mocking)
   - `test_debug_path.py`: Debug utility (no mocking)
   - `test_browser.py`: Unit tests with proper Playwright mocking (correct)
   - `test_chat_builder.py`: KV-cache alignment contract tests (over-mocked)
   - `test_context_manager.py`: Context window management tests (over-mocked)
   - `test_compressor.py`: Tool output compression tests (over-mocked)
   - `test_monitoring.py`: Llama.cpp log parsing tests (over-mocked)

5. **Common Test Structure Pattern (from correct files)**:
   - Import real modules when possible
   - Use `@patch` for specific behaviors that need isolation
   - Use mock factories for complex mock objects (e.g., LLM clients)
   - Use `tmp_path` or `tmpdir` for file-based tests
   - Avoid module-level `sys.modules` manipulation

### Implementation Notes

When fixing each file:
1. First, identify and remove ALL `sys.modules.setdefault()` calls
2. Then, verify the imports work without them
3. Keep any `@patch` decorators that are targeting specific methods
4. Keep any mock factory functions that create appropriate mock objects
5. Run tests immediately after each file fix to verify

### Debugging Tips

If imports still fail after removing `sys.modules.setdefault()`:
1. Check that `/content` is in `sys.path` (pytest should handle this automatically)
2. Look for any other mocking in the test file that might be blocking imports
3. Check if any imports are done at module level that trigger side effects
4. Use `test_simple_import.py` as a baseline - if that works, imports should work

### Potential Pitfalls

1. **Don't over-revert**: Some mocking is appropriate (e.g., LLM clients, external APIs)
2. **Preserve test isolation**: `@patch` decorators should still be used where needed
3. **Check for side effects**: Some modules might have import-time side effects
4. **Verify test behavior**: Just because imports work doesn't mean tests pass - run them

---

## Action Log

### Completed Actions
- ✅ Analyzed all 7 test files
- ✅ Identified problematic `sys.modules.setdefault()` patterns
- ✅ Documented correct vs. incorrect mocking approaches
- ✅ Created this progress tracking document

### Next Action
- 🔄 Start with Task 2: Fix `test_chat_builder.py`

### Pending Actions
- ⏳ Task 3: Fix `test_context_manager.py`
- ⏳ Task 4: Fix `test_compressor.py`
- ⏳ Task 5: Fix `test_monitoring.py`
- ⏳ Task 6: Verify complete test suite

---

## Last Updated
Generated during analysis phase. Will be updated after each task completion.