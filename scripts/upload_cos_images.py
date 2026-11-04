#!/usr/bin/env python3
"""Upload locally referenced post images to COS and rewrite Markdown links safely."""

from __future__ import annotations

import argparse
import hashlib
import html
import logging
import mimetypes
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, unquote, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen


MARKDOWN_IMAGE_RE = re.compile(
    r"!\[[^\]\n]*\]\(\s*(?:<(?P<angle>[^>\n]+)>|(?P<plain>[^\s)\n]+))"
)
HTML_IMAGE_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*(?P<quote>['\"])(?P<url>.*?)(?P=quote)",
    re.IGNORECASE,
)
POST_DATE_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})-")
IMAGE_SUFFIXES = {
    ".avif",
    ".bmp",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}


@dataclass(frozen=True)
class ImageReference:
    start: int
    end: int
    target: str


@dataclass(frozen=True)
class PlannedImage:
    local_path: Path
    upload_path: Path
    object_key: str
    public_url: str
    content_type: str
    original_size: int
    upload_size: int

    @property
    def saved_bytes(self) -> int:
        return self.original_size - self.upload_size

    @property
    def saved_percent(self) -> float:
        if not self.original_size:
            return 0.0
        return self.saved_bytes * 100 / self.original_size


@dataclass(frozen=True)
class RestoreReplacement:
    start: int
    end: int
    object_key: str
    local_path: Path
    local_reference: str


@dataclass(frozen=True)
class CosSettings:
    secret_id: str
    secret_key: str
    token: str | None
    bucket: str
    region: str
    public_base_url: str
    public_referer: str
    object_prefix: str
    image_quality: int


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"{path}:{line_number}: invalid environment variable name")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def iter_image_references(text: str) -> list[ImageReference]:
    references: list[ImageReference] = []
    for match in MARKDOWN_IMAGE_RE.finditer(text):
        group = "angle" if match.group("angle") is not None else "plain"
        references.append(
            ImageReference(match.start(group), match.end(group), match.group(group))
        )
    for match in HTML_IMAGE_RE.finditer(text):
        references.append(
            ImageReference(match.start("url"), match.end("url"), match.group("url"))
        )
    return sorted(references, key=lambda item: item.start)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_local_image(repo_root: Path, markdown_path: Path, target: str) -> Path | None:
    target = html.unescape(target.strip())
    if not target or target.startswith("//"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None

    decoded_path = unquote(parsed.path).replace("\\", "/")
    if not decoded_path:
        return None

    relative = Path(decoded_path.lstrip("/"))
    candidates: list[Path] = []
    if decoded_path.startswith("/"):
        candidates.append(repo_root / relative)
    else:
        date_match = POST_DATE_RE.match(markdown_path.name)
        if date_match:
            candidates.append(
                repo_root
                / "posts"
                / date_match.group("year")
                / date_match.group("month")
                / date_match.group("day")
                / relative
            )
        candidates.extend((markdown_path.parent / relative, repo_root / relative))

    for candidate in candidates:
        resolved = candidate.resolve()
        if (
            is_within(resolved, repo_root)
            and resolved.is_file()
            and resolved.suffix.lower() in IMAGE_SUFFIXES
        ):
            return resolved
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compressed_upload_path(path: Path, output_dir: Path, quality: int) -> Path:
    suffix = path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        return path

    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise RuntimeError(
            "Pillow is not installed; run: "
            "python3 -m pip install -r scripts/requirements-cos-images.txt"
        ) from error

    temporary_name = hashlib.sha256(str(path).encode("utf-8")).hexdigest() + ".webp"
    candidate = output_dir / temporary_name
    try:
        with Image.open(path) as source:
            if getattr(source, "is_animated", False):
                return path
            image = ImageOps.exif_transpose(source)
            image.save(
                candidate,
                format="WEBP",
                lossless=True,
                quality=quality,
                method=6,
                exact=True,
            )
    except Exception as error:
        candidate.unlink(missing_ok=True)
        raise RuntimeError(f"could not compress image: {path}") from error

    if candidate.stat().st_size >= path.stat().st_size:
        candidate.unlink()
        return path
    return candidate


def make_plan(
    path: Path,
    public_base_url: str,
    object_prefix: str,
    compression_dir: Path,
    quality: int,
) -> PlannedImage:
    upload_path = compressed_upload_path(path, compression_dir, quality)
    suffix = upload_path.suffix.lower()
    digest = sha256_file(upload_path)
    object_key = "/".join(part for part in (object_prefix.strip("/"), f"{digest}{suffix}") if part)
    public_url = f"{public_base_url.rstrip('/')}/{quote(object_key, safe='/~')}"
    content_type = mimetypes.guess_type(upload_path.name)[0] or "application/octet-stream"
    return PlannedImage(
        local_path=path,
        upload_path=upload_path,
        object_key=object_key,
        public_url=public_url,
        content_type=content_type,
        original_size=path.stat().st_size,
        upload_size=upload_path.stat().st_size,
    )


def rewrite_text(
    text: str,
    markdown_path: Path,
    repo_root: Path,
    plans_by_path: dict[Path, PlannedImage],
) -> tuple[str, int]:
    replacements: list[tuple[int, int, str]] = []
    for reference in iter_image_references(text):
        local_path = resolve_local_image(repo_root, markdown_path, reference.target)
        if local_path is not None and local_path in plans_by_path:
            replacements.append((reference.start, reference.end, plans_by_path[local_path].public_url))

    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]
    return text, len(replacements)


