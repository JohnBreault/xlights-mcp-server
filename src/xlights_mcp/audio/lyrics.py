"""Lyric extraction and phoneme mapping for xLights singing faces.

Uses OpenAI Whisper for speech-to-text transcription with word-level timestamps,
then converts words to xLights phoneme codes for the Faces effect.

xLights phoneme codes:
  AI  — A/I vowel sounds (bat, bite, father)
  E   — E vowel sound (bet, bead)
  FV  — F/V consonant (fan, van)
  L   — L consonant (lip, bell)
  MBP — M/B/P consonant (map, bat, pat) — closed mouth
  O   — O vowel sound (bot, boat)
  U   — U/OO vowel sound (but, boot)
  WQ  — W/Q consonant (wet, quick)
  etc — catch-all / transition
  rest — silence / closed mouth
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PhonemeEvent(BaseModel):
    """A single phoneme at a specific time."""

    phoneme: str  # xLights phoneme code: AI, E, FV, L, MBP, O, U, WQ, etc, rest
    start_time_ms: int
    end_time_ms: int
    word: str = ""  # the source word (for debugging)


class LyricWord(BaseModel):
    """A transcribed word with timing."""

    word: str
    start_time: float  # seconds
    end_time: float  # seconds


class LyricTrack(BaseModel):
    """Complete lyric/phoneme track for a song."""

    words: list[LyricWord] = Field(default_factory=list)
    phonemes: list[PhonemeEvent] = Field(default_factory=list)
    track_name: str = "Lyric Track"
    source: str = "full_mix"  # "full_mix", "vocals_stem", etc.
    available: bool = False


# Mapping of English letter patterns to xLights phoneme codes
# Order matters — longer/more specific patterns first
PHONEME_RULES: list[tuple[str, str]] = [
    # Vowel digraphs
    ("oo", "U"),
    ("ou", "U"),
    ("ow", "O"),
    ("oi", "O"),
    ("oy", "O"),
    ("ea", "E"),
    ("ee", "E"),
    ("ei", "AI"),
    ("ey", "E"),
    ("ai", "AI"),
    ("ay", "AI"),
    ("ie", "E"),
    ("oa", "O"),
    ("au", "O"),
    ("aw", "O"),
    # Consonant digraphs
    ("th", "L"),
    ("sh", "FV"),
    ("ch", "E"),
    ("wh", "WQ"),
    ("ph", "FV"),
    ("qu", "WQ"),
    ("ng", "E"),
    # Single consonants
    ("b", "MBP"),
    ("c", "E"),
    ("d", "E"),
    ("f", "FV"),
    ("g", "E"),
    ("h", "E"),
    ("j", "E"),
    ("k", "E"),
    ("l", "L"),
    ("m", "MBP"),
    ("n", "E"),
    ("p", "MBP"),
    ("r", "O"),
    ("s", "E"),
    ("t", "E"),
    ("v", "FV"),
    ("w", "WQ"),
    ("x", "E"),
    ("y", "E"),
    ("z", "E"),
    # Single vowels (fallback)
    ("a", "AI"),
    ("e", "E"),
    ("i", "AI"),
    ("o", "O"),
    ("u", "U"),
]


def extract_lyrics(
    audio_path: Path,
    whisper_model: str = "base",
) -> LyricTrack:
    """Transcribe audio and generate phoneme timing track.

    Args:
        audio_path: Path to audio file
        whisper_model: Whisper model size ("tiny", "base", "small", "medium")
    """
    try:
        import whisper
    except ImportError:
        logger.warning(
            "openai-whisper not installed. Install with: "
            "uv pip install openai-whisper"
        )
        return LyricTrack(available=False)

    logger.info(f"Transcribing lyrics with Whisper ({whisper_model}): {audio_path}")

    try:
        # Fix SSL cert issues on macOS
        import os
        try:
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
        except ImportError:
            pass

        model = whisper.load_model(whisper_model)
        result = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
        )
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return LyricTrack(available=False)

    # Extract word-level timestamps from segments
    words: list[LyricWord] = []
    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            word = word_info.get("word", "").strip()
            start = word_info.get("start", 0.0)
            end = word_info.get("end", 0.0)
            if word and end > start:
                words.append(LyricWord(word=word, start_time=start, end_time=end))

    if not words:
        logger.warning("No words detected in transcription")
        return LyricTrack(available=False)

    logger.info(f"Transcribed {len(words)} words")

    # Convert words to phonemes
    phonemes = _words_to_phonemes(words)
    logger.info(f"Generated {len(phonemes)} phoneme events")

    return LyricTrack(
        words=words,
        phonemes=phonemes,
        track_name="Lyric Track",
        source="full_mix",
        available=True,
    )


def extract_vocal_tracks(
    audio_path: Path,
    whisper_model: str = "base",
) -> list[LyricTrack]:
    """Extract all available vocal timing tracks from an audio file.

    Attempts stem separation (Demucs) to get a clean vocals track,
    then runs Whisper on each available source. Returns all tracks
    found so they can be independently assigned to singing models.

    Returns:
        List of LyricTrack objects (may be empty if no vocals detected).
        Each track has a unique track_name and source identifier.
    """
    tracks: list[LyricTrack] = []

    # Try stem separation for a clean vocals track
    vocals_stem_path: Path | None = None
    try:
        from xlights_mcp.audio.separator import separate_stems
        stems = separate_stems(audio_path)
        if stems.available and stems.vocals:
            vocals_stem_path = Path(stems.vocals)
            if vocals_stem_path.exists():
                logger.info(f"Vocals stem available: {vocals_stem_path}")
    except Exception as e:
        logger.info(f"Stem separation unavailable: {e}")

    # Track 1: Transcribe the isolated vocals stem (cleanest source)
    if vocals_stem_path:
        stem_track = extract_lyrics(vocals_stem_path, whisper_model=whisper_model)
        if stem_track.available:
            stem_track.track_name = "Vocals"
            stem_track.source = "vocals_stem"
            tracks.append(stem_track)
            logger.info(f"Extracted 'Vocals' track from stem: {len(stem_track.words)} words")

    # Track 2: Transcribe the full mix (captures backing vocals too)
    mix_track = extract_lyrics(audio_path, whisper_model=whisper_model)
    if mix_track.available:
        # Name depends on whether we already have a stem track
        if tracks:
            mix_track.track_name = "Full Mix Vocals"
        else:
            mix_track.track_name = "Vocals"
        mix_track.source = "full_mix"
        tracks.append(mix_track)
        logger.info(f"Extracted '{mix_track.track_name}' track from mix: {len(mix_track.words)} words")

    return tracks


def _words_to_phonemes(words: list[LyricWord]) -> list[PhonemeEvent]:
    """Convert word timestamps to xLights phoneme events.

    Each word is broken into phoneme segments based on its letters.
    Gaps between words get 'rest' phonemes.
    """
    phonemes: list[PhonemeEvent] = []

    for i, word in enumerate(words):
        # Add rest between words if there's a gap
        if i > 0:
            prev_end = words[i - 1].end_time
            gap = word.start_time - prev_end
            if gap > 0.05:  # more than 50ms gap
                phonemes.append(PhonemeEvent(
                    phoneme="rest",
                    start_time_ms=int(prev_end * 1000),
                    end_time_ms=int(word.start_time * 1000),
                    word="",
                ))

        # Break word into phoneme segments
        word_phonemes = _word_to_phoneme_sequence(word.word)
        if not word_phonemes:
            word_phonemes = ["etc"]

        word_duration_ms = int((word.end_time - word.start_time) * 1000)
        segment_duration = max(25, word_duration_ms // len(word_phonemes))

        current_ms = int(word.start_time * 1000)
        for j, phon in enumerate(word_phonemes):
            end_ms = current_ms + segment_duration
            if j == len(word_phonemes) - 1:
                # Last phoneme extends to word end
                end_ms = int(word.end_time * 1000)

            phonemes.append(PhonemeEvent(
                phoneme=phon,
                start_time_ms=current_ms,
                end_time_ms=end_ms,
                word=word.word if j == 0 else "",
            ))
            current_ms = end_ms

    return phonemes


def _word_to_phoneme_sequence(word: str) -> list[str]:
    """Convert a word to a sequence of xLights phoneme codes."""
    word_lower = re.sub(r"[^a-z]", "", word.lower())
    if not word_lower:
        return ["etc"]

    phonemes = []
    i = 0
    while i < len(word_lower):
        matched = False
        # Try 2-character patterns first
        if i + 1 < len(word_lower):
            digraph = word_lower[i : i + 2]
            for pattern, code in PHONEME_RULES:
                if pattern == digraph and len(pattern) == 2:
                    phonemes.append(code)
                    i += 2
                    matched = True
                    break

        if not matched:
            char = word_lower[i]
            for pattern, code in PHONEME_RULES:
                if pattern == char and len(pattern) == 1:
                    phonemes.append(code)
                    break
            i += 1

    # Deduplicate consecutive identical phonemes
    deduped = []
    for p in phonemes:
        if not deduped or deduped[-1] != p:
            deduped.append(p)

    return deduped if deduped else ["etc"]
