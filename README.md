
# video-summary

基于 `yt-dlp`、`ffmpeg` 与 `faster-whisper` 的视频转录与总结 Skill，支持 YouTube、Bilibili URL 和 Bilibili `BV` 号。

它会先获取视频时长，再以固定的 large Whisper 模型完成 ASR 转录；对长视频自动生成按时间切分的转录块，供 Agent 做完整覆盖的分段总结。

## 目录结构

```text
video-summary/
├── SKILL.md
├── scripts/
│   └── fetch_video_transcript.py
└── references/
    └── output-formats.md
```

## 功能

- 支持 YouTube 与 Bilibili 视频
- 支持 Bilibili 标准 URL、分享 URL、watch-later URL 与裸 `BV` 号
- 固定使用 `mobiuslabsgmbh/faster-whisper-large-v3-turbo`
- 自动获取视频时长并计算转录 timeout：

  ```text
  min(600, max(60, ceil(duration_seconds / 20)))
  ```

- 最低 timeout 为 60 秒，最高为 10 分钟
- 超过 30 分钟的视频自动生成约 10 分钟一个的 JSONL 转录块
- 输出完整转录、带时间戳 segments、分块清单和绝对产物路径
- Skill 规定长视频必须逐块阅读并完成覆盖检查后再总结

## 依赖

运行环境需要：

- Python 3.10+
- `yt-dlp`
- `ffmpeg` / `ffprobe`
- `faster-whisper`
- Hugging Face 模型缓存或可访问 Hugging Face 下载模型

示例安装：

```bash
pip install faster-whisper yt-dlp
```

请另外安装系统级 `ffmpeg`。

## 使用方式

探测视频时长与建议 timeout：

```bash
python scripts/fetch_video_transcript.py \
  --url "https://www.bilibili.com/video/BVxxxxxxxx/" \
  --output-dir /tmp/video-summary \
  --probe-only \
  --json
```

执行完整转录：

```bash
HF_HOME=/path/to/hf-cache \
HUGGINGFACE_HUB_CACHE=/path/to/hf-cache/hub \
python scripts/fetch_video_transcript.py \
  --url "https://www.bilibili.com/video/BVxxxxxxxx/" \
  --output-dir /tmp/video-summary \
  --json
```

## 输出字段

成功时 JSON 会包含：

- `transcript_path`：完整转录的绝对路径
- `segments_path`：逐句时间戳 JSONL 的绝对路径
- `chunk_manifest_path`：长视频分块清单的绝对路径
- `chunk_count`：分块数量
- `duration_seconds`：视频时长
- `recommended_timeout_seconds`：建议的完整转录 timeout
- `transcript_char_count`：转录字符数

长视频的分块清单为 JSONL，每行对应一个连续时间窗口：

```json
{
  "index": 1,
  "start_seconds": 0.0,
  "end_seconds": 600.0,
  "text": "..."
}
```

## Bilibili Cookie

部分 Bilibili 视频或字幕请求需要登录 Cookie。请在本地配置 Cookie 文件，且不要提交到 Git：

```text
private/bilibili_cookies.txt
```

可通过参数指定：

```bash
--cookies-file /path/to/cookies.txt
```

## 注意事项

- 不要上传 `.env`、Cookie、Hugging Face 模型缓存、音频文件或转录产物。
- 视频总结应基于转录内容，而不是标题、简介或评论。
- 对超过 30 分钟的视频，应逐块处理全部 `chunk_manifest_path` 内容，避免只总结开头或结尾。
```
