"""Tests for the browser tool.

Structure
---------
Unit tests (mocked)   – fast, hermetic, cover all validation and response shaping.
                        Run by default.
Integration tests     – real Chromium + real network. Opt-in only:
                        pytest -m integration

Fast suite (default):
    pytest test_browser.py

Full suite:
    pytest test_browser.py -m "integration or not integration"
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from nbchat.tools.browser import browser, _TransientNetworkError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ok(result: str) -> dict:
    data = json.loads(result)
    assert "error" not in data, f"Unexpected error: {data}"
    return data


def err(result: str) -> dict:
    data = json.loads(result)
    assert "error" in data, f"Expected error, got: {data}"
    assert "hint" in data, "Error response must include a hint"
    assert data["hint"], "hint must be a non-empty string"
    return data


# ---------------------------------------------------------------------------
# Playwright mock factory
# ---------------------------------------------------------------------------

_DEFAULT_PAGE_DATA = {
    "title": "Example Domain",
    "url": "https://example.com/",
    "text": "Example Domain\nThis domain is for use in illustrative examples.",
    "interactive": [{"role": "link", "text": "More information...", "selector": None}],
    "links": [{"text": "More information...", "href": "https://www.iana.org/domains/reserved"}],
}


def _make_playwright_mock(
    page_data: dict | None = None,
    nav_status: int = 200,
    page_url: str = "https://example.com/",
    raise_on_goto=None,
    raise_on_action: Exception | None = None,
):
    data = page_data or _DEFAULT_PAGE_DATA

    page = MagicMock()
    page.url = page_url
    page.evaluate.return_value = data
    page.goto.return_value = MagicMock(status=nav_status)
    page.locator.return_value.all_inner_texts.return_value = [data["text"]]

    if raise_on_goto:
        page.goto.side_effect = raise_on_goto
    if raise_on_action:
        page.click.side_effect = raise_on_action
        page.fill.side_effect = raise_on_action
        page.select_option.side_effect = raise_on_action

    ctx = MagicMock()
    ctx.new_page.return_value = page

    browser_inst = MagicMock()
    browser_inst.new_context.return_value = ctx

    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser_inst
    playwright.__enter__ = MagicMock(return_value=playwright)
    playwright.__exit__ = MagicMock(return_value=False)

    return playwright, browser_inst, ctx, page


def _patch(pw):
    return patch("nbchat.tools.browser.sync_playwright", return_value=pw)


def _run(actions, page_data=None, **kwargs):
    """Convenience: run browser() with a mock and return (data, page)."""
    pw, bi, ctx, page = _make_playwright_mock(page_data=page_data)
    with _patch(pw):
        data = ok(browser(url="https://example.com", actions=actions, **kwargs))
    return data, page


# ===========================================================================
# 1. INPUT VALIDATION
# ===========================================================================

class TestInputValidation:

    def test_url_none_rejected(self):
        data = err(browser(url=None))
        assert "url is required" in data["error"]

    def test_url_empty_string_rejected(self):
        data = err(browser(url=""))
        assert "url is required" in data["error"]

    def test_url_whitespace_only_rejected(self):
        data = err(browser(url="   "))
        assert "url is required" in data["error"]

    def test_url_integer_rejected(self):
        data = err(browser(url=42))
        assert "url is required" in data["error"]

    def test_url_whitespace_is_stripped(self):
        pw, _, _, page = _make_playwright_mock()
        with _patch(pw):
            ok(browser(url="  https://example.com  "))
        assert page.goto.call_args[0][0] == "https://example.com"

    def test_url_missing_scheme_autofixed_to_https(self):
        pw, _, _, page = _make_playwright_mock()
        with _patch(pw):
            ok(browser(url="example.com"))
        assert page.goto.call_args[0][0] == "https://example.com"

    def test_actions_not_a_list_rejected(self):
        data = err(browser(url="https://example.com", actions="click"))
        assert "must be a list" in data["error"]

    def test_actions_dict_rejected(self):
        # A plain dict is not a list
        data = err(browser(url="https://example.com", actions={"type": "click"}))
        assert "must be a list" in data["error"]

    def test_actions_item_string_rejected(self):
        data = err(browser(url="https://example.com", actions=["click h1"]))
        assert "must be a dict" in data["error"]

    def test_actions_item_number_rejected(self):
        data = err(browser(url="https://example.com", actions=[1]))
        assert "must be a dict" in data["error"]

    def test_actions_mixed_valid_invalid_rejected(self):
        data = err(browser(url="https://example.com", actions=[{"type": "wait", "timeout": 100}, "bad"]))
        assert "must be a dict" in data["error"]

    def test_actions_empty_list_accepted(self):
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com", actions=[]))
        assert data["status"] == "success"
        assert "actions" not in data

    def test_actions_dict_without_type_normalised_to_unknown(self):
        data, _ = _run([{}])
        assert data["status"] == "success"
        assert any("unknown action type" in a for a in data.get("actions", []))

    def test_wait_until_invalid_rejected(self):
        data = err(browser(url="https://example.com", wait_until="instant"))
        assert "wait_until" in data["error"]

    def test_wait_until_valid_values_accepted(self):
        for val in ("commit", "domcontentloaded", "load", "networkidle"):
            pw, _, _, _ = _make_playwright_mock()
            with _patch(pw):
                ok(browser(url="https://example.com", wait_until=val))

    def test_navigation_timeout_zero_rejected(self):
        data = err(browser(url="https://example.com", navigation_timeout=0))
        assert "navigation_timeout" in data["error"]

    def test_navigation_timeout_negative_rejected(self):
        data = err(browser(url="https://example.com", navigation_timeout=-1000))
        assert "navigation_timeout" in data["error"]

    def test_navigation_timeout_non_int_rejected(self):
        data = err(browser(url="https://example.com", navigation_timeout="30000"))
        assert "navigation_timeout" in data["error"]

    def test_action_timeout_zero_rejected(self):
        data = err(browser(url="https://example.com", action_timeout=0))
        assert "action_timeout" in data["error"]

    def test_max_content_length_zero_rejected(self):
        data = err(browser(url="https://example.com", max_content_length=0))
        assert "max_content_length" in data["error"]

    def test_max_content_length_negative_rejected(self):
        data = err(browser(url="https://example.com", max_content_length=-1))
        assert "max_content_length" in data["error"]


# ===========================================================================
# 2. RESPONSE SHAPING
# ===========================================================================

class TestResponseShape:

    def test_success_has_required_keys(self):
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com"))
        assert {"status", "url", "title", "content"} <= data.keys()

    def test_status_success_when_no_action_errors(self):
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com"))
        assert data["status"] == "success"

    def test_status_partial_when_action_fails(self):
        from playwright.sync_api import TimeoutError as PWTimeout
        pw, _, _, _ = _make_playwright_mock(raise_on_action=PWTimeout("timed out"))
        with _patch(pw):
            data = ok(browser(url="https://example.com", actions=[{"type": "click", "selector": ".x"}]))
        assert data["status"] == "partial"

    def test_action_errors_field_on_partial(self):
        from playwright.sync_api import TimeoutError as PWTimeout
        pw, _, _, _ = _make_playwright_mock(raise_on_action=PWTimeout("timed out"))
        with _patch(pw):
            data = ok(browser(url="https://example.com", actions=[{"type": "click", "selector": ".x"}]))
        assert isinstance(data["action_errors"], list)
        assert len(data["action_errors"]) > 0

    def test_actions_log_present_even_on_partial(self):
        from playwright.sync_api import TimeoutError as PWTimeout
        pw, _, _, _ = _make_playwright_mock(raise_on_action=PWTimeout("timed out"))
        with _patch(pw):
            data = ok(browser(url="https://example.com", actions=[{"type": "click", "selector": ".x"}]))
        assert "actions" in data

    def test_content_truncated_to_max_content_length(self):
        long_data = {**_DEFAULT_PAGE_DATA, "text": "x" * 20_000}
        pw, _, _, _ = _make_playwright_mock(page_data=long_data)
        with _patch(pw):
            data = ok(browser(url="https://example.com", max_content_length=100))
        assert len(data["content"]) <= 100

    def test_title_present_without_selector(self):
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com"))
        assert data["title"] == _DEFAULT_PAGE_DATA["title"]

    def test_title_absent_with_selector(self):
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com", selector="h1"))
        assert "title" not in data
        assert "content" in data

    def test_selector_branch_no_nameerror(self):
        """Regression: selector branch must not NameError on 'data' / 'page_data'."""
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            result = browser(url="https://example.com", selector="h1")
        assert json.loads(result)  # valid JSON

    def test_extract_elements_false_omits_fields(self):
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com", extract_elements=False))
        assert "interactive" not in data
        assert "links" not in data

    def test_extract_elements_true_includes_both_fields(self):
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com", extract_elements=True))
        assert "interactive" in data
        assert "links" in data

    def test_url_reflects_final_page_url_not_input(self):
        """url in response must come from page.url, capturing any redirect."""
        pw, _, _, _ = _make_playwright_mock(page_url="https://example.com/redirected")
        with _patch(pw):
            data = ok(browser(url="https://example.com"))
        assert data["url"] == "https://example.com/redirected"

    def test_http_403_returns_error_with_hint(self):
        pw, _, _, _ = _make_playwright_mock(nav_status=403)
        with _patch(pw):
            data = err(browser(url="https://example.com"))
        assert "403" in data["error"]
        assert "403" in data["hint"]

    def test_http_404_returns_error(self):
        pw, _, _, _ = _make_playwright_mock(nav_status=404)
        with _patch(pw):
            data = err(browser(url="https://example.com"))
        assert "404" in data["error"]

    def test_http_429_returns_error(self):
        pw, _, _, _ = _make_playwright_mock(nav_status=429)
        with _patch(pw):
            data = err(browser(url="https://example.com"))
        assert "429" in data["error"]

    def test_http_500_returns_error(self):
        pw, _, _, _ = _make_playwright_mock(nav_status=500)
        with _patch(pw):
            data = err(browser(url="https://example.com"))
        assert "500" in data["error"]

    def test_hint_for_403_does_not_contain_raw_digits_from_404_key(self):
        """Regression: '403' must not match '404' hint and vice versa."""
        pw, _, _, _ = _make_playwright_mock(nav_status=403)
        with _patch(pw):
            data = err(browser(url="https://example.com"))
        assert "404" not in data["hint"]

    def test_selector_not_found_hint_does_not_fire_for_action_errors(self):
        """'selector not found' hint pattern must not match ValueError messages
        about missing 'selector' fields in actions."""
        pw, _, _, _ = _make_playwright_mock()
        with _patch(pw):
            data = ok(browser(url="https://example.com", actions=[{"type": "click"}]))
        # The action error message contains "'selector' is required for click"
        # — this should NOT trigger the "selector not found" hint pattern.
        error_text = str(data.get("action_errors", []))
        assert "extract_elements" not in error_text  # wrong hint bled through


# ===========================================================================
# 3. ACTIONS
# ===========================================================================

class TestActions:

    def test_click_calls_page_click(self):
        data, page = _run([{"type": "click", "selector": "h1"}])
        page.click.assert_called_once_with("h1", timeout=5000)
        assert "clicked 'h1'" in data["actions"]

    def test_click_missing_selector_is_action_error(self):
        data, _ = _run([{"type": "click"}])
        assert data["status"] == "partial"
        assert any("'selector' is required" in e for e in data["action_errors"])

    def test_type_calls_page_fill(self):
        data, page = _run([{"type": "type", "selector": "input", "text": "hello"}])
        page.fill.assert_called_once_with("input", "hello", timeout=5000)
        assert "typed into 'input'" in data["actions"]

    def test_type_empty_string_is_valid(self):
        """Empty string clears the field — must not be rejected."""
        data, page = _run([{"type": "type", "selector": "input", "text": ""}])
        page.fill.assert_called_once_with("input", "", timeout=5000)
        assert data["status"] == "success"

    def test_type_numeric_text_is_cast_to_str(self):
        data, page = _run([{"type": "type", "selector": "input", "text": 42}])
        page.fill.assert_called_once_with("input", "42", timeout=5000)

    def test_type_missing_text_key_is_action_error(self):
        """Missing 'text' key (not empty string) must be an error."""
        data, _ = _run([{"type": "type", "selector": "input"}])
        assert data["status"] == "partial"
        assert any("'text' is required" in e for e in data["action_errors"])

    def test_type_missing_selector_is_action_error(self):
        data, _ = _run([{"type": "type", "text": "hello"}])
        assert data["status"] == "partial"

    def test_select_calls_page_select_option(self):
        data, page = _run([{"type": "select", "selector": "select", "value": "opt1"}])
        page.select_option.assert_called_once_with("select", value="opt1", timeout=5000)
        assert "selected 'opt1' in 'select'" in data["actions"]

    def test_select_missing_selector_is_action_error(self):
        data, _ = _run([{"type": "select", "value": "opt1"}])
        assert data["status"] == "partial"

    def test_wait_with_timeout_calls_wait_for_timeout(self):
        data, page = _run([{"type": "wait", "timeout": 1000}])
        page.wait_for_timeout.assert_called_once_with(1000)
        assert "waited 1000ms" in data["actions"]

    def test_wait_timeout_string_is_cast_to_int(self):
        data, page = _run([{"type": "wait", "timeout": "500"}])
        page.wait_for_timeout.assert_called_once_with(500)

    def test_wait_with_selector_calls_wait_for_selector(self):
        data, page = _run([{"type": "wait", "selector": "h1"}])
        page.wait_for_selector.assert_called_with("h1", timeout=5000)
        assert "waited for 'h1'" in data["actions"]

    def test_wait_selector_takes_priority_over_timeout(self):
        data, page = _run([{"type": "wait", "selector": "h1", "timeout": 5000}])
        page.wait_for_selector.assert_called()
        page.wait_for_timeout.assert_not_called()

    def test_wait_missing_both_is_action_error(self):
        data, _ = _run([{"type": "wait"}])
        assert data["status"] == "partial"
        assert any("'selector' or 'timeout'" in e for e in data["action_errors"])

    def test_scroll_down_uses_positive_dy(self):
        data, page = _run([{"type": "scroll", "direction": "down", "amount": 500}])
        page.evaluate.assert_any_call("window.scrollBy(0, 500)")

    def test_scroll_up_uses_negative_dy(self):
        data, page = _run([{"type": "scroll", "direction": "up", "amount": 300}])
        page.evaluate.assert_any_call("window.scrollBy(0, -300)")

    def test_scroll_default_direction_is_down(self):
        data, page = _run([{"type": "scroll", "amount": 200}])
        page.evaluate.assert_any_call("window.scrollBy(0, 200)")

    def test_scroll_negative_amount_treated_as_positive(self):
        """A negative amount must not silently invert the direction."""
        data, page = _run([{"type": "scroll", "direction": "down", "amount": -400}])
        page.evaluate.assert_any_call("window.scrollBy(0, 400)")

    def test_navigate_calls_goto_with_dest_url(self):
        data, page = _run([{"type": "navigate", "url": "https://httpbin.org/get"}])
        calls = [c[0][0] for c in page.goto.call_args_list]
        assert "https://httpbin.org/get" in calls
        assert "navigated to 'https://httpbin.org/get'" in data["actions"]

    def test_navigate_missing_url_is_action_error(self):
        data, _ = _run([{"type": "navigate"}])
        assert data["status"] == "partial"

    def test_navigate_http_error_is_action_error(self):
        """HTTP error on navigate action must be an action error, not a crash."""
        pw, _, _, page = _make_playwright_mock()
        # First goto (initial navigation) succeeds; second (navigate action) returns 404.
        nav_resp_404 = MagicMock(status=404)
        page.goto.side_effect = [MagicMock(status=200), nav_resp_404]
        with _patch(pw):
            data = ok(browser(url="https://example.com", actions=[{"type": "navigate", "url": "https://example.com/gone"}]))
        assert data["status"] == "partial"
        assert any("404" in e for e in data["action_errors"])

    def test_navigate_timeout_is_action_error_not_navigation_failure(self):
        """PWTimeout on a navigate action must log an action error, not abort the tool."""
        from playwright.sync_api import TimeoutError as PWTimeout
        pw, _, _, page = _make_playwright_mock()
        page.goto.side_effect = [MagicMock(status=200), PWTimeout("timed out")]
        with _patch(pw):
            data = ok(browser(url="https://example.com", actions=[{"type": "navigate", "url": "https://slow.example.com"}]))
        assert data["status"] == "partial"
        assert any("timed out" in e for e in data["action_errors"])

    def test_screenshot_calls_page_screenshot(self):
        data, page = _run([{"type": "screenshot", "path": "/tmp/shot.png"}])
        page.screenshot.assert_called_once_with(path="/tmp/shot.png")
        assert "screenshot saved to '/tmp/shot.png'" in data["actions"]

    def test_screenshot_default_path(self):
        data, page = _run([{"type": "screenshot"}])
        page.screenshot.assert_called_once_with(path="screenshot.png")

    def test_unknown_action_logged_not_errored(self):
        data, _ = _run([{"type": "hover", "selector": "h1"}])
        assert data["status"] == "success"
        assert any("unknown action type 'hover'" in a for a in data["actions"])
        assert "action_errors" not in data

    def test_multiple_actions_log_is_ordered(self):
        data, _ = _run([
            {"type": "wait", "timeout": 100},
            {"type": "click", "selector": "h1"},
            {"type": "scroll", "direction": "down", "amount": 100},
        ])
        log = data["actions"]
        assert len(log) == 3
        assert "waited" in log[0]
        assert "clicked" in log[1]
        assert "scrolled" in log[2]

    def test_later_actions_run_after_earlier_action_error(self):
        """A failed action must not abort the remaining actions."""
        pw, _, _, page = _make_playwright_mock()
        from playwright.sync_api import TimeoutError as PWTimeout
        # click raises, but fill (type) should still be called
        page.click.side_effect = PWTimeout("no element")
        with _patch(pw):
            data = ok(browser(
                url="https://example.com",
                actions=[
                    {"type": "click", "selector": ".gone"},
                    {"type": "type", "selector": "input", "text": "hello"},
                ],
            ))
        assert data["status"] == "partial"
        assert len(data["actions"]) == 2
        page.fill.assert_called_once()


# ===========================================================================
# 4. RETRY LOGIC
# ===========================================================================

class TestRetryLogic:

    def test_transient_error_triggers_retry(self):
        """_TransientNetworkError on first call must cause a second attempt."""
        pw, _, _, _ = _make_playwright_mock()
        call_count = 0

        def fake_run():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _TransientNetworkError("net::ERR_CONNECTION_RESET")
            # Second call: use the real mock path
            return json.dumps({"status": "success", "url": "https://example.com", "title": "", "content": ""})

        with patch("nbchat.tools.browser.browser.__code__"):
            pass  # Can't easily patch _run(); test via goto side_effect instead

        # Test via network error on goto that matches _TRANSIENT_MARKERS
        pw2, _, _, page2 = _make_playwright_mock()
        page2.goto.side_effect = [
            Exception("net::ERR_CONNECTION_RESET"),
            MagicMock(status=200),
        ]
        with _patch(pw2):
            result = browser(url="https://example.com")
        # Two goto calls = one retry
        assert page2.goto.call_count == 2

    def test_non_transient_error_does_not_retry(self):
        """A generic exception must not trigger a retry."""
        pw, _, _, page = _make_playwright_mock()
        page.goto.side_effect = Exception("something unexpected")
        with _patch(pw):
            result = browser(url="https://example.com")
        assert page.goto.call_count == 1
        data = json.loads(result)
        assert "error" in data


# ===========================================================================
# 5. RESOURCE MANAGEMENT
# ===========================================================================

class TestResourceManagement:

    def test_browser_closed_on_success(self):
        pw, bi, ctx, _ = _make_playwright_mock()
        with _patch(pw):
            browser(url="https://example.com")
        bi.close.assert_called_once()
        ctx.close.assert_called_once()

    def test_browser_closed_when_extraction_raises(self):
        """ctx and browser_inst must be closed even if page.evaluate raises."""
        pw, bi, ctx, page = _make_playwright_mock()
        page.evaluate.side_effect = RuntimeError("JS crash")
        with _patch(pw):
            browser(url="https://example.com")
        ctx.close.assert_called_once()
        bi.close.assert_called_once()

    def test_browser_inst_closed_when_new_context_raises(self):
        """browser_inst must be closed even if new_context() raises."""
        pw, bi, ctx, _ = _make_playwright_mock()
        bi.new_context.side_effect = RuntimeError("context failed")
        with _patch(pw):
            result = browser(url="https://example.com")
        bi.close.assert_called_once()
        data = json.loads(result)
        assert "error" in data

    def test_selector_not_found_still_closes_browser(self):
        pw, bi, ctx, page = _make_playwright_mock()
        page.wait_for_selector.side_effect = Exception("not found")
        with _patch(pw):
            browser(url="https://example.com", selector=".missing")
        ctx.close.assert_called_once()
        bi.close.assert_called_once()


# ===========================================================================
# 6. INTEGRATION  (real network, opt-in)
# ===========================================================================

@pytest.mark.integration
class TestIntegration:
    """Real browser + real network. Run with: pytest -m integration"""

    def test_example_com_loads(self):
        data = ok(browser(url="https://example.com"))
        assert data["status"] == "success"
        assert "Example Domain" in data["title"]
        assert "Example Domain" in data["content"]
        assert data["url"].startswith("https://example.com")

    def test_missing_scheme_autofixed(self):
        data = ok(browser(url="example.com"))
        assert data["status"] == "success"

    def test_invalid_domain_returns_error(self):
        data = err(browser(url="https://not-a-real-domain-xyz-12345.com"))
        assert "hint" in data

    def test_extract_elements_true_returns_both_fields(self):
        data = ok(browser(url="https://example.com", extract_elements=True))
        assert isinstance(data["interactive"], list)
        assert isinstance(data["links"], list)

    def test_extract_elements_false_omits_both_fields(self):
        data = ok(browser(url="https://example.com", extract_elements=False))
        assert "interactive" not in data
        assert "links" not in data

    def test_selector_branch_returns_content_no_title(self):
        data = ok(browser(url="https://example.com", selector="h1"))
        assert "content" in data
        assert "title" not in data
        assert "Example Domain" in data["content"]

    def test_selector_not_found_returns_error_with_page_url(self):
        data = err(browser(url="https://example.com", selector=".does-not-exist-xyz"))
        assert "selector not found" in data["error"]
        assert "page_url" in data

    def test_click_h1_succeeds(self):
        data = ok(browser(url="https://example.com", actions=[{"type": "click", "selector": "h1"}]))
        assert data["status"] == "success"
        assert any("clicked" in a for a in data.get("actions", []))

    def test_click_nonexistent_selector_is_partial(self):
        data = ok(browser(url="https://example.com", actions=[{"type": "click", "selector": ".xyz-nope"}]))
        assert data["status"] == "partial"
        assert "action_errors" in data

    def test_type_empty_string_accepted(self):
        data = ok(browser(
            url="https://httpbin.org/forms/post",
            actions=[{"type": "type", "selector": "input[name='custname']", "text": ""}],
        ))
        assert data["status"] == "success"

    def test_type_missing_text_key_is_partial(self):
        data = ok(browser(
            url="https://httpbin.org/forms/post",
            actions=[{"type": "type", "selector": "input[name='custname']"}],
        ))
        assert data["status"] == "partial"

    def test_navigate_action_url_updates(self):
        data = ok(browser(
            url="https://example.com",
            actions=[{"type": "navigate", "url": "https://example.org"}],
        ))
        assert data["status"] == "success"
        assert "example.org" in data["url"]

    def test_scroll_down(self):
        data = ok(browser(url="https://example.com", actions=[{"type": "scroll", "direction": "down", "amount": 300}]))
        assert data["status"] == "success"

    def test_scroll_negative_amount_does_not_crash(self):
        data = ok(browser(url="https://example.com", actions=[{"type": "scroll", "direction": "down", "amount": -300}]))
        assert data["status"] == "success"

    def test_wait_timeout(self):
        data = ok(browser(url="https://example.com", actions=[{"type": "wait", "timeout": 500}]))
        assert data["status"] == "success"
        assert any("waited 500ms" in a for a in data.get("actions", []))

    def test_max_content_length_respected(self):
        data = ok(browser(url="https://example.com", max_content_length=50))
        assert len(data["content"]) <= 50

    def test_screenshot_saved(self, tmp_path):
        import os
        path = str(tmp_path / "shot.png")
        data = ok(browser(url="https://example.com", actions=[{"type": "screenshot", "path": path}]))
        assert data["status"] == "success"
        assert os.path.exists(path)

    def test_invalid_wait_until_rejected_before_browser_launch(self):
        # This must fail in validation, not deep inside Playwright
        data = err(browser(url="https://example.com", wait_until="bogus"))
        assert "wait_until" in data["error"]