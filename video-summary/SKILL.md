---
name: video-summary
description: >
  Use this for any request to summarize, analyze, extract transcript from, or
  write about a YouTube/Bilibili/video URL or BV id, including Chinese prompts
  like "总结视频", "总结这个视频", "视频总结", "提取字幕", "B站视频总结", and "YouTube视频总结".
  Use this workflow before producing the answer; resolve short links or pages when
  needed to find the real video URL/BV id, then base the answer on transcript/ASR,
  not webpage title, description, comments, or metadata.
---

# Video Summary

Use this skill to extract a transcript from a YouTube or Bilibili video with ASR, then turn it into the format the user asked for.

## Trigger Policy

For any request involving a video summary, video transcript, video content analysis, chaptering, quote extraction, thread, or blog post, use this skill's workflow as the controlling workflow.

Do not summarize from webpage metadata, preview cards, titles, descriptions, comments, search results, or browser page text unless transcript extraction fails and the user explicitly accepts a metadata-only fallback.

If the user provides a short link, redirect URL, share URL, article page, or any video link without an obvious YouTube id or Bilibili `BV` id, it is acceptable to use `web` or `browser` first only to resolve the canonical video URL, extract the `BV`/video id, or follow redirects. After that, run the transcript extraction step and produce the answer from transcript/ASR content.

For Bilibili inputs, normalize the input into a standard video URL before extraction when needed. Support:

- standard video URLs such as `https://www.bilibili.com/video/BVxxxxxxx/`
- bare `BV` ids such as `BV1jsdsBBE7y`
- watch-later URLs such as `https://www.bilibili.com/list/watchlater/?bvid=BVxxxxxxx`

## Required Environment

- Script: `/opt/data/skills/media/video-summary/scripts/fetch_video_transcript.py`
- `HF_HOME=/opt/hf-cache`
- `HUGGINGFACE_HUB_CACHE=/opt/hf-cache/hub`

## SOP

### 1. Probe Duration and Set the Outer Timeout

Run the helper once with `--probe-only --json`. Read `duration_seconds` and `recommended_timeout_seconds` from its output.

```bash
/usr/bin/python3 /opt/data/skills/media/video-summary/scripts/fetch_video_transcript.py --url "VIDEO_URL" --output-dir /tmp/video-summary --probe-only --json
```

Use the script's `recommended_timeout_seconds` as the timeout of the terminal/tool call that runs full extraction. The script computes it as `min(600, max(60, ceil(duration_seconds / 20)))`: 20x the video duration, with a 60-second minimum and a 600-second (10-minute) maximum. Do not add a manual buffer or replace it with a fixed timeout. If the terminal supports background execution, stop the extraction when this script-provided limit is reached.

### 2. Run Extraction

Run the helper script once with `--json` and use that JSON as the source of truth.

If the user provides a bare Bilibili `BV` id, convert it to `https://www.bilibili.com/video/BVxxxxxxx/` first.

If the user provides a Bilibili watch-later URL, extract the `bvid` query parameter and convert it to the same standard video URL before running extraction.

```bash
HF_HOME=/opt/hf-cache HUGGINGFACE_HUB_CACHE=/opt/hf-cache/hub /usr/bin/python3 /opt/data/skills/media/video-summary/scripts/fetch_video_transcript.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir /tmp/video-summary --json
```

Always use the configured large ASR model (`mobiuslabsgmbh/faster-whisper-large-v3-turbo`) for every video. Do not substitute a smaller model. For videos of 30 minutes or less, run only one Whisper transcription process. For videos longer than 30 minutes, at most two Whisper transcription processes may run concurrently; never start a third while two are active.

### 3. Check Result

Check these fields first:

- `success`
- `asr_status`
- `transcript_source`
- `transcript_char_count`
- `transcript_file`
- `segments_file`
- `transcript_path`
- `segments_path`
- `chunk_manifest_path`
- `chunk_count`
- `duration_seconds`
- `recommended_timeout_seconds`

Continue only if:

- `success=true`
- `asr_status=transcribed`
- `transcript_source=asr`
- `transcript_char_count > 0`
- `transcript_file` is present

### 4. Read Transcript

Use `transcript_path` from the JSON result directly. Do not guess the output directory or reconstruct a path from `transcript_file`. Base all downstream work on transcript artifacts, not on terminal preview text or the inline `transcript` JSON field.

Prefer `segments_file` when it is present. It is JSONL with `start`, `end`, and `text` fields and preserves the timeline. Use `transcript_file` for full-text reading and search.

Treat a video as long-form when it is over 30 minutes or its transcript exceeds about 30K characters. For long-form video, read every entry of `chunk_manifest_path` one at a time. The helper produces contiguous 10-minute JSONL windows with `index`, `start_seconds`, `end_seconds`, and `text`; use `chunk_count` as the required coverage count. Do not summarize the complete transcript in one pass.

