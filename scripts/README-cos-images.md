# COS article image uploader

This helper compresses locally referenced images from `_posts`, uploads the smaller payload to COS, rewrites the Markdown/HTML image URLs to a custom HTTPS domain, and removes local image files only after every upload and rewrite succeeds.

Static PNG, JPEG, and WebP files are converted to lossless WebP. Animated images, GIF, SVG, and other formats keep their original encoding. If WebP produces a larger file, the original bytes are uploaded instead. Temporary compressed files are removed automatically.

## Setup

```bash
python3 -m venv .venv-cos-upload
. .venv-cos-upload/bin/activate
python3 -m pip install -r scripts/requirements-cos-images.txt
cp .env.cos-upload.example .env.cos-upload
chmod 600 .env.cos-upload
```

Fill `.env.cos-upload` locally. It is ignored by Git. Use a CAM sub-account with only the minimum object-upload permission and rotate any credential that has ever been pasted into chat, logs, or source code.

Set `COS_IMAGE_QUALITY` from `1` to `100` to change the lossless WebP compression effort. This affects encoding time and file size, not visual quality. It can also be overridden per run with `--quality`.

`COS_PUBLIC_REFERER` is sent as the HTTP `Referer` header when restoring images. Set it to the blog origin allowed by the image-domain hotlink policy.

## Run

Preview all article changes without accessing COS:

```bash
./blog.sh images
```

Upload, rewrite links, and delete local images that are no longer referenced:

```bash
./blog.sh images --apply
```

Process one article, or keep local image files:

```bash
./blog.sh images --apply --keep-local "_posts/2026-11-05-example.md"
```

Use a different lossless compression effort:

```bash
./blog.sh images --quality 75
./blog.sh images --apply --quality 75
```

## Restore from the public image domain

Restoration downloads through `COS_PUBLIC_BASE_URL` (for example, the custom image CDN domain), sends `COS_PUBLIC_REFERER`, and never puts the bucket origin in the request URL. If the public request still returns 401/403 and local COS credentials are available, the script retries with a five-minute signature attached to the same custom-domain URL. It verifies each SHA-256 hash, recreates files under `posts/YYYY/MM/DD/`, and changes article links back to relative local links. Remote objects are never deleted.

Preview restoration:

```bash
./blog.sh images --restore
```

Download and restore:

```bash
./blog.sh images --restore --apply
```

Restore one article:

```bash
./blog.sh images --restore --apply "_posts/2026-11-05-example.md"
```

Object names use the full SHA-256 content hash of the final upload payload, so original image names are not exposed and identical image content is uploaded to the same stable URL.
