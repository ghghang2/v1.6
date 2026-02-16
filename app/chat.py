"""Utilities that handle the chat logic.

The original implementation of the chat handling lived directly in
``app.py``.  Extracting the functions into this dedicated module keeps
the UI entry point small and makes the chat logic easier to unit‑test.

Functions
---------
* :func:`build_messages` – convert a conversation history into the
  list of messages expected by the OpenAI chat completion endpoint.
* :func:`stream_and_collect` – stream the assistant response while
  capturing any tool calls.
* :func:`process_tool_calls` – invoke the tools requested by the model
  and generate subsequent assistant turns.
"""

from __future__ import annotations

import json
import logging
import time
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from .config import MODEL_NAME
from .tools import TOOLS
from .db import log_message, log_tool_msg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename="chat.log",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Public helper functions
# ---------------------------------------------------------------------------

# def build_messages(
#     history: Any,
#     system_prompt: str,
#     user_input: Optional[str] = None,
#     max_context_tokens: int = 60000,
# ) -> List[Dict[str, Any]]:
#     """Return the list of messages to send to the chat model.

#     Parameters
#     ----------
#     history
#         List of ``(user, assistant, tool_id, tool_name, tool_args)``
#         tuples that have already happened.
#     system_prompt
#         The system message that sets the model behaviour.
#     user_input
#         The new user message that will trigger the assistant reply.
#     """
#     # Estimate token usage of the conversation.  The OpenAI tokenizer is
#     # complex, but for a quick heuristic we treat each word as ~4 tokens
#     # (roughly the average for English).  This keeps us well below the
#     # 64k token limit while still preserving recent context.
#     def estimate_tokens(text: str) -> int:
#         # Rough estimate: 1 token per 2 words, which is conservative for
#         # English.  The goal is simply to keep the total below the
#         # hard 64k token limit.
#         return max(1, len(text.split())) * 2

#     total_tokens = estimate_tokens(system_prompt)
#     # Build a list of messages first to allow trimming.
#     raw_msgs: List[Dict[str, Any]] = [{"role": "system", "content": str(system_prompt)}]
#     for role, content, tool_id, tool_name, tool_args in history:
#         if tool_name:
#             raw_msgs.append(
#                 {
#                     "role": role,
#                     "content": "",
#                     "tool_calls": [
#                         {
#                             "id": tool_id,
#                             "type": "function",
#                             "function": {
#                                 "name": tool_name,
#                                 "arguments": tool_args or "{}",
#                             },
#                         }
#                     ],
#                 }
#             )
#         elif role == "tool":
#             raw_msgs.append({"role": role, "content": content, "tool_call_id": tool_id})
#         else:
#             raw_msgs.append({"role": role, "content": content})

#         # Update token estimate for this message
#         if role != "tool":
#             total_tokens += estimate_tokens(content)
#         else:
#             total_tokens += estimate_tokens(content)
#     if user_input is not None:
#         raw_msgs.append({"role": "user", "content": str(user_input)})
#         total_tokens += estimate_tokens(user_input)

#     # If we still exceed the limit, drop the oldest non-system messages until
#     # we are within the limit or only the system message remains.
#     while total_tokens > max_context_tokens and len(raw_msgs) > 1:
#         removed = raw_msgs.pop(1)
#         content = removed.get("content", "")
#         total_tokens -= estimate_tokens(content)

#     # Additionally, cap the number of messages to avoid very long histories
#     # that could still push the token count close to the limit.
#     if len(raw_msgs) > 30:
#         # keep system + last 29 user/assistant entries
#         raw_msgs = [raw_msgs[0]] + raw_msgs[-29:]
#     msgs = raw_msgs

#     for role, content, tool_id, tool_name, tool_args in history:
#         if tool_name:
#             msgs.append(
#                 {
#                     "role": role,
#                     "content": "",
#                     "tool_calls": [
#                         {
#                             "id": tool_id,
#                             "type": "function",
#                             "function": {
#                                 "name": tool_name,
#                                 "arguments": tool_args or "{}",
#                             },
#                         }
#                     ],
#                 }
#             )
#         elif role == "tool":
#             msgs.append({"role": role, "content": content, "tool_call_id": tool_id})
#         else:
#             msgs.append({"role": role, "content": content})

#     if user_input is not None:
#         msgs.append({"role": "user", "content": str(user_input)})

