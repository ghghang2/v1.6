# Patch Guard Implementation Plan

| Step | Description | Status |
|------|-------------|--------|
| 1 | Strip Markdown quote (`>`) and other non‑diff prefixes before parsing. | Pending |
| 2 | Validate presence of at least one `@@` hunk header. | Pending |
| 3 | Reject non‑UTF‑8 files on read/write. | Pending |
| 4 | Enforce path safety (`..`, absolute paths). | Pending |
| 5 | Require existing files for `update` / `delete`; prevent overwriting existing files on `create`. | Pending |
| 6 | Add configurable patch size limit. | Pending |
| 7 | Check for `*** End File ***` in create mode. | Pending |
| 8 | Improve context‑matching error reporting. | Pending |
| 9 | Wrap entire operation in try/except that always returns JSON. | Pending |

---

**Implementation notes**
- Each step will be implemented in the `apply_patch.py` file.
- After each step is completed, we will update the corresponding status to `Done`.
- If a step fails during implementation, we will note the failure and adjust accordingly.