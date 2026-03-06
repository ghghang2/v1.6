| Relative path | Function | Description |
|---------------|----------|-------------|
| nbchat/core/client.py | get_client | Return a client that talks to the local OpenAI‑compatible server. |
| nbchat/core/config.py | _load_config | Load the YAML configuration file.  Parameters ---------- path: Path     Path to the YAML file.  Returns ------- dict     Parsed configuration or an empty dict on failure. |
| nbchat/core/db.py | init_db | Create the database and tables if they do not exist.  Idempotent — safe to call on every application startup. |
| nbchat/core/db.py | log_message | Persist a single chat line (user or assistant text). |
| nbchat/core/db.py | log_tool_msg | Persist a tool result row with its associated metadata. |
| nbchat/core/db.py | load_history | Return chat rows for *session_id* in insertion order.  Returns tuples of ``(role, content, tool_id, tool_name, tool_args)``. |
| nbchat/core/db.py | get_session_ids | Return all distinct session IDs ordered by most recent activity. |
| nbchat/core/db.py | replace_session_history | Atomically replace all chat_log rows for *session_id*.  Used by the compaction engine after it trims older turns.  The context summary is stored separately via ``save_context_summary`` and is therefore unaffected by this call. |
| nbchat/core/db.py | save_context_summary | Upsert the rolling context summary for *session_id*.  There is at most one summary row per session; this replaces any previously stored value. |
| nbchat/core/db.py | load_context_summary | Return the stored context summary for *session_id*, or ``""``. |
| nbchat/core/remote.py | _token | Return the GitHub PAT from the environment. |
| nbchat/core/remote.py | _remote_url | Return an HTTPS URL that contains the PAT.  Parameters ---------- repo_name:     The repository name to use in the URL.  If ``None`` the default     :data:`~nbchat.core.config.REPO_NAME` is used. |
| nbchat/core/utils.py | lazy_import | Import a module only when needed.  The function mirrors the behaviour of the legacy ``lazy_import``. |
| nbchat/tools/__init__.py | _generate_schema |  |
| nbchat/tools/__init__.py | get_tools | Return the list of tools formatted for chat.completions.create. |
| nbchat/tools/browser.py | browser | Stateless browser wrapper using Playwright.  The function launches a fresh browser instance for each call, performs any optional actions, extracts page content, and then tears the browser down. This design avoids shared state and makes the tool safe for concurrent use.  Parameters ---------- url: str     The URL to visit. actions: list[dict], optional     A list of user interactions. Each dict must contain a ``type`` key     and any additional keys required for that action:      ``click``   – ``selector`` required.     ``type``    – ``selector`` and ``text`` required.     ``wait``    – either ``selector`` or ``timeout`` (ms) required.     ``screenshot`` – optional ``path``; defaults to ``"screenshot.png"``. selector: str, optional     CSS selector from which to extract text. If omitted, the entire page     body text is returned. navigation_timeout: int, optional     Timeout in milliseconds for page navigation. action_timeout: int, optional     Default timeout for click, type, and wait actions. max_content_length: int, optional     Maximum number of characters returned in ``content``. screenshot_path: str, optional     Path to store the screenshot. If ``None`` the action's ``path`` key     is used or a default ``screenshot.png``. **kwargs     Accepts a nested JSON string under the ``kwargs`` key for LLM     compatibility.  Returns ------- str     JSON string containing the extracted text, source, or operation     results. On failure an ``{"error": ...}`` payload is returned. |
| nbchat/tools/create_file.py | _safe_resolve | Resolve ``rel_path`` against ``repo_root`` and ensure the result does **not** escape the repository root (prevents directory traversal). |
| nbchat/tools/create_file.py | _create_file | Create a new file at ``path`` (relative to the repository root) with the supplied ``content``.  Parameters ---------- path     File path relative to the repo root.  ``path`` may contain     directory separators but **must not** escape the root. content     Raw text to write into the file.  Returns ------- str     JSON string.  On success:      .. code-block:: json          { "result": "File created: <path>" }      On failure:      .. code-block:: json          { "error": "<exception message>" } |
| nbchat/tools/get_weather.py | _geocode_city | Return latitude and longitude for a given city name.  The function queries the OpenMeteo geocoding API and returns the first result.  It raises a :class:`ValueError` if the city cannot be found. |
| nbchat/tools/get_weather.py | _fetch_weather | Fetch current and daily forecast weather data for the given coordinates and date.  Parameters ---------- lat, lon: float     Latitude and longitude of the location. date: str     ISO 8601 formatted date string (YYYY-MM-DD).  The API expects a     single day, so ``start_date`` and ``end_date`` are identical. |
| nbchat/tools/get_weather.py | _get_weather | Retrieve current and forecast weather information for a given city and date.  Parameters ---------- city: str     The name of the city to look up. date: str, optional     The date for which to retrieve forecast data (ISO format YYYY-MM-DD).     If omitted or empty, today's date is used. |
| nbchat/tools/make_change_to_file.py | _safe_resolve | Resolve ``rel_path`` against ``repo_root`` and guard against directory traversal. Normalize to NFKC to ensure characters like '..' or '/' aren't spoofed |
| nbchat/tools/make_change_to_file.py | _extract_payload |  |
| nbchat/tools/make_change_to_file.py | apply_diff |  |
| nbchat/tools/make_change_to_file.py | _trim_overlap | Trims the end of ins_lines if they already exist at the start of following_lines. Prevents duplicate 'stitching' when the diff and file overlap. |
| nbchat/tools/make_change_to_file.py | _normalize_diff_lines | Clean the diff and strip Unified Diff metadata headers. |
| nbchat/tools/make_change_to_file.py | _detect_newline |  |
| nbchat/tools/make_change_to_file.py | _is_done |  |
| nbchat/tools/make_change_to_file.py | _read_str |  |
| nbchat/tools/make_change_to_file.py | _parse_create_diff |  |
| nbchat/tools/make_change_to_file.py | _parse_update_diff |  |
| nbchat/tools/make_change_to_file.py | _advance_cursor |  |
| nbchat/tools/make_change_to_file.py | _read_section |  |
| nbchat/tools/make_change_to_file.py | _equals_slice | Helper to compare a slice of lines using a transformation function (like strip). |
| nbchat/tools/make_change_to_file.py | _find_context |  |
| nbchat/tools/make_change_to_file.py | _apply_chunks |  |
| nbchat/tools/make_change_to_file.py | make_change_to_file | Apply a unified diff to a file inside the repository.  Parameters ---------- path : str     Relative file path (under the repo root). op_type : str     One of ``create``, ``update`` or ``delete``. diff : str     Unified diff string (ignored for ``delete``).  Returns ------- str     JSON string with either ``result`` or ``error``. |
| nbchat/tools/push_to_github.py | push_to_github | Push the current repository to GitHub.  Parameters ---------- repo_name:     Optional override for the repository name.  If ``None`` the     default from :data:`nbchat.core.config.REPO_NAME` is used. commit_message:     Commit message for the auto commit.  Defaults to ``"Auto commit"``. rebase:     Whether to rebase during pull.  Defaults to ``False`` to mirror     the original behaviour. |
| nbchat/tools/repo_overview.py | walk_python_files | Return a sorted list of all ``.py`` files under *root*. |
| nbchat/tools/repo_overview.py | extract_functions_from_file | Return a list of (function_name, docstring) for top‑level functions.  Functions defined inside classes or other functions are ignored. |
| nbchat/tools/repo_overview.py | build_markdown_table |  |
| nbchat/tools/repo_overview.py | func | Generate a markdown table of all top‑level Python functions.  The table is written to ``repo_overview.md`` in the repository root. |
| nbchat/tools/run_command.py | _safe_resolve | Resolve ``rel_path`` against ``repo_root`` and ensure the result does **not** escape the repository root (prevents directory traversal). |
| nbchat/tools/run_command.py | _run_command | Execute ``command`` in the repository root and return a JSON string with:     * ``stdout``     * ``stderr``     * ``exit_code`` Any exception is converted to an error JSON.  The ``cwd`` argument is accepted for backward compatibility but ignored; the command is always executed in the repository root. |
| nbchat/tools/run_tests.py | _run_tests | Execute `pytest -q` in the repository root and return JSON. |
| nbchat/tools/send_email.py | _send_email | Send an email via Gmail.  Parameters ---------- subject: str     Subject line of the email. body: str     Plain‑text body of the email.  Returns ------- str     JSON string containing either ``result`` or ``error``. |
| nbchat/ui/chat_builder.py | build_messages | Build OpenAI messages from internal chat history.  Parameters ---------- history:     List of tuples ``(role, content, tool_id, tool_name, tool_args)``. system_prompt:     The system message to prepend. context_summary:     Rolling summary produced by CompactionEngine.  When non-empty it is     merged into the single system message so llama.cpp chat templates     that only honour one system block still receive the summary. |
| nbchat/ui/chat_renderer.py | render_user |  |
| nbchat/ui/chat_renderer.py | render_assistant |  |
| nbchat/ui/chat_renderer.py | render_reasoning |  |
| nbchat/ui/chat_renderer.py | render_tool |  |
| nbchat/ui/chat_renderer.py | render_assistant_with_tools |  |
| nbchat/ui/chat_renderer.py | render_assistant_full |  |
| nbchat/ui/chat_renderer.py | render_system |  |
| nbchat/ui/chat_renderer.py | render_placeholder |  |
| nbchat/ui/chat_renderer.py | render_compacted_summary |  |
| nbchat/ui/styles.py | _style |  |
| nbchat/ui/styles.py | _div |  |
| nbchat/ui/styles.py | _style_code | Inject color style into un-styled <code>, <span>, and codehilite <div> tags. |
| nbchat/ui/styles.py | _md |  |
| nbchat/ui/styles.py | _tool_calls_html |  |
| nbchat/ui/styles.py | user_message_html |  |
| nbchat/ui/styles.py | assistant_message_html |  |
| nbchat/ui/styles.py | reasoning_html |  |
| nbchat/ui/styles.py | assistant_full_html |  |
| nbchat/ui/styles.py | assistant_message_with_tools_html |  |
| nbchat/ui/styles.py | tool_result_html |  |
| nbchat/ui/styles.py | system_message_html |  |
| nbchat/ui/styles.py | compacted_summary_html |  |
| nbchat/ui/styles.py | make_widget | Return an :class:`ipywidgets.HTML` widget.  The original code defined this function inside ``compacted_summary_html`` due to a stray indentation.  That made the module fail to import.  The function is now defined at module level. |
| nbchat/ui/tool_executor.py | run_tool | Execute a tool with arguments and return the string result.  Parameters ---------- tool_name:     Name of the tool to execute. args_json:     JSON string containing the arguments for the tool. timeout:     Optional timeout in seconds.  If ``None`` a default of 60 seconds     is used for ``browser`` and ``run_tests`` tools, otherwise 30. |
| nbchat/ui/tool_executor.py | trim_tool_output |  |
| nbchat/ui/utils.py | md_to_html | Convert markdown to HTML using fenced code blocks.  This is the same implementation that lived in the legacy file. |
| nbchat/ui/utils.py | changed_files |  |
| run.py | _run | Run a shell command, optionally merging extra environment variables. |
| run.py | _is_port_free |  |
| run.py | _wait_for |  |
| run.py | _save_service_info |  |
| run.py | _load_service_info |  |
| run.py | _kill_pid | Gracefully terminate a process and its children. |
| run.py | main |  |
| run.py | status |  |
| run.py | stop |  |