def atomic_write(path: Path, content: str) -> None:
    original_mode = stat.S_IMODE(path.stat().st_mode)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, original_mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as destination, source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def markdown_files(repo_root: Path, selected: Iterable[str]) -> list[Path]:
    selected = list(selected)
    if selected:
        paths = [(repo_root / item).resolve() if not Path(item).is_absolute() else Path(item).resolve() for item in selected]
    else:
        paths = sorted((repo_root / "_posts").glob("*.md"))
    invalid = [path for path in paths if not path.is_file() or path.suffix.lower() != ".md" or not is_within(path, repo_root)]
    if invalid:
        raise ValueError("every input must be a Markdown file inside the repository")
    return sorted(set(paths))


def all_markdown_files(repo_root: Path) -> Iterable[Path]:
    excluded = {".git", ".jekyll-cache", ".venv-cos-upload", "_site", "dist"}
    for path in repo_root.rglob("*.md"):
        if not any(part in excluded for part in path.relative_to(repo_root).parts):
            yield path


def still_referenced(repo_root: Path, image_path: Path) -> bool:
    for markdown_path in all_markdown_files(repo_root):
        try:
            text = markdown_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for reference in iter_image_references(text):
            if resolve_local_image(repo_root, markdown_path, reference.target) == image_path:
                return True
    return False


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"missing {name} in the local environment file")
    return value


def get_settings(require_credentials: bool, quality_override: int | None = None) -> CosSettings:
    public_base_url = os.environ.get("COS_PUBLIC_BASE_URL", "https://img.h1kari.cn").strip()
    public_referer = os.environ.get("COS_PUBLIC_REFERER", "https://h1kari.cn/").strip()
    object_prefix = os.environ.get("COS_OBJECT_PREFIX", "blog/images").strip()
    quality_text = str(quality_override) if quality_override is not None else os.environ.get("COS_IMAGE_QUALITY", "82")
    if not public_base_url.startswith("https://"):
        raise ValueError("COS_PUBLIC_BASE_URL must use HTTPS")
    if not public_referer.startswith("https://"):
        raise ValueError("COS_PUBLIC_REFERER must use HTTPS")
    try:
        image_quality = int(quality_text)
    except ValueError as error:
        raise ValueError("COS_IMAGE_QUALITY must be an integer from 1 to 100") from error
    if not 1 <= image_quality <= 100:
        raise ValueError("COS_IMAGE_QUALITY must be an integer from 1 to 100")
    secret_id = os.environ.get("COS_SECRET_ID", "").strip()
    secret_key = os.environ.get("COS_SECRET_KEY", "").strip()
    bucket = os.environ.get("COS_BUCKET", "").strip()
    region = os.environ.get("COS_REGION", "").strip()
    if require_credentials:
        secret_id = required_env("COS_SECRET_ID")
        secret_key = required_env("COS_SECRET_KEY")
        bucket = required_env("COS_BUCKET")
        region = required_env("COS_REGION")
    return CosSettings(
        secret_id=secret_id,
        secret_key=secret_key,
        token=os.environ.get("COS_SESSION_TOKEN", "").strip() or None,
        bucket=bucket,
        region=region,
        public_base_url=public_base_url,
        public_referer=public_referer,
        object_prefix=object_prefix,
        image_quality=image_quality,
    )


