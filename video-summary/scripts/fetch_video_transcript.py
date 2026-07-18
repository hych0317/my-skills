#!/usr/bin/env python3
"""
Fetch a video's transcript by downloading audio and running Whisper ASR.

This script supports YouTube and Bilibili URLs and uses ASR directly.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path

WHISPER_MODEL = None
WHISPER_MODEL_KEY = None
DEFAULT_BILIBILI_COOKIES = Path(__file__).resolve().parents[4] / "private" / "bilibili_cookies.txt"
DEFAULT_FASTER_WHISPER_MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
DEFAULT_FASTER_WHISPER_COMPUTE_TYPE = "float16"
DEFAULT_FASTER_WHISPER_BEAM_SIZE = 2
DEFAULT_HF_CACHE_DIR = Path("/opt/hf-cache/hub")
DEFAULT_FFPROBE_TIMEOUT_SECONDS = 30
DEFAULT_TRANSCRIPTION_TIMEOUT_DIVISOR = 20.0
DEFAULT_TRANSCRIPTION_TIMEOUT_MINIMUM_SECONDS = 60
DEFAULT_TRANSCRIPTION_TIMEOUT_MAXIMUM_SECONDS = 600
DEFAULT_OUTER_TIMEOUT_MAXIMUM_SECONDS = 600
LONG_VIDEO_CHUNK_SECONDS = 600
SKILL_OUTPUT_SUBDIR = "video-summary"
MAX_SKILL_AUDIO_BYTES = 200 * 1024 * 1024
AUDIO_FILE_EXTENSIONS = {
    ".m4a",
    ".mp3",
    ".wav",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".webm",
    ".m4b",
    ".mp4",
    ".wma",
    ".aiff",
    ".alac",
}


@dataclass
class VideoTranscriptResult:
    url: str
    source_id: str
    success: bool
    fetch_status: str
    asr_status: str
    transcript_source: str | None
    transcript: str | None
    transcript_char_count: int
    transcript_file: str | None
    segments_file: str | None
    transcript_path: str | None
    segments_path: str | None
    chunk_manifest_file: str | None
    chunk_manifest_path: str | None
    chunk_count: int
    duration_seconds: float | None
    recommended_timeout_seconds: int
    audio_file: str | None
    metadata_file: str | None
    metadata_char_count: int
    title: str | None
    uploader: str | None
    warning: str

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def safe_source_id(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    combined = f"{parsed.netloc}-{parsed.path}" if parsed.netloc else value
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", combined).strip("-").lower()
    return normalized[:120] or "video"


def combine_warnings(*messages: str | None) -> str:
    deduped: list[str] = []
    for message in messages:
        if not message:
            continue
        message = message.strip()
        if not message or message in deduped:
            continue
        deduped.append(message)
    return "; ".join(deduped)


def resolve_output_dirs(base_output_dir: Path, source_id: str) -> tuple[Path, Path]:
    skill_output_dir = base_output_dir / SKILL_OUTPUT_SUBDIR
    video_output_dir = skill_output_dir / source_id
    return skill_output_dir, video_output_dir


def write_chunk_manifest(
    segments_path: Path,
    *,
    output_dir: Path,
    source_id: str,
    window_seconds: int = LONG_VIDEO_CHUNK_SECONDS,
) -> tuple[str | None, int]:
    """Write contiguous timestamped transcript windows for long-form summarization."""
    try:
        records = [json.loads(line) for line in segments_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return None, 0
    if not records:
        return None, 0

    chunks: list[dict] = []
    current: list[dict] = []
    chunk_start = float(records[0]["start"])
    chunk_end = chunk_start + window_seconds
    for record in records:
        if current and float(record["start"]) >= chunk_end:
            chunks.append(
                {
                    "index": len(chunks) + 1,
                    "start_seconds": round(chunk_start, 3),
                    "end_seconds": round(float(current[-1]["end"]), 3),
                    "text": normalize_whitespace(" ".join(item["text"] for item in current)),
                }
            )
            current = []
            chunk_start = float(record["start"])
            chunk_end = chunk_start + window_seconds
        current.append(record)
    if current:
        chunks.append(
            {
                "index": len(chunks) + 1,
                "start_seconds": round(chunk_start, 3),
                "end_seconds": round(float(current[-1]["end"]), 3),
                "text": normalize_whitespace(" ".join(item["text"] for item in current)),
            }
        )

    manifest_path = output_dir / f"{source_id}_chunks.jsonl"
    manifest_path.write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + "\n",
        encoding="utf-8",
    )
    return manifest_path.name, len(chunks)


def list_skill_audio_files(skill_output_dir: Path) -> list[Path]:
    if not skill_output_dir.exists():
        return []
    audio_files = [
        path
        for path in skill_output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_FILE_EXTENSIONS
    ]
    return sorted(audio_files, key=lambda path: path.stat().st_mtime_ns)


def prune_oldest_audio_if_skill_over_limit(
    skill_output_dir: Path, limit_bytes: int = MAX_SKILL_AUDIO_BYTES
) -> str | None:
    audio_files = list_skill_audio_files(skill_output_dir)
    total_bytes = sum(path.stat().st_size for path in audio_files)
    if total_bytes <= limit_bytes or not audio_files:
        return None
    oldest = audio_files[0]
    try:
        oldest.unlink()
    except Exception as exc:
        return f"audio cleanup failed before download: {oldest} ({exc})"
    return f"pre-download cleanup removed oldest audio: {oldest.name}"


def delete_file(path: Path) -> str | None:
    try:
        path.unlink(missing_ok=True)
        return None
    except Exception as exc:
        return f"failed to delete file: {path} ({exc})"


def run_command(command: list[str], timeout: int, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    try:
        command_env = os.environ.copy()
        if env:
            command_env.update(env)
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=command_env,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        message = stderr.strip() or stdout.strip() or f"command timed out after {timeout}s"
        return 124, stdout, message
    except Exception as exc:
        return 1, "", str(exc)


def is_bilibili_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return "bilibili.com" in host or "b23.tv" in host


def resolve_cookies_file(url: str, cookies_file: str | None) -> str | None:
    if cookies_file:
        return cookies_file
    if is_bilibili_url(url) and DEFAULT_BILIBILI_COOKIES.exists():
        return str(DEFAULT_BILIBILI_COOKIES)
    return None


def iter_hf_cache_dirs() -> list[Path]:
    candidates: list[Path] = []

    hub_cache = os.getenv("HUGGINGFACE_HUB_CACHE")
    if hub_cache:
        candidates.append(Path(hub_cache))

    hf_home = os.getenv("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home) / "hub")

    candidates.append(DEFAULT_HF_CACHE_DIR)

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)
    return deduped


def resolve_existing_model_file(path: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
    except Exception:
        if path.exists():
            return path
        return None
    return resolved if resolved.exists() else None


def is_valid_faster_whisper_snapshot(snapshot_dir: Path) -> bool:
    required_files = [
        "config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.json",
    ]
    for filename in required_files:
        resolved = resolve_existing_model_file(snapshot_dir / filename)
        if resolved is None:
            return False
        try:
            if resolved.stat().st_size <= 0:
                return False
        except OSError:
            return False
    return True


def resolve_faster_whisper_model(model_name: str) -> str:
    candidate = Path(model_name)
    if candidate.exists():
        return str(candidate)

    if "/" not in model_name:
        return model_name

    repo_name = f"models--{model_name.replace('/', '--')}"
    for cache_dir in iter_hf_cache_dirs():
        if not cache_dir.exists():
            continue
        repo_dir = cache_dir / repo_name
        snapshots_dir = repo_dir / "snapshots"
        if not snapshots_dir.exists():
            continue

        snapshots = sorted(
            (path for path in snapshots_dir.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for snapshot_dir in snapshots:
            if is_valid_faster_whisper_snapshot(snapshot_dir):
                return str(snapshot_dir)

    return model_name


def yt_dlp_cookie_args(cookies_from_browser: str | None, cookies_file: str | None) -> list[str]:
    args: list[str] = []
    if cookies_from_browser:
        args.extend(["--cookies-from-browser", cookies_from_browser])
    if cookies_file:
        args.extend(["--cookies", cookies_file])
    return args


def fetch_video_metadata(
    url: str,
    *,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
) -> tuple[dict | None, str | None]:
    command = [
        "yt-dlp",
        "--no-playlist",
        "-J",
        "--no-download",
        url,
        *yt_dlp_cookie_args(cookies_from_browser, cookies_file),
    ]
    code, stdout, stderr = run_command(command, timeout=120)
    if code != 0 or not stdout.strip():
        return None, stderr.strip() or "failed to fetch video metadata"
    try:
        return json.loads(stdout), None
    except json.JSONDecodeError as exc:
        return None, f"failed to decode video metadata: {exc}"


def save_metadata_text(output_dir: Path, source_id: str, metadata: dict | None) -> tuple[str | None, int]:
    if not metadata:
        return None, 0
    parts = [
        metadata.get("title", ""),
        metadata.get("description", ""),
        metadata.get("uploader", ""),
    ]
    raw_text = "\n".join(part for part in parts if part).strip()
    if not raw_text:
        return None, 0
    path = output_dir / f"{source_id}.txt"
    path.write_text(raw_text, encoding="utf-8")
    return path.name, len(raw_text)


def coerce_duration_seconds(value: object) -> float | None:
    try:
        duration_seconds = float(value)
    except (TypeError, ValueError):
        return None
    return duration_seconds if duration_seconds > 0 else None


def probe_media_duration_seconds(path: Path) -> float | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    code, stdout, _stderr = run_command(command, timeout=DEFAULT_FFPROBE_TIMEOUT_SECONDS)
    if code != 0:
        return None
    return coerce_duration_seconds(stdout.strip())


def estimate_transcription_timeout_seconds(audio_duration_seconds: float | None) -> int:
    if audio_duration_seconds is None:
        return DEFAULT_TRANSCRIPTION_TIMEOUT_MAXIMUM_SECONDS
    estimated_seconds = math.ceil(audio_duration_seconds / DEFAULT_TRANSCRIPTION_TIMEOUT_DIVISOR)
    bounded_seconds = max(DEFAULT_TRANSCRIPTION_TIMEOUT_MINIMUM_SECONDS, estimated_seconds)
    return min(DEFAULT_TRANSCRIPTION_TIMEOUT_MAXIMUM_SECONDS, bounded_seconds)


def estimate_outer_timeout_seconds(audio_duration_seconds: float | None) -> int:
    return min(DEFAULT_OUTER_TIMEOUT_MAXIMUM_SECONDS, estimate_transcription_timeout_seconds(audio_duration_seconds))


def format_duration_label(audio_duration_seconds: float | None) -> str:
    if audio_duration_seconds is None:
        return "unknown-length"
    if audio_duration_seconds >= 60:
        return f"{audio_duration_seconds / 60:.1f}min"
    return f"{math.ceil(audio_duration_seconds)}s"


def download_video_audio(
    url: str,
    *,
    target_dir: Path,
    source_id: str,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
) -> tuple[Path | None, str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    template = str(target_dir / f"{source_id}_audio.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        "ba",
        "-o",
        template,
        url,
        *yt_dlp_cookie_args(cookies_from_browser, cookies_file),
    ]
    code, stdout, stderr = run_command(command, timeout=600)
    audio_files = sorted(target_dir.glob(f"{source_id}_audio.*"))
    audio_files = [path for path in audio_files if path.suffix.lower() != ".part"]
    if audio_files:
        return audio_files[0], ""
    warning = stderr.strip() or stdout.strip() or "audio download failed"
    if is_bilibili_url(url) and "cookies" in warning.lower():
        warning = "bilibili audio download failed, cookies file may be missing or expired"
    elif code != 0 and not warning:
        warning = "audio download failed"
    return None, warning


def load_whisper_model(
    model_name: str = DEFAULT_FASTER_WHISPER_MODEL,
    compute_type: str = DEFAULT_FASTER_WHISPER_COMPUTE_TYPE,
):
    global WHISPER_MODEL
    global WHISPER_MODEL_KEY
    model_ref = resolve_faster_whisper_model(model_name)
    model_key = (model_ref, compute_type)
    if WHISPER_MODEL is None or WHISPER_MODEL_KEY != model_key:
        from faster_whisper import WhisperModel

        try:
            WHISPER_MODEL = WhisperModel(model_ref, device="cuda", compute_type=compute_type)
        except Exception:
            WHISPER_MODEL = WhisperModel(model_ref, device="cpu", compute_type="int8")
        WHISPER_MODEL_KEY = model_key
    return WHISPER_MODEL


def transcribe_audio_locally(
    audio_path: Path,
    *,
    output_dir: Path,
    source_id: str,
    model_name: str = DEFAULT_FASTER_WHISPER_MODEL,
    language: str | None = "zh",
    compute_type: str = DEFAULT_FASTER_WHISPER_COMPUTE_TYPE,
    beam_size: int = DEFAULT_FASTER_WHISPER_BEAM_SIZE,
) -> tuple[str | None, str | None, str | None, str]:
    try:
        os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        model = load_whisper_model(model_name=DEFAULT_FASTER_WHISPER_MODEL, compute_type=compute_type)
        segments, _info = model.transcribe(
            str(audio_path),
            task="transcribe",
            language=language,
            beam_size=beam_size,
            vad_filter=True,
        )
        segment_records = [
            {
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": normalize_whitespace(segment.text),
            }
            for segment in segments
            if normalize_whitespace(segment.text)
        ]
        text = normalize_whitespace(" ".join(record["text"] for record in segment_records))
    except Exception as exc:
        return None, None, None, f"faster-whisper transcription failed: {exc}"
    if not text:
        return None, None, None, "faster-whisper returned empty text"

    transcript_path = output_dir / f"{source_id}_transcript.txt"
    transcript_path.write_text(text, encoding="utf-8")
    segments_path = output_dir / f"{source_id}_segments.jsonl"
    segments_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in segment_records) + "\n",
        encoding="utf-8",
    )
    return text, transcript_path.name, segments_path.name, ""


def transcribe_audio_with_whisper(
    audio_path: Path,
    *,
    output_dir: Path,
    source_id: str,
    model_name: str = DEFAULT_FASTER_WHISPER_MODEL,
    language: str | None = "zh",
    compute_type: str = DEFAULT_FASTER_WHISPER_COMPUTE_TYPE,
    beam_size: int = DEFAULT_FASTER_WHISPER_BEAM_SIZE,
    audio_duration_seconds: float | None = None,
) -> tuple[str | None, str | None, str | None, str]:
    resolved_duration_seconds = audio_duration_seconds or probe_media_duration_seconds(audio_path)
    timeout_seconds = estimate_transcription_timeout_seconds(resolved_duration_seconds)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--internal-transcribe-audio",
        str(audio_path),
        "--internal-transcribe-output-dir",
        str(output_dir),
        "--internal-transcribe-source-id",
        source_id,
        "--whisper-model",
        DEFAULT_FASTER_WHISPER_MODEL,
        "--whisper-compute-type",
        compute_type,
        "--whisper-beam-size",
        str(beam_size),
        "--asr-language",
        language if language is not None else "auto",
        "--json",
    ]
    code, stdout, stderr = run_command(
        command,
        timeout=timeout_seconds,
        env={"KMP_DUPLICATE_LIB_OK": "TRUE"},
    )
    if code == 124:
        return (
            None,
            None,
            None,
            f"faster-whisper transcription timed out after {timeout_seconds}s for {format_duration_label(resolved_duration_seconds)} audio",
        )

    payload = stdout.strip()
    if not payload:
        return None, None, None, stderr.strip() or "faster-whisper transcription failed without output"

    try:
        result = json.loads(payload)
    except json.JSONDecodeError as exc:
        return None, None, None, f"failed to decode faster-whisper result: {exc}"

    transcript = result.get("transcript")
    transcript_file = result.get("transcript_file")
    segments_file = result.get("segments_file")
    warning = result.get("warning", "")
    if transcript:
        return transcript, transcript_file, segments_file, warning
    return None, None, None, warning or stderr.strip() or "faster-whisper returned empty text"


def fetch_video_transcript(
    url: str,
    *,
    output_dir: Path,
    source_id: str | None = None,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    whisper_model_name: str = DEFAULT_FASTER_WHISPER_MODEL,
    asr_language: str | None = "zh",
    write_metadata_text: bool = True,
    whisper_compute_type: str = DEFAULT_FASTER_WHISPER_COMPUTE_TYPE,
    whisper_beam_size: int = DEFAULT_FASTER_WHISPER_BEAM_SIZE,
) -> VideoTranscriptResult:
    resolved_source_id = safe_source_id(source_id) if source_id else safe_source_id(url)
    skill_output_dir, video_output_dir = resolve_output_dirs(output_dir, resolved_source_id)
    video_output_dir.mkdir(parents=True, exist_ok=True)
    resolved_cookies_file = resolve_cookies_file(url, cookies_file)

    metadata, meta_error = fetch_video_metadata(
        url,
        cookies_from_browser=cookies_from_browser,
        cookies_file=resolved_cookies_file,
    )
    metadata_file, metadata_char_count = (
        save_metadata_text(video_output_dir, resolved_source_id, metadata) if write_metadata_text else (None, 0)
    )
    audio_duration_seconds = coerce_duration_seconds((metadata or {}).get("duration"))

    pre_download_cleanup_warning = prune_oldest_audio_if_skill_over_limit(skill_output_dir)
    audio_path, audio_warning = download_video_audio(
        url,
        target_dir=video_output_dir,
        source_id=resolved_source_id,
        cookies_from_browser=cookies_from_browser,
        cookies_file=resolved_cookies_file,
    )
    if not audio_path:
        return VideoTranscriptResult(
            url=url,
            source_id=resolved_source_id,
            success=False,
            fetch_status="partial" if metadata_file else "failed",
            asr_status="audio_download_failed",
            transcript_source=None,
            transcript=None,
            transcript_char_count=0,
            transcript_file=None,
            segments_file=None,
            transcript_path=None,
            segments_path=None,
            chunk_manifest_file=None,
            chunk_manifest_path=None,
            chunk_count=0,
            duration_seconds=audio_duration_seconds,
            recommended_timeout_seconds=estimate_outer_timeout_seconds(audio_duration_seconds),
            audio_file=None,
            metadata_file=metadata_file,
            metadata_char_count=metadata_char_count,
            title=(metadata or {}).get("title"),
            uploader=(metadata or {}).get("uploader"),
            warning=combine_warnings(pre_download_cleanup_warning, audio_warning, meta_error),
        )

    delete_current_audio_at_end = audio_path.stat().st_size > MAX_SKILL_AUDIO_BYTES
    asr_text, asr_file, segments_file, asr_warning = transcribe_audio_with_whisper(
        audio_path,
        output_dir=video_output_dir,
        source_id=resolved_source_id,
        model_name=whisper_model_name,
        language=asr_language,
        compute_type=whisper_compute_type,
        beam_size=whisper_beam_size,
        audio_duration_seconds=audio_duration_seconds,
    )
    if asr_text:
        transcript_path = str((video_output_dir / asr_file).resolve()) if asr_file else None
        resolved_segments_path = video_output_dir / segments_file if segments_file else None
        chunk_manifest_file, chunk_count = (
            write_chunk_manifest(resolved_segments_path, output_dir=video_output_dir, source_id=resolved_source_id)
            if resolved_segments_path
            else (None, 0)
        )
        chunk_manifest_path = (
            str((video_output_dir / chunk_manifest_file).resolve()) if chunk_manifest_file else None
        )
        result = VideoTranscriptResult(
            url=url,
            source_id=resolved_source_id,
            success=True,
            fetch_status="fetched",
            asr_status="transcribed",
            transcript_source="asr",
            transcript=asr_text,
            transcript_char_count=len(asr_text),
            transcript_file=asr_file,
            segments_file=segments_file,
            transcript_path=transcript_path,
            segments_path=str(resolved_segments_path.resolve()) if resolved_segments_path else None,
            chunk_manifest_file=chunk_manifest_file,
            chunk_manifest_path=chunk_manifest_path,
            chunk_count=chunk_count,
            duration_seconds=audio_duration_seconds,
            recommended_timeout_seconds=estimate_outer_timeout_seconds(audio_duration_seconds),
            audio_file=audio_path.name,
            metadata_file=metadata_file,
            metadata_char_count=metadata_char_count,
            title=(metadata or {}).get("title"),
            uploader=(metadata or {}).get("uploader"),
            warning=combine_warnings(
                pre_download_cleanup_warning,
                "audio downloaded and transcribed with Whisper ASR",
            ),
        )
    else:
        result = VideoTranscriptResult(
            url=url,
            source_id=resolved_source_id,
            success=False,
            fetch_status="partial" if metadata_file else "failed",
            asr_status="transcription_failed",
            transcript_source=None,
            transcript=None,
            transcript_char_count=0,
            transcript_file=None,
            segments_file=None,
            transcript_path=None,
            segments_path=None,
            chunk_manifest_file=None,
            chunk_manifest_path=None,
            chunk_count=0,
            duration_seconds=audio_duration_seconds,
            recommended_timeout_seconds=estimate_outer_timeout_seconds(audio_duration_seconds),
            audio_file=audio_path.name,
            metadata_file=metadata_file,
            metadata_char_count=metadata_char_count,
            title=(metadata or {}).get("title"),
            uploader=(metadata or {}).get("uploader"),
            warning=combine_warnings(pre_download_cleanup_warning, asr_warning, audio_warning, meta_error),
        )

    if delete_current_audio_at_end:
        size_mb = round(audio_path.stat().st_size / (1024 * 1024), 2)
        delete_error = delete_file(audio_path)
        auto_delete_warning = (
            delete_error
            if delete_error
            else f"current audio {audio_path.name} ({size_mb}MB) exceeded 200MB and was auto-deleted after processing"
        )
        result.warning = combine_warnings(result.warning, auto_delete_warning)

    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch transcript from video audio with faster-whisper ASR.")
    parser.add_argument("--url", default="", help="Video URL.")
    parser.add_argument("--output-dir", default="", help="Directory for transcript/audio/meta outputs.")
    parser.add_argument("--source-id", default="", help="Optional stable file prefix.")
    parser.add_argument("--cookies-from-browser", default="", help="Browser name for yt-dlp cookies, e.g. edge.")
    parser.add_argument("--cookies-file", default="", help="cookies.txt path for yt-dlp.")
    parser.add_argument(
        "--whisper-model",
        default=DEFAULT_FASTER_WHISPER_MODEL,
        help="Deprecated compatibility option; transcription always uses the configured large model.",
    )
    parser.add_argument(
        "--whisper-compute-type",
        default=DEFAULT_FASTER_WHISPER_COMPUTE_TYPE,
        help="faster-whisper compute type, e.g. float16 or int8.",
    )
    parser.add_argument("--whisper-beam-size", default=DEFAULT_FASTER_WHISPER_BEAM_SIZE, type=int, help="faster-whisper beam size.")
    parser.add_argument("--asr-language", default="zh", help="Whisper language hint. Use auto to disable hint.")
    parser.add_argument("--no-metadata-text", action="store_true", help="Do not write title/description text file.")
    parser.add_argument("--json", action="store_true", help="Print full result as JSON.")
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Fetch metadata and print duration plus the recommended outer command timeout without downloading audio.",
    )
    parser.add_argument("--internal-transcribe-audio", default="", help=argparse.SUPPRESS)
    parser.add_argument("--internal-transcribe-output-dir", default="", help=argparse.SUPPRESS)
    parser.add_argument("--internal-transcribe-source-id", default="", help=argparse.SUPPRESS)
    return parser


def configure_stdout_encoding() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> None:
    configure_stdout_encoding()
    parser = build_arg_parser()
    args = parser.parse_args()

    language = None if args.asr_language.strip().lower() == "auto" else args.asr_language.strip()
    if args.internal_transcribe_audio:
        if not args.internal_transcribe_output_dir or not args.internal_transcribe_source_id:
            parser.error("internal transcription mode requires output dir and source id")
        result = {}
        transcript, transcript_file, segments_file, warning = transcribe_audio_locally(
            Path(args.internal_transcribe_audio),
            output_dir=Path(args.internal_transcribe_output_dir),
            source_id=args.internal_transcribe_source_id,
            model_name=args.whisper_model,
            language=language,
            compute_type=args.whisper_compute_type,
            beam_size=args.whisper_beam_size,
        )
        result["success"] = bool(transcript)
        result["transcript"] = transcript
        result["transcript_file"] = transcript_file
        result["segments_file"] = segments_file
        result["warning"] = warning
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.url or not args.output_dir:
        parser.error("--url and --output-dir are required")

    if args.probe_only:
        resolved_cookies_file = resolve_cookies_file(args.url, args.cookies_file or None)
        metadata, warning = fetch_video_metadata(
            args.url,
            cookies_from_browser=args.cookies_from_browser or None,
            cookies_file=resolved_cookies_file,
        )
        duration_seconds = coerce_duration_seconds((metadata or {}).get("duration"))
        probe_result = {
            "success": metadata is not None,
            "duration_seconds": duration_seconds,
            "recommended_timeout_seconds": estimate_outer_timeout_seconds(duration_seconds),
            "title": (metadata or {}).get("title"),
            "uploader": (metadata or {}).get("uploader"),
            "warning": warning or "",
        }
        print(json.dumps(probe_result, ensure_ascii=False, indent=2))
        return

    result = fetch_video_transcript(
        args.url,
        output_dir=Path(args.output_dir),
        source_id=args.source_id or None,
        cookies_from_browser=args.cookies_from_browser or None,
        cookies_file=args.cookies_file or None,
        whisper_model_name=args.whisper_model,
        asr_language=language,
        write_metadata_text=not args.no_metadata_text,
        whisper_compute_type=args.whisper_compute_type,
        whisper_beam_size=args.whisper_beam_size,
    )

    _skill_output_dir, video_output_dir = resolve_output_dirs(Path(args.output_dir), result.source_id)
    result_json_path = video_output_dir / f"{result.source_id}_result.json"
    result_json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"success: {result.success}")
    print(f"fetch_status: {result.fetch_status}")
    print(f"asr_status: {result.asr_status}")
    print(f"transcript_source: {result.transcript_source or ''}")
    print(f"transcript_char_count: {result.transcript_char_count}")
    print(f"transcript_file: {result.transcript_file or ''}")
    print(f"segments_file: {result.segments_file or ''}")
    print(f"transcript_path: {result.transcript_path or ''}")
    print(f"segments_path: {result.segments_path or ''}")
    print(f"chunk_manifest_file: {result.chunk_manifest_file or ''}")
    print(f"chunk_manifest_path: {result.chunk_manifest_path or ''}")
    print(f"chunk_count: {result.chunk_count}")
    print(f"duration_seconds: {result.duration_seconds or ''}")
    print(f"recommended_timeout_seconds: {result.recommended_timeout_seconds}")
    print(f"audio_file: {result.audio_file or ''}")
    print(f"metadata_file: {result.metadata_file or ''}")
    print(f"metadata_char_count: {result.metadata_char_count}")
    print(f"result_json: {result_json_path.name}")
    if result.warning:
        print(f"warning: {result.warning}")


if __name__ == "__main__":
    main()
