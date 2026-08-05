# storage-i2v-s3: Image-to-Video S3 Automation

## Overview

A scheduled GitHub Action that downloads images from an S3-compatible storage, composites them into a video at a configured frame rate, and uploads the result (plus a manifest file) to another S3-compatible storage.

## Trigger

- **Schedule**: Daily at 01:00 CST (UTC+8) → cron `0 17 * * *` UTC
- **Manual**: `workflow_dispatch` also supported for reruns

## Tech Stack

- **Runtime**: Python 3.x
- **S3 Client**: `boto3` (S3-compatible, via endpoint override)
- **Video Compositing**: `ffmpeg` (via subprocess)
- **CI**: GitHub Actions (`ubuntu-latest`, `ffmpeg` pre-installed)

## Environment Variables

### Source S3 (image origin)

| Variable | Description |
|---|---|
| `SOURCE_S3_ENDPOINT` | Endpoint URL |
| `SOURCE_S3_REGION` | Region |
| `SOURCE_S3_ACCESS_KEY` | Access key |
| `SOURCE_S3_SECRET_KEY` | Secret key |
| `SOURCE_S3_BUCKET` | Bucket name |
| `SOURCE_PREFIX` | Custom prefix, e.g. `warden` |

### Destination S3 (video output)

| Variable | Description |
|---|---|
| `DEST_S3_ENDPOINT` | Endpoint URL |
| `DEST_S3_REGION` | Region |
| `DEST_S3_ACCESS_KEY` | Access key |
| `DEST_S3_SECRET_KEY` | Secret key |
| `DEST_S3_BUCKET` | Bucket name |
| `DEST_PREFIX` | Upload path prefix |

### Video

| Variable | Description |
|---|---|
| `FPS` | Output video frame rate, e.g. `30` |

## Workflow

### Step 1: Determine date in UTC+8

Use `datetime.now(timezone(timedelta(hours=8)))` to get the current CST date. This ensures the prefix is correct even when UTC is still the previous day.

### Step 2: Construct source path

```
{SOURCE_PREFIX}/{YYYY}/{MM}/
```

Example: `warden/2026/07/`

### Step 3: List & download images

- List all `.jpg` files under the source path
- Sort by filename (ascending) → chronological order by timestamp
- Download to a temporary directory

### Step 4: Compose video

- Read the first image to determine output resolution (width × height)
- Use ffmpeg to stitch images: `ffmpeg -framerate {FPS} -pattern_type glob -i '*.jpg' -c:v libx264 -pix_fmt yuv420p output.mp4`
- Calculate actual duration: `total_frames / FPS`

### Step 5: Generate manifest

Create a `.txt` file containing:

```
Source prefix: {SOURCE_PREFIX}
Date range: {YYYY-MM-DD HH:MM:SS} - {YYYY-MM-DD HH:MM:SS}
Frame rate: {FPS}
Total frames: {count}
Duration: {duration}s
Images:
  {filename1}
  {filename2}
  ...
```

### Step 6: Upload

- Upload `{DEST_PREFIX}/{YYYY-MM-DD}.mp4` to destination S3
- Upload `{DEST_PREFIX}/{YYYY-MM-DD}.txt` to destination S3

### Step 7: Cleanup

Remove temporary directory.

## File Structure

```
.
├── .github/workflows/daily.yml   # GitHub Actions workflow
├── main.py                       # Entry point, orchestrates all steps
├── requirements.txt              # Python dependencies
└── README.md                     # Usage & configuration
```

## Design Decisions

- **Single script**: The task has a single responsibility — one daily pipeline. A single `main.py` keeps it readable and maintainable.
- **boto3 + endpoint override**: Supports any S3-compatible service (AWS S3, MinIO, Cloudflare R2, Aliyun OSS, Tencent COS) via the same API.
- **Sort by filename**: Image filenames contain timestamps, so alphabetical sort gives chronological order.
- **First-image resolution**: Avoids hardcoding a resolution; automatically adapts to whatever the source produces.
- **Manifest `.txt`**: Provides full traceability of which images were used, at what FPS, and for how long.
- **UTC+8 in script**: The cron runs at UTC 17:00, but the script computes the date using UTC+8 so the prefix always reflects the correct local date.