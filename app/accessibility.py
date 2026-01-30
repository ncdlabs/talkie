"""
macOS Accessibility permission check and opening the Accessibility settings pane.
Used so Talkie can inform the user when it needs Accessibility (e.g. for scroll)
and open the pane where they can add the app.
"""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def check_accessibility_permission() -> bool:
    """
    Return True if the current process has Accessibility permission (or we're not on macOS).
    On macOS uses AXIsProcessTrustedWithOptions; on other platforms returns True.
    """
    if platform.system() != "Darwin":
        return True
    try:
        import ctypes

        app_services = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        # AXIsProcessTrustedWithOptions(CFDictionaryRef options) -> Boolean
        # Pass NULL to only check, no prompt.
        if not hasattr(app_services, "AXIsProcessTrustedWithOptions"):
            logger.debug("AXIsProcessTrustedWithOptions not found")
            return False
        app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        return bool(app_services.AXIsProcessTrustedWithOptions(None))
    except Exception as e:
        logger.debug("Accessibility check failed: %s", e)
        return False


def open_accessibility_pane() -> None:
    """
    Open the macOS Accessibility settings pane so the user can add the app.
    No-op on non-macOS.
    """
    if platform.system() != "Darwin":
        return
    try:
        # Ventura/Sonoma: x-apple.systempreferences for System Settings
        # Universal Access / Accessibility pane
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ],
            check=True,
            timeout=5,
            capture_output=True,
        )
    except Exception as e:
        try:
            # Fallback: open the prefPane directly (works on older macOS too)
            subprocess.run(
                [
                    "open",
                    "-b",
                    "com.apple.systempreferences",
                    "/System/Library/PreferencePanes/Security.prefPane",
                ],
                check=True,
                timeout=5,
                capture_output=True,
            )
        except Exception as e2:
            logger.warning("Could not open Accessibility pane: %s; fallback: %s", e, e2)
