import tempfile
import unittest
from pathlib import Path

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

    def test_jpeg_is_compressed_before_hashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "large.jpg"
            compression_dir = root / "compressed"
            compression_dir.mkdir()
            self.make_image(image, image_format="JPEG", quality=100)

            plan = uploader.make_plan(
                image, "https://img.example.com", "blog/images", compression_dir, 60
            )

            self.assertLess(plan.upload_size, plan.original_size)
            self.assertNotEqual(image, plan.upload_path)
            self.assertIn(uploader.sha256_file(plan.upload_path), plan.object_key)

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


if __name__ == "__main__":
    unittest.main()