#     return msgs
def build_messages(
    history: Any,
    system_prompt: str,
    user_input: Optional[str] = None,
    max_context_tokens: int = 60000,
) -> List[Dict[str, Any]]:
    """Convert the conversation history into a list of messages for the API.

    The history may contain:
      - (role, content, tool_id, tool_name, tool_args)
    Special handling:
      - An "analysis" entry followed immediately by an "assistant" entry is merged
        into a single assistant message with `reasoning_content`.
      - Assistant entries with tool_id == "multiple" contain a JSON array of
        multiple tool calls in tool_args.
    """
    msgs = [{"role": "system", "content": str(system_prompt)}]
    i = 0
    n = len(history)

    while i < n:
        role, content, tool_id, tool_name, tool_args = history[i]

        # ---- Merge analysis + assistant (with or without tool calls) ----
        if role == "analysis" and i + 1 < n:
            next_role, next_content, next_tool_id, next_tool_name, next_tool_args = history[i + 1]
            if next_role == "assistant":
                reasoning = content
                assistant_text = next_content

                # Build the assistant message
                if next_tool_id == "multiple":
                    # Multiple tool calls: parse the stored JSON
                    try:
                        tool_calls_list = json.loads(next_tool_args)
                        api_tool_calls = [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["args"],
                                },
                            }
                            for tc in tool_calls_list
                        ]
                    except Exception:
                        # Fallback: treat as empty
                        api_tool_calls = []
                else:
                    # Single tool call (legacy) – not expected after update,
                    # but handle for compatibility.
                    if next_tool_id:
                        api_tool_calls = [{
                            "id": next_tool_id,
                            "type": "function",
                            "function": {
                                "name": next_tool_name,
                                "arguments": next_tool_args or "{}",
                            },
                        }]
                    else:
                        api_tool_calls = None

                msg = {
                    "role": "assistant",
                    "content": assistant_text,
                    "reasoning_content": reasoning,
                }
                if api_tool_calls:
                    msg["tool_calls"] = api_tool_calls

                msgs.append(msg)
                i += 2  # skip both entries
                continue

        # ---- Normal handling for non-analysis entries ----
        if role == "assistant":
            # Assistant message with possible tool calls
            if tool_id == "multiple":
                # Multiple tool calls stored in tool_args
                try:
                    tool_calls_list = json.loads(tool_args)
                    api_tool_calls = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["args"],
                            },
                        }
                        for tc in tool_calls_list
                    ]
                except Exception:
                    api_tool_calls = None
                msgs.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": api_tool_calls,
                })
            elif tool_id:
                # Single tool call (legacy)
                msgs.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [{
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tool_args or "{}",
                        },
                    }],
                })
            else:
                # Ordinary assistant message
                msgs.append({"role": "assistant", "content": content})

        elif role == "tool":
            msgs.append({"role": "tool", "content": content, "tool_call_id": tool_id})

        elif role == "user":
            msgs.append({"role": "user", "content": content})

        # "analysis" entries that are not merged are simply skipped (they
        # should not occur in a well-formed history, but we drop them safely).

        i += 1

    # Add the new user input if present
    if user_input is not None:
        msgs.append({"role": "user", "content": str(user_input)})

    # ---- Token estimation and trimming (unchanged) ----
    def estimate_tokens(text: str) -> int:
        return max(1, len(text.split())) * 2

    total_tokens = sum(estimate_tokens(msg.get("content", "")) for msg in msgs)
    while total_tokens > max_context_tokens and len(msgs) > 1:
        removed = msgs.pop(1)
        total_tokens -= estimate_tokens(removed.get("content", ""))

    if len(msgs) > 30:
        msgs = [msgs[0]] + msgs[-29:]

    return msgs

def stream_and_collect(
    client: Any,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
) -> Tuple[str, Optional[List[Dict[str, Any]]], bool, str]:
    """Stream the assistant response while capturing tool calls.

    The function writes the incremental assistant content to a placeholder
    and returns a tuple of the complete assistant text, a list of tool
    calls (or ``None`` if no tool call was emitted), a boolean indicating
    if the assistant finished, and any reasoning text.
    """
    stream = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        stream=True,
        tools=tools,
    )

    assistant_text = ""
    reasoning_text = ""
    tool_calls_buffer: Dict[int, Dict[str, Any]] = {}
    finished = False
    reasoning_placeholder = st.empty()
    placeholder = st.empty()

    for chunk in stream:
        choice = chunk.choices[0]
        if choice.finish_reason == "stop":
            finished = True
            break
        delta = choice.delta

        if "metrics_placeholder" in st.session_state:
            st.session_state.metrics_placeholder.markdown(
                st.session_state.latest_metrics_md
            )

        reasoning_part = getattr(delta, "reasoning_content", None)
        if reasoning_part:
            reasoning_text += reasoning_part
            md = f"<details open><summary>Reasoning</summary>\n{reasoning_text}\n</details>"
            reasoning_placeholder.markdown(md, unsafe_allow_html=True)

        if delta.content:
            assistant_text += delta.content
            placeholder.markdown(assistant_text, unsafe_allow_html=True)

        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_calls_buffer:
                    tool_calls_buffer[idx] = {
                        "id": tc_delta.id,
                        "name": tc_delta.function.name,
                        "arguments": "",
                    }
                if tc_delta.function.arguments:
                    tool_calls_buffer[idx]["arguments"] += tc_delta.function.arguments

    final_tool_calls = list(tool_calls_buffer.values()) if tool_calls_buffer else None
    return assistant_text, final_tool_calls, finished, reasoning_text


