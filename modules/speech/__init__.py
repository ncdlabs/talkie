"""
Speech module loader: core only loads the speech module via API or uses SDK no-ops.
When modules.speech.server is enabled, returns remote clients; otherwise no-op components.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from sdk import (
    NoOpCapture,
    NoOpSpeakerFilter,
    NoOpSTTEngine,
    NoOpTTSEngine,
    get_logger,
    get_speech_section,
)

logger = get_logger("speech")


# Re-export calibration overlay from app for backward compatibility
def apply_calibration_overlay(audio_cfg: dict, settings_repo: Any) -> dict:
    from app.config_overlay import apply_calibration_overlay as _apply

    return _apply(audio_cfg, settings_repo)


def apply_llm_calibration_overlay(llm_cfg: dict, settings_repo: Any) -> dict:
    from app.config_overlay import apply_llm_calibration_overlay as _apply

    return _apply(llm_cfg, settings_repo)


class SpeechComponents(NamedTuple):
    """Immutable bundle of capture, STT, TTS, speaker filter, and auto_sensitivity config."""

    capture: Any
    stt: Any
    tts: Any
    speaker_filter: Any
    auto_sensitivity: dict


def _default_auto_sensitivity() -> dict:
    return {
        "enabled": False,
        "min_level": 0.002,
        "max_level": 0.08,
        "step": 0.25,
        "cooldown_chunks": 3,
    }


def create_speech_components(
    config: dict, settings_repo: Any = None
) -> SpeechComponents:
    """
    Build speech components: remote API clients when speech server is configured,
    otherwise SDK no-ops so core runs without the speech module.
    """
    raw_config = getattr(config, "_raw", config)
    from modules.api.config import get_module_base_url, get_module_server_config

    server_config = get_module_server_config(raw_config, "speech")
    if server_config is not None:
        from modules.api.client import ModuleAPIClient
        from modules.api.speech_client import (
            RemoteAudioCapture,
            RemoteSTTEngine,
            RemoteTTSEngine,
            RemoteSpeakerFilter,
        )

        base_url = get_module_base_url(server_config)
        client = ModuleAPIClient(
            base_url=base_url,
            timeout_sec=server_config["timeout_sec"],
            retry_max=server_config["retry_max"],
            retry_delay_sec=server_config["retry_delay_sec"],
            circuit_breaker_failure_threshold=server_config[
                "circuit_breaker_failure_threshold"
            ],
            circuit_breaker_recovery_timeout_sec=server_config[
                "circuit_breaker_recovery_timeout_sec"
            ],
            api_key=server_config["api_key"],
            module_name="speech",
            use_service_discovery=server_config.get("use_service_discovery", False),
            consul_host=server_config.get("consul_host"),
            consul_port=server_config.get("consul_port", 8500),
            keydb_host=server_config.get("keydb_host"),
            keydb_port=server_config.get("keydb_port", 6379),
            load_balancing_strategy=server_config.get(
                "load_balancing_strategy", "health_based"
            ),
            health_check_interval_sec=server_config.get(
                "health_check_interval_sec", 30.0
            ),
        )
        speech_cfg = get_speech_section(raw_config)
        audio_cfg = speech_cfg.get("audio", {})
        auto_sensitivity = _default_auto_sensitivity()
        if audio_cfg.get("auto_sensitivity"):
            auto_sensitivity["enabled"] = True
            auto_sensitivity["min_level"] = max(
                0.0,
                min(1.0, float(audio_cfg.get("auto_sensitivity_min_level", 0.002))),
            )
            auto_sensitivity["max_level"] = max(
                0.0,
                min(1.0, float(audio_cfg.get("auto_sensitivity_max_level", 0.08))),
            )
            auto_sensitivity["step"] = max(
                0.05,
                min(2.0, float(audio_cfg.get("auto_sensitivity_step", 0.25))),
            )
            auto_sensitivity["cooldown_chunks"] = max(
                1, int(audio_cfg.get("auto_sensitivity_cooldown_chunks", 3))
            )
        return SpeechComponents(
            capture=RemoteAudioCapture(client),
            stt=RemoteSTTEngine(client),
            tts=RemoteTTSEngine(client),
            speaker_filter=RemoteSpeakerFilter(client),
            auto_sensitivity=auto_sensitivity,
        )

    return SpeechComponents(
        capture=NoOpCapture(),
        stt=NoOpSTTEngine(),
        tts=NoOpTTSEngine(),
        speaker_filter=NoOpSpeakerFilter(),
        auto_sensitivity=_default_auto_sensitivity(),
    )


def register(context: dict) -> None:
    """
    Register speech components with the app context (two-phase).
    Phase 1 (context has no "pipeline"): set context["speech_components"] with TTS replaced by NoOp so only browser speaks.
    Phase 2 (context has "pipeline"): no-op.
    """
    if context.get("pipeline") is not None:
        return
    config = context.get("config")
    settings_repo = context.get("settings_repo")
    if config is None:
        return
    try:
        comps = create_speech_components(config, settings_repo)
        context["speech_components"] = comps._replace(tts=NoOpTTSEngine())
    except Exception as e:
        logger.debug("Speech module register (phase 1) failed: %s", e)


__all__ = [
    "SpeechComponents",
    "apply_calibration_overlay",
    "apply_llm_calibration_overlay",
    "create_speech_components",
    "register",
]