def create_cos_client(settings: CosSettings):
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as error:
        raise RuntimeError(
            "COS SDK is not installed; run: "
            "python3 -m pip install -r scripts/requirements-cos-images.txt"
        ) from error

    logging.getLogger("qcloud_cos").setLevel(logging.CRITICAL)
    return CosS3Client(
        CosConfig(
            Region=settings.region,
            SecretId=settings.secret_id,
            SecretKey=settings.secret_key,
            Token=settings.token,
        )
    )


def upload_images(settings: CosSettings, plans: Iterable[PlannedImage]) -> None:
    client = create_cos_client(settings)
    for plan in plans:
        with plan.upload_path.open("rb") as stream:
            client.put_object(
                Bucket=settings.bucket,
                Key=plan.object_key,
                Body=stream,
                EnableMD5=True,
                ContentType=plan.content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
        print(
            f"uploaded: {plan.local_path.relative_to(Path.cwd())} "
            f"({plan.upload_size} bytes) -> {plan.public_url}"
        )


def object_key_from_public_url(target: str, settings: CosSettings) -> str | None:
    target_url = urlsplit(html.unescape(target.strip()))
    base_url = urlsplit(settings.public_base_url.rstrip("/"))
    if (
        target_url.scheme != base_url.scheme
        or target_url.netloc != base_url.netloc
        or not target_url.path.startswith(base_url.path.rstrip("/") + "/")
    ):
        return None
    object_key = unquote(target_url.path[len(base_url.path.rstrip("/")) :].lstrip("/"))
    prefix = settings.object_prefix.strip("/")
    if prefix and not object_key.startswith(prefix + "/"):
        return None
    filename = Path(object_key).name
    if Path(filename).suffix.lower() not in IMAGE_SUFFIXES:
        return None
    if not re.fullmatch(r"[0-9a-f]{64}\.[A-Za-z0-9]+", filename):
        return None
    return object_key


def is_managed_object_key(object_key: str, settings: CosSettings) -> bool:
    prefix = settings.object_prefix.strip("/")
    expected_parent = f"{prefix}/" if prefix else ""
    if not object_key.startswith(expected_parent):
        return False
    filename = object_key[len(expected_parent) :]
    if "/" in filename:
        return False
    return bool(re.fullmatch(r"[0-9a-f]{64}\.[A-Za-z0-9]+", filename)) and (
        Path(filename).suffix.lower() in IMAGE_SUFFIXES
    )


def referenced_remote_keys(repo_root: Path, settings: CosSettings) -> set[str]:
    keys: set[str] = set()
    for markdown_path in all_markdown_files(repo_root):
        try:
            text = markdown_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for reference in iter_image_references(text):
            object_key = object_key_from_public_url(reference.target, settings)
            if object_key is not None:
                keys.add(object_key)
    return keys


def list_managed_remote_objects(settings: CosSettings) -> set[str]:
    client = create_cos_client(settings)
    prefix = settings.object_prefix.strip("/")
    request_prefix = f"{prefix}/" if prefix else ""
    marker = ""
    objects: set[str] = set()
    while True:
        response = client.list_objects(
            Bucket=settings.bucket,
            Prefix=request_prefix,
            Marker=marker,
            MaxKeys=1000,
        )
        contents = response.get("Contents", []) or []
        for item in contents:
            object_key = item.get("Key", "")
            if is_managed_object_key(object_key, settings):
                objects.add(object_key)
        truncated = str(response.get("IsTruncated", "false")).lower() == "true"
        if not truncated:
            break
        next_marker = response.get("NextMarker") or (
            contents[-1].get("Key", "") if contents else ""
        )
        if not next_marker or next_marker == marker:
            raise RuntimeError("COS object listing did not provide a usable next marker")
        marker = next_marker
    return objects


def prune_remote_objects(
    repo_root: Path,
    settings: CosSettings,
    apply_changes: bool,
) -> int:
    referenced = referenced_remote_keys(repo_root, settings)
    remote = list_managed_remote_objects(settings)
    unused = sorted(remote - referenced)
    print(
        f"remote cleanup: {len(remote)} managed objects, "
        f"{len(referenced)} referenced, {len(unused)} unused"
    )
    for object_key in unused:
        print(f"remote unused: {Path(object_key).name}")
    if not unused:
        return 0
    if not apply_changes:
        print("remote cleanup dry run; add --apply to delete these objects")
        return len(unused)

    client = create_cos_client(settings)
    for object_key in unused:
        client.delete_object(Bucket=settings.bucket, Key=object_key)
        print(f"remote deleted: {Path(object_key).name}")
    return len(unused)


def restore_replacements_for_document(
    repo_root: Path,
    markdown_path: Path,
    text: str,
    settings: CosSettings,
) -> list[RestoreReplacement]:
    date_match = POST_DATE_RE.match(markdown_path.name)
    if not date_match:
        return []
    image_directory = (
        repo_root
        / "posts"
        / date_match.group("year")
        / date_match.group("month")
        / date_match.group("day")
    )
    replacements: list[RestoreReplacement] = []
    for reference in iter_image_references(text):
        object_key = object_key_from_public_url(reference.target, settings)
        if object_key is None:
            continue
        filename = Path(object_key).name
        replacements.append(
            RestoreReplacement(
                start=reference.start,
                end=reference.end,
                object_key=object_key,
                local_path=image_directory / filename,
                local_reference=quote(filename),
            )
        )
    return replacements


def rewrite_restored_text(text: str, replacements: Iterable[RestoreReplacement]) -> str:
    replacements = list(replacements)
    for replacement in reversed(replacements):
        text = (
            text[: replacement.start]
            + replacement.local_reference
            + text[replacement.end :]
        )
    return text


def download_public_objects(
    settings: CosSettings,
    object_keys: Iterable[str],
    download_dir: Path,
) -> dict[str, Path]:
    signer = None
    if all((settings.secret_id, settings.secret_key, settings.bucket, settings.region)):
        signer = create_cos_client(settings)

    def download_url(url: str, destination: Path) -> None:
        request = Request(
            url,
            headers={
                "User-Agent": "blog-image-restorer/1.0",
                "Referer": settings.public_referer,
            },
        )
        with urlopen(request, timeout=30) as response, destination.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)

    downloaded: dict[str, Path] = {}
    for object_key in sorted(set(object_keys)):
        destination = download_dir / Path(object_key).name
        unsigned_public_url = (
            f"{settings.public_base_url.rstrip('/')}/"
            f"{quote(object_key, safe='/~')}"
        )
        try:
            download_url(unsigned_public_url, destination)
        except HTTPError as error:
            destination.unlink(missing_ok=True)
            if error.code not in {401, 403} or signer is None:
                raise
            signed_origin_url = signer.get_presigned_url(
                Bucket=settings.bucket,
                Key=object_key,
                Method="GET",
                Expired=300,
                SignHost=False,
            )
            signature_query = urlsplit(signed_origin_url).query
            download_url(f"{unsigned_public_url}?{signature_query}", destination)
        expected_hash = destination.stem.lower()
        if sha256_file(destination) != expected_hash:
            destination.unlink(missing_ok=True)
            raise RuntimeError("downloaded image failed its content-hash check")
        downloaded[object_key] = destination
        print(f"downloaded: {Path(object_key).name}")
    return downloaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload post images to COS, rewrite image links, then delete unused local copies."
    )
    parser.add_argument("markdown", nargs="*", help="specific Markdown files; default: all files in _posts")
    parser.add_argument(
        "--env-file",
        default=".env.cos-upload",
        help="ignored local environment file (default: .env.cos-upload)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform upload/restore and file changes; without this flag, only show the plan",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="restore local images by downloading them from COS_PUBLIC_BASE_URL",
    )
    parser.add_argument(
        "--keep-local",
        action="store_true",
        help="rewrite links but do not delete local image files",
    )
    parser.add_argument(
        "--prune-remote",
        action="store_true",
        help="list unused managed COS images; combine with --apply to delete them",
    )
    parser.add_argument(
        "--quality",
        type=int,
        help="WebP lossless compression effort from 1 to 100 (default: COS_IMAGE_QUALITY or 82)",
    )
    return parser.parse_args()