# def process_tool_calls(
#     client: Any,
#     messages: List[Dict[str, Any]],
#     session_id: str,
#     history: List[Tuple[str, str, str, str, str]],
#     tools: List[Dict[str, Any]],
#     tool_calls: Optional[List[Dict[str, Any]]],
#     finished: bool,
#     assistant_text: str = "",
#     reasoning_text: str = "",
# ) -> List[Tuple[str, str, str, str, str]]:
#     """Execute each tool that the model requested.

#     Parameters
#     ----------
#     client
#         The OpenAI client used to stream assistant replies.
#     messages
#         The conversation history that will be extended with the tool‑call
#         messages and the tool replies.
#     session_id
#         Identifier of the chat session.
#     history
#         Mutable list of ``(role, content, tool_id, tool_name, tool_args)``
#         tuples used to build the chat history.
#     tools
#         The list of OpenAI‑compatible tool definitions.
#     tool_calls
#         The list of tool‑call objects produced by :func:`stream_and_collect`.
#     finished
#         Boolean indicating whether the assistant already finished a turn.
#     assistant_text
#         Text that the assistant returned before the first tool call.
#     reasoning_text
#         Any reasoning content produced by the model.

#     Returns
#     -------
#     list
#         Updated history list.
#     """
#     if not tool_calls:
#         return history

#     # Preserve any assistant text and reasoning that were produced before
#     # the first tool call – the original code discarded this content.
#     if assistant_text:
#         history.append(("assistant", assistant_text, "", "", ""))
#     if reasoning_text:
#         history.append(("analysis", reasoning_text, "", "", ""))

#     while tool_calls and not finished:
#         for tc in tool_calls:
#             try:
#                 args = json.loads(tc.get("arguments") or "{}")
#             except Exception as exc:
#                 args = {}
#                 result = f"\u274c  JSON error: {exc}"
#                 logger.exception("Failed to parse tool arguments", exc_info=True)
#             else:
#                 tool_name = tc.get("name")
#                 logger.info(
#                     "Calling tool %s with arguments %s",
#                     tool_name,
#                     json.dumps(args),
#                 )
#                 func = next((t.func for t in TOOLS if t.name == tool_name), None)
#                 if func:
#                     try:
#                         executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
#                         try:
#                             if tool_name in ['browser', 'run_tests']:
#                                 timeout_sec = 60
#                             else: 
#                                 timeout_sec = 30
#                             future = executor.submit(func, **args)
#                             result = future.result(timeout=timeout_sec)
#                         except concurrent.futures.TimeoutError:  # pragma: no cover
#                             result = (
#                                 f"\u26d4  Tool call {tool_name} timed out after {timeout_sec} seconds. "
#                                 "Try a shorter or more specific request."
#                             )
#                         except Exception as exc:  # pragma: no cover
#                             result = f"\u274c  Tool error: {exc}"
#                         finally:
#                             executor.shutdown(wait=False)
#                     except Exception as exc:  # pragma: no cover
#                         result = f"\u274c  Tool error: {exc}"
#                         logger.exception("Tool raised an exception", exc_info=True)
#                 else:
#                     result = f"\u26a0\ufe0f  Unknown tool '{tc.get('name')}'"

#             preview = result[:10] + ("\u2026" if len(result) > 10 else "")
#             tool_block = (
#                 f"<details>"
#                 f"<summary>{tc.get('name')}|`{json.dumps(args)}`|{preview}</summary>"
#                 f"\n\n`{result}`\n\n"
#                 f"</details>"
#             )
#             st.empty().markdown(tool_block, unsafe_allow_html=True)

#             tool_id = tc.get("id")
            
#             tool_args = tc.get("arguments")
#             messages.append(
#                 {
#                     "role": "assistant",
#                     "content": "",
#                     "tool_calls": [
#                         {
#                             "id": tool_id,
#                             "type": "function",
#                             "function": {
#                                 "name": tool_name,
#                                 "arguments": tool_args or "{}",
#                             },
#                         }
#                     ],
#                 }
#             )
#             messages.append(
#                 {
#                     "role": "tool",
#                     "tool_call_id": str(tool_id or ""),
#                     "content": result,
#                 }
#             )

#             history.append(("assistant", "", tool_id, tool_name, tool_args))
#             history.append(("tool", result, tool_id, tool_name, tool_args))

#             log_tool_msg(session_id, tool_id, tool_name, tool_args, result)

#         new_assistant_resp, new_tool_calls, finished, reasoning_text = stream_and_collect(
#             client, messages, tools
#         )