Create a compact evidence note for every window containing:

- its time range or character range
- topics and claims introduced in that window
- supporting examples, evidence, steps, decisions, and conclusions
- details that must survive final synthesis

Merge adjacent windows only when they repeat the same material. Keep the window notes available until the final coverage check. If the manifest is missing, use `segments_path` to create equivalent contiguous 8-12 minute windows before writing the summary.

### 5. Produce Output

Supported outputs:

- `transcript`
- `summary`
- `chapters`
- `chapter summaries`
- `quotes`
- `thread`
- `blog post`

If the user does not specify a format, return a `summary`.

When writing a summary, prefer short paragraphs over bullet lists. Start with a brief factual paragraph covering the video title, creator, and topic, then follow with paragraph-style content summary.

Do not use a fixed short summary length. Scale the output length with the source length and information density:

- For short or simple videos, a concise summary is fine.
- For long videos or information-dense videos, write a substantially longer summary that preserves all major points, arguments, examples, steps, decisions, and conclusions.
- If the transcript was read in chunks, synthesize across all chunks instead of summarizing only the beginning or ending.
- Do not omit important sections just to keep the answer brief unless the user explicitly asks for a short summary.
- When a video has many distinct topics, use section headings or chapter-style organization to keep the longer summary readable.

Use these default detail budgets unless the user requests a different length. Treat them as coverage targets, not word-count padding:

| Duration | Default organization | Approximate Chinese summary length |
| --- | --- | --- |
| Up to 15 min | 3–5 topic paragraphs | 600–1,200 characters |
| 15–45 min | 5–8 topic sections | 1,200–2,500 characters |
| 45–90 min | 8–12 topic sections | 2,500–4,500 characters |
| Over 90 min | At least one section per 8–12 substantive minutes | 4,000+ characters; split into parts if needed |

Use the upper end for tutorials, lectures, debates, and information-dense interviews. Repetitive material may produce a shorter result, but state which spans were consolidated as repetition.

For videos over 30 minutes, default to a layered result:

1. A brief executive summary.
2. Detailed chapter-style summaries organized by time or topic.
3. Key conclusions, decisions, or reusable actions when applicable.

For technical or tutorial-heavy videos, prioritize extracting:

- the workflow or step sequence
- the toolchain and how each tool is used
- concrete techniques, decisions, constraints, and reusable methods

For these videos, focus less on rhetorical framing and more on what the viewer could actually repeat or apply.

### 6. Final Check

Before replying, confirm that the response is based on the transcript artifacts, that the requested format was followed, and that the final summary reflects the transcript content rather than only metadata.

For long-form video, build a coverage ledger listing every manifest window and mark it `covered`, `merged as repetition`, or `non-substantive`. Do not reply until every `chunk_count` window has a status. Check that the final result preserves each window's distinct claims, examples, steps, decisions, and conclusions instead of describing only the beginning, ending, or overall theme.

### Bilibili Subtitle Fallback (Fast Path)

If ASR extraction fails or produces poor quality, attempt Bilibili subtitle download as a fallback. Do not abandon a still-running extraction merely because a fixed short wait elapsed.

Prerequisites:
- Check if Bilibili cookies exist at `/tmp/bilibili_cookies.txt`
- If missing, cookies may be stored in yt-dlp config; try without `--cookies`

Steps:
1. Check available subtitles with yt-dlp:
   ```bash
   yt-dlp --cookies /tmp/bilibili_cookies.txt --list-subs "VIDEO_URL"
   ```
2. If `ai-zh` (AI-generated Chinese subtitles) is available, download it:
   ```bash
   yt-dlp --cookies /tmp/bilibili_cookies.txt --write-subs --sub-langs ai-zh --skip-download --convert-subs srt -o "subtitle" "VIDEO_URL"
   ```
3. Read the `.zh.zh.srt` file, extract plain text by stripping timestamps and sequence numbers
4. If `ai-zh` is not available, try `zh-Hans` or fall back to ASR

Note: Bilibili subtitles require auth (cookies). Use subtitles before starting a separate fallback ASR process. Only videos longer than 30 minutes may use two concurrent Whisper transcription processes; otherwise use one.

## If It Fails

- If ASR extraction fails after the dynamically sized timeout, report the script error and stop. Do not implement an ad hoc manual transcription pipeline in the conversation.
- If the transcript file is not found at the first guessed path, use the JSON result and output directory to locate the actual transcript file before summarizing.
- If tool output is truncated, continue from the transcript file and JSON fields instead of terminal preview text.
- If the required cache environment is missing, report the configuration problem directly.
