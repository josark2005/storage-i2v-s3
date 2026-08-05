# storage-i2v-s3

自动下载 S3 兼容存储中的图像序列，合成为视频，上传到另一个 S3 兼容存储。

## 工作流程

每天北京时间 01:00（UTC 17:00）自动触发：

1. 根据 `SOURCE_PREFIX` + 当前日期（UTC+8）构造源路径 `{prefix}/{YYYY}/{MM}/`
2. 列出该路径下所有 `.jpg` 文件，按文件名排序（时间序）
3. 下载图像到临时目录
4. 用 ffmpeg 合成为 H.264 MP4，帧率由 `FPS` 环境变量指定，分辨率自适应第一张图片
5. 生成同名 `.txt` 说明文件（时间范围、图片列表、帧率、视频时长）
6. 上传到目标 S3 存储：`{DEST_PREFIX}/{YYYY-MM-DD}.mp4` + `.txt`
7. 清理临时文件

## 环境变量

### 源 S3（图片来源）

| 变量 | 说明 |
|---|---|
| `SOURCE_S3_ENDPOINT` | 源 S3 endpoint |
| `SOURCE_S3_REGION` | 源 S3 region |
| `SOURCE_S3_ACCESS_KEY` | 源 S3 access key |
| `SOURCE_S3_SECRET_KEY` | 源 S3 secret key |
| `SOURCE_S3_BUCKET` | 源 S3 bucket |
| `SOURCE_PREFIX` | 自定义前缀，如 `warden` |

### 目标 S3（视频输出）

| 变量 | 说明 |
|---|---|
| `DEST_S3_ENDPOINT` | 目标 S3 endpoint |
| `DEST_S3_REGION` | 目标 S3 region |
| `DEST_S3_ACCESS_KEY` | 目标 S3 access key |
| `DEST_S3_SECRET_KEY` | 目标 S3 secret key |
| `DEST_S3_BUCKET` | 目标 S3 bucket |
| `DEST_PREFIX` | 上传路径前缀 |

### 视频参数

| 变量 | 说明 |
|---|---|
| `FPS` | 输出视频帧率，如 `30` |

## 触发方式

- **定时触发**：每天 UTC 17:00（北京时间 01:00）
- **手动触发**：GitHub Actions 页面点击 `Run workflow`

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 确保 ffmpeg 已安装

# 设置环境变量后运行
python main.py
```