#         history.append(("analysis", reasoning_text, "", "", ""))
#         history.append(("assistant", new_assistant_resp, "", "", ""))
#         log_message(session_id, "analysis", reasoning_text)
#         log_message(session_id, "assistant", new_assistant_resp)
#         tool_calls = new_tool_calls or None

#     return history

def process_tool_calls(
    client: Any,
    messages: List[Dict[str, Any]],
    session_id: str,
    history: List[Tuple[str, str, str, str, str]],
    tools: List[Dict[str, Any]],
    tool_calls: Optional[List[Dict[str, Any]]],
    finished: bool,
    assistant_text: str = "",
    reasoning_text: str = "",
) -> List[Tuple[str, str, str, str, str]]:
    """Execute tools and continue the conversation, handling multiple tool calls in one turn."""
    if not tool_calls:
        return history

    # --- 1. Construct the assistant message that contains all tool calls ---
    # The message should include any assistant text, reasoning, and all tool calls.
    tool_calls_list = []
    for tc in tool_calls:
        tool_calls_list.append({
            "id": tc.get("id"),
            "type": "function",
            "function": {
                "name": tc.get("name"),
                "arguments": tc.get("arguments") or "{}",
            },
        })

    assistant_msg = {
        "role": "assistant",
        "content": assistant_text,                     # any text before tool calls
        "reasoning_content": reasoning_text,           # reasoning for this turn
        "tool_calls": tool_calls_list,
    }
    messages.append(assistant_msg)

    # Store the reasoning in history (as before)
    if reasoning_text:
        history.append(("analysis", reasoning_text, "", "", ""))

    # Store the combined assistant turn in history.
    # We use a single assistant entry with tool_id = "multiple" to indicate it holds
    # multiple tool calls. The tool_args will hold a JSON array of all tool calls.
    # This is a compact representation that does not require schema changes.
    import json
    tool_calls_data = json.dumps([
        {"id": tc.get("id"), "name": tc.get("name"), "args": tc.get("arguments")}
        for tc in tool_calls
    ])
    history.append(("assistant", assistant_text, "multiple", "tool_calls", tool_calls_data))

    # --- 2. Execute each tool and append tool responses ---
    for tc in tool_calls:
        tool_id = tc.get("id")
        tool_name = tc.get("name")
        tool_args = tc.get("arguments") or "{}"

        try:
            args = json.loads(tool_args)
        except Exception as exc:
            args = {}
            result = f"\u274c  JSON error: {exc}"
            logger.exception("Failed to parse tool arguments", exc_info=True)
        else:
            func = next((t.func for t in TOOLS if t.name == tool_name), None)
            if func:
                try:
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    try:
                        timeout_sec = 60 if tool_name in ['browser', 'run_tests'] else 30
                        future = executor.submit(func, **args)
                        result = future.result(timeout=timeout_sec)
                    except concurrent.futures.TimeoutError:
                        result = f"\u26d4  Tool call {tool_name} timed out after {timeout_sec} seconds."
                    except Exception as exc:
                        result = f"\u274c  Tool error: {exc}"
                    finally:
                        executor.shutdown(wait=False)
                except Exception as exc:
                    result = f"\u274c  Tool error: {exc}"
                    logger.exception("Tool raised an exception", exc_info=True)
            else:
                result = f"\u26a0\ufe0f  Unknown tool '{tool_name}'"

        # Display tool result (optional)
        preview = result[:10] + ("\u2026" if len(result) > 10 else "")
        tool_block = (
            f"<details>"
            f"<summary>{tool_name}|`{json.dumps(args)}`|{preview}</summary>"
            f"\n\n`{result}`\n\n"
            f"</details>"
        )
        st.empty().markdown(tool_block, unsafe_allow_html=True)

        # Append tool response to messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_id,
            "content": result,
        })

        # Append to history
        history.append(("tool", result, tool_id, tool_name, tool_args))

        # Log to DB
        log_tool_msg(session_id, tool_id, tool_name, tool_args, result)

    # --- 3. Get the next assistant response (may be final answer or more tool calls) ---
    new_assistant_resp, new_tool_calls, finished, new_reasoning = stream_and_collect(
        client, messages, tools
    )

    # Append the new assistant turn to history (separate from the tool-call turn)
    if new_reasoning:
        history.append(("analysis", new_reasoning, "", "", ""))
    if new_assistant_resp:
        history.append(("assistant", new_assistant_resp, "", "", ""))

    # Log the new turn
    log_message(session_id, "analysis", new_reasoning)
    log_message(session_id, "assistant", new_assistant_resp)

    # If there are more tool calls, recursively process them
    if new_tool_calls and not finished:
        history = process_tool_calls(
            client, messages, session_id, history, tools,
            new_tool_calls, finished, new_assistant_resp, new_reasoning
        )

    return history