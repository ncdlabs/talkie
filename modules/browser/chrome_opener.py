"""
Open a URL in the system browser (e.g. Google Chrome on macOS).
Supports scrolling via pyautogui key presses (page up/down, left/right).
"""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

_SCROLL_KEYS = {"down": "pagedown", "up": "pageup", "left": "left", "right": "right"}


class ChromeOpener:
    """Opens URLs in the configured browser app (e.g. Chrome) via subprocess."""

    def __init__(self, chrome_app_name: str = "Google Chrome") -> None:
        self._app_name = (chrome_app_name or "Google Chrome").strip() or "Google Chrome"

    def scroll(self, direction: str) -> str:
        """
        Scroll by sending key(s) to the focused window via pyautogui.
        direction: one of "up", "down", "left", "right".
        Returns a short user-facing message; on failure returns an error message.
        """
        direction = (direction or "").strip().lower()
        if direction not in _SCROLL_KEYS:
            return "Scroll direction must be up, down, left, or right."
        return self._scroll_via_keys(direction)

    def _scroll_via_keys(self, direction: str) -> str:
        """Send key(s) via pyautogui for full-page scroll."""
        try:
            import pyautogui
        except ImportError:
            return "Scroll is not available (pyautogui not installed)."
        key = _SCROLL_KEYS[direction]
        try:
            if direction in ("left", "right"):
                for _ in range(5):
                    pyautogui.press(key, interval=0.05)
            else:
                # Send page up/down twice so we scroll a full page (more pronounced).
                for _ in range(2):
                    pyautogui.press(key, interval=0.12)
            return "Scrolled."
        except Exception as e:
            logger.warning("Scroll key press failed: %s", e)
            return "Could not scroll. Is the window you want to scroll in focus?"

    def open_in_browser(self, url: str) -> None:
        """
        Open URL in the configured browser in front of the user (autonomous visible window).
        On macOS uses 'open -a "AppName" "url"'; if that fails (e.g. app name wrong), falls back
        to default browser. Raises RuntimeError only if both fail.
        """
        url = (url or "").strip()
        if not url:
            raise ValueError("URL is empty.")
        system = platform.system()
        if system == "Darwin":
            try:
                subprocess.run(
                    ["open", "-a", self._app_name, url],
                    check=True,
                    timeout=10,
                    capture_output=True,
                )
                return
            except subprocess.CalledProcessError as e:
                logger.warning(
                    "open -a %s failed (exit %s), trying default browser: %s",
                    self._app_name,
                    e.returncode,
                    e,
                )
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.warning("open -a failed, trying default browser: %s", e)
            try:
                import webbrowser

                webbrowser.open(url)
                logger.info(
                    "Opened URL in default browser (open -a %s failed or timed out)",
                    self._app_name,
                )
            except Exception as e:
                logger.exception("Default browser open failed: %s", e)
                raise RuntimeError("Could not open the browser.") from e
            return
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception as e:
            logger.exception("Open in browser failed: %s", e)
            raise RuntimeError("Could not open the browser.") from e

    def open_in_new_tab(self, url: str) -> None:
        """
        Open URL in a new tab of the configured browser.
        On macOS uses AppleScript to tell Chrome to make a new tab with the URL.
        On other platforms falls back to open_in_browser (default behavior).
        """
        url = (url or "").strip()
        if not url:
            raise ValueError("URL is empty.")
        if platform.system() != "Darwin":
            self.open_in_browser(url)
            return
        # Escape backslash and double-quote for AppleScript string
        url_esc = url.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            f'tell application "{self._app_name}" to '
            "reopen\n"
            f'tell application "{self._app_name}" to activate\n'
            f'tell application "{self._app_name}" to tell front window '
            f'to make new tab with properties {{URL:"{url_esc}"}}'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                timeout=10,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(
                "Chrome new tab failed (exit %s), falling back to open: %s",
                e.returncode,
                e.stderr,
            )
            self.open_in_browser(url)
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("Chrome new tab failed: %s", e)
            self.open_in_browser(url)

    def get_active_tab_url(self) -> str | None:
        """
        Return the URL of the active tab in the frontmost window of the browser.
        On macOS uses AppleScript; on other platforms returns None.
        """
        if platform.system() != "Darwin":
            return None
        script = (
            f'tell application "{self._app_name}" to '
            "get URL of active tab of front window"
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                check=True,
                timeout=5,
                capture_output=True,
                text=True,
            )
            url = (result.stdout or "").strip()
            return url if url else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            logger.debug("Chrome get active tab URL failed: %s", e)
            return None

    def close_active_tab(self) -> str:
        """
        Close the active tab in the frontmost window of the browser.
        On macOS uses AppleScript. Returns a short user-facing message.
        """
        if platform.system() != "Darwin":
            return "Close tab is only supported on macOS."
        script = (
            f'tell application "{self._app_name}" to '
            "tell front window to close active tab"
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                timeout=5,
                capture_output=True,
            )
            return "Tab closed."
        except subprocess.CalledProcessError as e:
            logger.debug("Chrome close active tab failed: %s", e)
            return "Could not close the tab. Is Chrome in front?"
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("Chrome close active tab failed: %s", e)
            return "Could not close the tab."