def run_upload(
    repo_root: Path,
    documents: list[Path],
    settings: CosSettings,
    apply_changes: bool,
    keep_local: bool,
    prune_remote: bool,
) -> int:
    document_text: dict[Path, str] = {}
    local_images: set[Path] = set()
    unresolved: list[tuple[Path, str]] = []
    for markdown_path in documents:
        text = markdown_path.read_text(encoding="utf-8")
        document_text[markdown_path] = text
        for reference in iter_image_references(text):
            if urlsplit(html.unescape(reference.target)).scheme:
                continue
            local_path = resolve_local_image(repo_root, markdown_path, reference.target)
            if local_path is None:
                unresolved.append((markdown_path, reference.target))
            else:
                local_images.add(local_path)

    with tempfile.TemporaryDirectory(prefix="blog-cos-compress-") as directory:
        compression_dir = Path(directory)
        plans_by_path = {
            path: make_plan(
                path,
                settings.public_base_url,
                settings.object_prefix,
                compression_dir,
                settings.image_quality,
            )
            for path in sorted(local_images)
        }
        rewritten: dict[Path, tuple[str, int]] = {
            path: rewrite_text(text, path, repo_root, plans_by_path)
            for path, text in document_text.items()
        }

        print(f"mode: {'UPLOAD' if apply_changes else 'UPLOAD DRY RUN'}")
        print(f"documents: {len(documents)}, local images: {len(plans_by_path)}")
        total_original = sum(plan.original_size for plan in plans_by_path.values())
        total_upload = sum(plan.upload_size for plan in plans_by_path.values())
        for path, plan in plans_by_path.items():
            compression = (
                f"{plan.original_size} -> {plan.upload_size} bytes "
                f"(-{plan.saved_percent:.1f}%)"
                if plan.saved_bytes
                else f"{plan.original_size} bytes (original retained)"
            )
            print(f"plan: {path.relative_to(repo_root)} [{compression}] -> {plan.public_url}")
        if total_original:
            saved_percent = (total_original - total_upload) * 100 / total_original
            print(
                f"compression total: {total_original} -> {total_upload} bytes "
                f"(-{saved_percent:.1f}%)"
            )
        for path, target in unresolved:
            print(
                f"warning: unresolved local image in {path.relative_to(repo_root)}: {target}",
                file=sys.stderr,
            )

        if not plans_by_path and not prune_remote:
            print("nothing to upload")
            return 0
        if not apply_changes:
            if plans_by_path:
                print("upload dry run only; rerun with --apply after reviewing the plan")
            if prune_remote:
                try:
                    prune_remote_objects(repo_root, settings, apply_changes=False)
                except Exception as error:
                    print(
                        f"remote cleanup scan failed ({type(error).__name__})",
                        file=sys.stderr,
                    )
                    return 1
            return 0

        unique_plans = {plan.object_key: plan for plan in plans_by_path.values()}
        if unique_plans:
            try:
                upload_images(settings, unique_plans.values())
            except RuntimeError as error:
                print(f"error: {error}", file=sys.stderr)
                return 2
            except Exception as error:
                print(
                    f"upload failed ({type(error).__name__}); no Markdown files were changed "
                    "and no local images were deleted",
                    file=sys.stderr,
                )
                return 1

        for markdown_path, (new_text, replacement_count) in rewritten.items():
            if replacement_count and new_text != document_text[markdown_path]:
                atomic_write(markdown_path, new_text)
                print(
                    f"rewritten: {markdown_path.relative_to(repo_root)} "
                    f"({replacement_count} links)"
                )

        deleted = 0
        if keep_local:
            print("local images kept (--keep-local)")
        else:
            for image_path in plans_by_path:
                if still_referenced(repo_root, image_path):
                    print(f"kept (still referenced): {image_path.relative_to(repo_root)}")
                    continue
                image_path.unlink()
                deleted += 1
                print(f"deleted: {image_path.relative_to(repo_root)}")

        remote_deleted = 0
        if prune_remote:
            try:
                remote_deleted = prune_remote_objects(
                    repo_root, settings, apply_changes=True
                )
            except Exception as error:
                print(
                    f"remote cleanup failed ({type(error).__name__}); uploads and article "
                    "changes were kept, but unused remote images were not fully cleaned",
                    file=sys.stderr,
                )
                return 1
        print(
            f"done: uploaded {len(unique_plans)}, deleted {deleted} local, "
            f"deleted {remote_deleted} remote"
        )
        return 0


