# Refactoring Progress Tracker

## Pending Tasks
- [ ] Review all modules for hardcoded configuration values and replace them with values loaded from `repo_config.yaml`.
- [ ] Update imports accordingly.
- [ ] Run the test suite to ensure no regressions.
- [ ] Commit and push changes to GitHub.
- [ ] Notify via email upon completion.

## Completed Tasks
- [x] Consolidated `MAX_TOOL_OUTPUT_CHARS` into `repo_config.yaml` and updated `nbchat/ui/tool_executor.py` to import the value from `nbchat.core.config`.
