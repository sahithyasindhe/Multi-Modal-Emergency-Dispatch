"""ASR providers — Whisper when available, deterministic demo otherwise."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from backend.config import get_settings
from backend.schemas.incident import AudioEvidence
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Keyword heuristics for audio-event indicators in demo/transcript mode.
EVENT_PATTERNS = {
    "siren": r"\b(siren|ambulance|fire.?truck)\b",
    "scream": r"\b(scream|screaming|yelling|crying)\b",
    "explosion": r"\b(explosion|blast|blew.?up|detonat)\b",
    "glass_breaking": r"\b(glass|shattered|breaking.?window)\b",
    "gunshot": r"\b(gunshot|shot.?fired|gun.?fire)\b",
}


def panic_from_transcript(transcript: str, prosody: dict | None = None) -> float:
    """Transparent heuristic panic index in [0, 1]."""
    text = transcript.lower()
    score = 0.15
    panic_words = [
        "help", "please", "urgent", "dying", "bleeding", "fire", "trapped",
        "can't breathe", "unconscious", "not breathing", "hurry", "screaming",
    ]
    for w in panic_words:
        if w in text:
            score += 0.08
    if "!!!" in transcript or transcript.isupper():
        score += 0.15
    if prosody:
        score += min(0.25, prosody.get("rms_energy", 0) * 0.5)
        score += min(0.15, max(0, (prosody.get("speech_rate_wpm", 120) - 140) / 200))
        score += min(0.1, prosody.get("silence_ratio", 0) * 0.3)
    return round(min(1.0, score), 3)


def detect_audio_events(transcript: str) -> list[str]:
    found = []
    for name, pat in EVENT_PATTERNS.items():
        if re.search(pat, transcript, re.I):
            found.append(name)
    return found


def estimate_prosody_from_text(transcript: str) -> dict:
    words = transcript.split()
    n = max(1, len(words))
    # Approximate speaking duration ~ 150 wpm baseline for demo.
    duration_s = max(1.0, n / 2.5)
    speech_rate = (n / duration_s) * 60
    silence_ratio = 0.12 if n > 20 else 0.25
    return {
        "rms_energy": 0.35 + min(0.4, n / 80),
        "pitch_mean": 180.0,
        "speech_rate_wpm": round(speech_rate, 1),
        "silence_ratio": silence_ratio,
    }


class ASRProvider(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: Optional[str] = None, transcript_hint: Optional[str] = None) -> AudioEvidence:
        raise NotImplementedError


class DemoASRProvider(ASRProvider):
    name = "demo"

    def transcribe(self, audio_path: Optional[str] = None, transcript_hint: Optional[str] = None) -> AudioEvidence:
        transcript = transcript_hint or (
            "There's been a bad car accident on Market Street. "
            "Three people are hurt, one isn't moving. I smell gas."
        )
        prosody = estimate_prosody_from_text(transcript)
        if audio_path and Path(audio_path).exists():
            try:
                prosody = self._librosa_prosody(audio_path) or prosody
            except Exception as exc:
                logger.info("Prosody fallback (demo): %s", exc)
        panic = panic_from_transcript(transcript, prosody)
        return AudioEvidence(
            transcript=transcript,
            language="en",
            timestamps=[{"start": 0.0, "end": 8.0, "text": transcript}],
            panic_index=panic,
            speech_rate_wpm=prosody["speech_rate_wpm"],
            silence_ratio=prosody["silence_ratio"],
            rms_energy=prosody["rms_energy"],
            pitch_mean=prosody["pitch_mean"],
            audio_events=detect_audio_events(transcript),
            provider=self.name,
            confidence=0.75,
        )

    def _librosa_prosody(self, audio_path: str) -> dict | None:
        try:
            import librosa
            import numpy as np

            y, sr = librosa.load(audio_path, sr=16000, duration=30)
            rms = float(np.mean(librosa.feature.rms(y=y)))
            pitches, mags = librosa.piptrack(y=y, sr=sr)
            pitch_vals = pitches[mags > np.median(mags)]
            pitch_mean = float(np.mean(pitch_vals)) if len(pitch_vals) else 0.0
            intervals = librosa.effects.split(y, top_db=30)
            voiced = sum(e - s for s, e in intervals) / max(1, len(y))
            duration = len(y) / sr
            # Rough speech-rate proxy from zero-crossing / duration.
            speech_rate = min(220.0, 60.0 / max(0.5, duration) * 10)
            return {
                "rms_energy": min(1.0, rms * 5),
                "pitch_mean": pitch_mean,
                "speech_rate_wpm": speech_rate,
                "silence_ratio": max(0.0, 1.0 - voiced),
            }
        except Exception:
            return None


class WhisperASRProvider(ASRProvider):
    name = "faster-whisper"

    def __init__(self) -> None:
        self._model = None
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
            logger.info("faster-whisper loaded (tiny/cpu)")
        except Exception as exc:
            logger.warning("Whisper unavailable, will fall back: %s", exc)
            self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_path: Optional[str] = None, transcript_hint: Optional[str] = None) -> AudioEvidence:
        if self._model is None or not audio_path:
            return DemoASRProvider().transcribe(audio_path, transcript_hint)
        segments, info = self._model.transcribe(audio_path, beam_size=1)
        parts = []
        stamps = []
        for seg in segments:
            parts.append(seg.text.strip())
            stamps.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        transcript = " ".join(parts).strip() or (transcript_hint or "")
        demo = DemoASRProvider()
        prosody = demo._librosa_prosody(audio_path) or estimate_prosody_from_text(transcript)
        panic = panic_from_transcript(transcript, prosody)
        return AudioEvidence(
            transcript=transcript,
            language=getattr(info, "language", "en") or "en",
            timestamps=stamps,
            panic_index=panic,
            speech_rate_wpm=prosody["speech_rate_wpm"],
            silence_ratio=prosody["silence_ratio"],
            rms_energy=prosody["rms_energy"],
            pitch_mean=prosody["pitch_mean"],
            audio_events=detect_audio_events(transcript),
            provider=self.name,
            confidence=0.85,
        )


def get_asr_provider() -> ASRProvider:
    settings = get_settings()
    if settings.model_mode == "demo":
        return DemoASRProvider()
    whisper = WhisperASRProvider()
    if whisper.available:
        return whisper
    return DemoASRProvider()