def run_restore(
    repo_root: Path,
    documents: list[Path],
    settings: CosSettings,
    apply_changes: bool,
) -> int:
    document_text = {path: path.read_text(encoding="utf-8") for path in documents}
    replacements_by_document = {
        path: restore_replacements_for_document(repo_root, path, text, settings)
        for path, text in document_text.items()
    }
    replacements = [
        replacement
        for document_replacements in replacements_by_document.values()
        for replacement in document_replacements
    ]
    print(f"mode: {'RESTORE' if apply_changes else 'RESTORE DRY RUN'}")
    print(f"documents: {len(documents)}, remote image links: {len(replacements)}")
    for replacement in replacements:
        print(
            f"plan: {Path(replacement.object_key).name} -> "
            f"{replacement.local_path.relative_to(repo_root)}"
        )
    if not replacements:
        print("nothing to restore")
        return 0
    if not apply_changes:
        print("dry run only; rerun with --restore --apply after reviewing the plan")
        return 0

    with tempfile.TemporaryDirectory(prefix="blog-cos-restore-") as directory:
        try:
            downloaded = download_public_objects(
                settings,
                (replacement.object_key for replacement in replacements),
                Path(directory),
            )
        except RuntimeError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        except Exception as error:
            print(
                f"restore download failed ({type(error).__name__}); no Markdown files were changed",
                file=sys.stderr,
            )
            return 1

        targets: dict[Path, str] = {}
        for replacement in replacements:
            previous_key = targets.setdefault(replacement.local_path, replacement.object_key)
            if previous_key != replacement.object_key:
                raise RuntimeError("two remote objects resolve to the same local restore path")
        for local_path, object_key in targets.items():
            source = downloaded[object_key]
            if local_path.exists() and sha256_file(local_path) != sha256_file(source):
                raise RuntimeError(f"refusing to overwrite a different local image: {local_path}")
        for local_path, object_key in targets.items():
            source = downloaded[object_key]
            if not local_path.exists():
                atomic_write_bytes(local_path, source)
                print(f"restored: {local_path.relative_to(repo_root)}")

        for markdown_path, document_replacements in replacements_by_document.items():
            if not document_replacements:
                continue
            rewritten = rewrite_restored_text(
                document_text[markdown_path], document_replacements
            )
            atomic_write(markdown_path, rewritten)
            print(
                f"rewritten: {markdown_path.relative_to(repo_root)} "
                f"({len(document_replacements)} links)"
            )
    print(f"done: restored {len(targets)} local images; remote objects were kept")
    return 0


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    try:
        if args.restore and args.keep_local:
            raise ValueError("--keep-local only applies to uploads")
        if args.restore and args.prune_remote:
            raise ValueError("--prune-remote cannot be combined with --restore")
        load_env_file((repo_root / args.env_file).resolve())
        settings = get_settings(
            require_credentials=(args.apply and not args.restore) or args.prune_remote,
            quality_override=args.quality,
        )
        documents = markdown_files(repo_root, args.markdown)
        if args.restore:
            return run_restore(repo_root, documents, settings, args.apply)
        return run_upload(
            repo_root,
            documents,
            settings,
            args.apply,
            args.keep_local,
            args.prune_remote,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
