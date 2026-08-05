import os
import sys
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import boto3
import botocore


def get_cst_date() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def build_source_prefix(prefix: str, date: datetime) -> str:
    return f"{prefix}/{date.year}/{date.month:02d}/"


def build_dest_base(prefix: str, date: datetime) -> str:
    return f"{prefix}/{date.strftime('%Y-%m-%d')}"


def create_s3_client(endpoint: str, region: str, access_key: str, secret_key: str) -> botocore.client.BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def list_images(s3, bucket: str, prefix: str) -> list[str]:
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".jpg"):
                keys.append(key)
    keys.sort()
    return keys


def download_images(s3, bucket: str, keys: list[str], dest_dir: Path) -> list[Path]:
    local_paths = []
    for key in keys:
        filename = Path(key).name
        local = dest_dir / filename
        s3.download_file(bucket, key, str(local))
        local_paths.append(local)
    return local_paths


def compose_video(image_paths: list[Path], fps: int, output_path: Path) -> float:
    total_frames = len(image_paths)
    duration = total_frames / fps

    concat_file = output_path.with_suffix(".concat")
    with open(concat_file, "w") as f:
        for img in image_paths:
            f.write(f"file '{img.resolve()}'\n")
            f.write(f"duration {1/fps:.6f}\n")
        f.write(f"file '{image_paths[-1].resolve()}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file.resolve()),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_path.resolve()),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(e.stderr, end="")
        raise
    concat_file.unlink()
    return duration


def generate_manifest(
    source_prefix: str,
    date: datetime,
    fps: int,
    total_frames: int,
    duration: float,
    image_keys: list[str],
) -> str:
    lines = []
    lines.append(f"Source prefix: {source_prefix}")
    lines.append(f"Processing date: {date.strftime('%Y-%m-%d %H:%M:%S')} UTC+8")
    lines.append(f"Frame rate: {fps}")
    lines.append(f"Total frames: {total_frames}")
    lines.append(f"Duration: {duration:.2f}s")
    lines.append("Images:")
    for key in image_keys:
        lines.append(f"  {key}")
    return "\n".join(lines) + "\n"


def upload_file(s3, bucket: str, key: str, local_path: Path):
    s3.upload_file(str(local_path), bucket, key)


def main():
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg not found in PATH")
        sys.exit(1)

    try:
        fps = int(os.environ["FPS"])
    except ValueError:
        print(f"Error: FPS must be an integer, got: {os.environ['FPS']}")
        sys.exit(1)

    try:
        endpoint = os.environ["SOURCE_S3_ENDPOINT"]
        region = os.environ["SOURCE_S3_REGION"]
        access_key = os.environ["SOURCE_S3_ACCESS_KEY"]
        secret_key = os.environ["SOURCE_S3_SECRET_KEY"]
        bucket = os.environ["SOURCE_S3_BUCKET"]
        source_prefix = os.environ["SOURCE_PREFIX"]

        dest_endpoint = os.environ["DEST_S3_ENDPOINT"]
        dest_region = os.environ["DEST_S3_REGION"]
        dest_access_key = os.environ["DEST_S3_ACCESS_KEY"]
        dest_secret_key = os.environ["DEST_S3_SECRET_KEY"]
        dest_bucket = os.environ["DEST_S3_BUCKET"]
        dest_prefix = os.environ["DEST_PREFIX"]

        date = get_cst_date()
        source_path = build_source_prefix(source_prefix, date)
        dest_base = build_dest_base(dest_prefix, date)

        print(f"Processing date: {date.strftime('%Y-%m-%d')} (UTC+8)")
        print(f"Source prefix: {source_path}")
        print(f"Dest base: {dest_base}")

        s3_source = create_s3_client(endpoint, region, access_key, secret_key)
        s3_dest = create_s3_client(dest_endpoint, dest_region, dest_access_key, dest_secret_key)

        keys = list_images(s3_source, bucket, source_path)
        if not keys:
            print("No images found, exiting.")
            sys.exit(0)

        print(f"Found {len(keys)} images")

        tmpdir = Path(tempfile.mkdtemp(prefix="i2v_"))
        try:
            local_paths = download_images(s3_source, bucket, keys, tmpdir)
            print(f"Downloaded {len(local_paths)} images")

            output_video = tmpdir / "output.mp4"
            duration = compose_video(local_paths, fps, output_video)
            print(f"Video composed: {duration:.2f}s at {fps} fps")

            manifest = generate_manifest(source_prefix, date, fps, len(keys), duration, keys)
            manifest_path = tmpdir / "manifest.txt"
            manifest_path.write_text(manifest, encoding="utf-8")

            video_key = f"{dest_base}.mp4"
            manifest_key = f"{dest_base}.txt"

            upload_file(s3_dest, dest_bucket, video_key, output_video)
            print(f"Uploaded: {video_key}")
            upload_file(s3_dest, dest_bucket, manifest_key, manifest_path)
            print(f"Uploaded: {manifest_key}")

            print("Done.")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()