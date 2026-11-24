import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from PIL import Image

import upload_cos_images as uploader


class UploadCosImagesTests(unittest.TestCase):
    def make_image(self, path: Path, image_format: str = "PNG", quality: int = 100):
        image = Image.new("RGB", (160, 120))
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                pixels[x, y] = ((x * 7) % 256, (y * 11) % 256, ((x + y) * 5) % 256)
        save_options = {"quality": quality} if image_format == "JPEG" else {}
        image.save(path, format=image_format, **save_options)

    def test_resolves_encoded_post_image_and_rewrites_only_local_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            post = root / "_posts" / "2026-11-05-example.md"
            image = root / "posts" / "2026" / "11" / "05" / "Pasted image.png"
            post.parent.mkdir()
            image.parent.mkdir(parents=True)
            post.write_text("![](Pasted%20image.png)\n![](https://example.com/a.png)\n", encoding="utf-8")
            self.make_image(image)

            resolved = uploader.resolve_local_image(root, post, "Pasted%20image.png")
            self.assertEqual(image, resolved)
            compression_dir = root / "compressed"
            compression_dir.mkdir()
            plan = uploader.make_plan(
                image, "https://img.example.com", "blog/images", compression_dir, 82
            )
            rewritten, count = uploader.rewrite_text(
                post.read_text(encoding="utf-8"), post, root, {image: plan}
            )

            self.assertEqual(1, count)
            self.assertIn(plan.public_url, rewritten)
            self.assertIn("https://example.com/a.png", rewritten)

    def test_content_hash_produces_same_object_key_for_same_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.png"
            second = root / "second.png"
            self.make_image(first)
            second.write_bytes(first.read_bytes())
            compression_dir = root / "compressed"
            compression_dir.mkdir()

            first_plan = uploader.make_plan(
                first, "https://img.example.com", "blog/images", compression_dir, 82
            )
            second_plan = uploader.make_plan(
                second, "https://img.example.com", "blog/images", compression_dir, 82
            )

            self.assertEqual(first_plan.object_key, second_plan.object_key)

    def test_html_image_source_is_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            post = root / "_posts" / "2026-11-05-example.md"
            image = root / "posts" / "2026" / "11" / "05" / "a.png"
            post.parent.mkdir()
            image.parent.mkdir(parents=True)
            self.make_image(image)
            text = '<img alt="x" src="a.png">'
            compression_dir = root / "compressed"
            compression_dir.mkdir()
            plan = uploader.make_plan(
                image, "https://img.example.com", "blog/images", compression_dir, 82
            )

            rewritten, count = uploader.rewrite_text(text, post, root, {image: plan})

            self.assertEqual(1, count)
            self.assertEqual(f'<img alt="x" src="{plan.public_url}">', rewritten)

    def test_png_is_converted_to_lossless_webp_before_hashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "screenshot.png"
            compression_dir = root / "compressed"
            compression_dir.mkdir()
            self.make_image(image)

            plan = uploader.make_plan(
                image, "https://img.example.com", "blog/images", compression_dir, 100
            )

            self.assertLess(plan.upload_size, plan.original_size)
            self.assertNotEqual(image, plan.upload_path)
            self.assertEqual(".webp", plan.upload_path.suffix)
            self.assertEqual(".webp", Path(plan.object_key).suffix)
            self.assertIn(uploader.sha256_file(plan.upload_path), plan.object_key)
            with Image.open(image) as original, Image.open(plan.upload_path) as compressed:
                self.assertEqual(
                    original.convert("RGBA").tobytes(),
                    compressed.convert("RGBA").tobytes(),
                )

    def test_original_is_kept_when_lossless_webp_is_larger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "photo.jpg"
            compression_dir = root / "compressed"
            compression_dir.mkdir()
            self.make_image(image, image_format="JPEG", quality=100)

            plan = uploader.make_plan(
                image, "https://img.example.com", "blog/images", compression_dir, 82
            )

            self.assertEqual(image, plan.upload_path)
            self.assertEqual(plan.original_size, plan.upload_size)
            self.assertEqual(".jpg", Path(plan.object_key).suffix)

    def test_restore_maps_public_hash_url_to_post_image_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            post = root / "_posts" / "2026-11-05-example.md"
            post.parent.mkdir()
            digest = "a" * 64
            public_url = f"https://img.example.com/blog/images/{digest}.png"
            text = f"![]({public_url})"
            settings = uploader.CosSettings(
                secret_id="",
                secret_key="",
                token=None,
                bucket="",
                region="",
                public_base_url="https://img.example.com",
                public_referer="https://example.com/",
                object_prefix="blog/images",
                image_quality=82,
            )

            replacements = uploader.restore_replacements_for_document(
                root, post, text, settings
            )
            rewritten = uploader.rewrite_restored_text(text, replacements)

            self.assertEqual(1, len(replacements))
            self.assertEqual(
                root / "posts" / "2026" / "11" / "05" / f"{digest}.png",
                replacements[0].local_path,
            )
            self.assertEqual(f"![]({digest}.png)", rewritten)

    def test_remote_cleanup_deletes_only_unreferenced_managed_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            posts = root / "_posts"
            posts.mkdir()
            used, unused, css, config, planned = (
                f"blog/images/{character * 64}.webp" for character in "abcde"
            )
            posts.joinpath("2026-11-05-example.md").write_text(
                f"![alt][image]\n\n[image]: https://img.example.com/{used}?size=1",
                encoding="utf-8",
            )
            root.joinpath("style.css").write_text(
                f".page {{ background: url(//old-cdn.example.com/{css}); }}",
                encoding="utf-8",
            )
            root.joinpath("_config.yml").write_text(
                f"image: https://img.example.com/{config.replace('/', '%2F')}",
                encoding="utf-8",
            )
            root.joinpath("dist").mkdir()
            root.joinpath("dist", "old.html").write_text(
                f'<img src="https://img.example.com/{unused}">', encoding="utf-8"
            )
            settings = self.remote_cleanup_settings()
            listing = [
                {
                    "IsTruncated": "true",
                    "Contents": [{"Key": used}, {"Key": unused}],
                },
                {
                    "IsTruncated": "false",
                    "Contents": [
                        {"Key": css},
                        {"Key": config},
                        {"Key": planned},
                        {"Key": "blog/images/readme.txt"},
                        {"Key": f"blog/images/nested/{'f' * 64}.png"},
                        {"Key": f"other/{'f' * 64}.png"},
                    ],
                },
            ]
            client = Mock()
            client.list_objects.side_effect = listing * 2
            client.delete_objects.return_value = {"Deleted": [{"Key": unused}]}
            with patch.object(uploader, "create_cos_client", return_value=client):
                previewed = uploader.prune_remote_objects(
                    root, settings, apply_changes=False, planned_keys=[planned]
                )
                client.delete_objects.assert_not_called()
                # The combined apply run has already written the new image URL.
                posts.joinpath("2026-11-05-new.md").write_text(
                    f"![](https://img.example.com/{planned})", encoding="utf-8"
                )
                deleted = uploader.prune_remote_objects(root, settings, apply_changes=True)

            self.assertEqual(1, previewed)
            self.assertEqual(1, deleted)
            self.assertEqual(
                [
                    call(Bucket="test", Prefix="blog/images/", Marker="", MaxKeys=1000),
                    call(Bucket="test", Prefix="blog/images/", Marker=unused, MaxKeys=1000),
                ] * 2,
                client.list_objects.call_args_list,
            )
            client.delete_objects.assert_called_once_with(
                Bucket="test", Delete={"Quiet": "false", "Object": [{"Key": unused}]}
            )

    def test_remote_cleanup_reports_partial_batch_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Mock()
            first, second, third = (
                f"blog/images/{character * 64}.png" for character in "abc"
            )
            client.list_objects.side_effect = [
                {"IsTruncated": "true", "Contents": [{"Key": first}, {"Key": second}]},
                {"IsTruncated": "false", "Contents": [{"Key": third}]},
            ]
            client.delete_objects.side_effect = [
                {
                    "Deleted": [{"Key": first}],
                    "Error": [{"Key": second, "Code": "AccessDenied"}],
                },
                {"Deleted": [{"Key": third}]},
            ]
            with (
                patch.object(uploader, "create_cos_client", return_value=client),
                patch.object(uploader, "COS_OBJECT_BATCH_SIZE", 2),
                self.assertRaisesRegex(RuntimeError, "deletion of 2/3"),
            ):
                uploader.prune_remote_objects(
                    Path(directory), self.remote_cleanup_settings(), apply_changes=True
                )
            self.assertEqual(
                [[first, second], [third]],
                [
                    [item["Key"] for item in request.kwargs["Delete"]["Object"]]
                    for request in client.delete_objects.call_args_list
                ],
            )

    def remote_cleanup_settings(self):
        return uploader.CosSettings(
            secret_id="test",
            secret_key="test",
            token=None,
            bucket="test",
            region="test",
            public_base_url="https://img.example.com",
            public_referer="https://example.com/",
            object_prefix="blog/images",
            image_quality=82,
        )


if __name__ == "__main__":
    unittest.main()
