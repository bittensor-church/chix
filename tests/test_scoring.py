"""Tests for the scoring functions in validator.py."""

from PIL import Image, ImageDraw

from validator import (
    Score,
    composite_score,
    decode_png_b64,
    encode_png_b64,
    generate_synthetic_image,
    score_background_preservation,
    score_speed,
)


def _make_solid(color: tuple[int, int, int], size: tuple[int, int] = (64, 64)) -> str:
    return encode_png_b64(Image.new("RGB", size, color))


class TestBackgroundPreservation:
    def test_identical_images(self) -> None:
        b64 = _make_solid((100, 150, 200))
        assert score_background_preservation(b64, b64) == Score(1.0)

    def test_completely_different(self) -> None:
        a = _make_solid((0, 0, 0))
        b = _make_solid((255, 255, 255))
        assert score_background_preservation(a, b) == Score(0.0)

    def test_small_region_changed(self) -> None:
        """Changing ~6% of pixels should give a high score."""
        img = Image.new("RGB", (100, 100), (50, 100, 150))
        draw = ImageDraw.Draw(img)
        original_b64 = encode_png_b64(img)

        draw.rectangle([0, 0, 24, 24], fill=(255, 0, 0))
        modified_b64 = encode_png_b64(img)

        score = score_background_preservation(original_b64, modified_b64)
        assert score > 0.7

    def test_size_mismatch(self) -> None:
        a = _make_solid((0, 0, 0), (64, 64))
        b = _make_solid((0, 0, 0), (32, 32))
        assert score_background_preservation(a, b) == Score(0.0)


class TestSpeedScore:
    def test_instant(self) -> None:
        assert score_speed(0.0, 120.0) == Score(1.0)

    def test_at_max(self) -> None:
        assert score_speed(120.0, 120.0) == Score(0.0)

    def test_over_max(self) -> None:
        assert score_speed(200.0, 120.0) == Score(0.0)

    def test_half(self) -> None:
        assert abs(score_speed(60.0, 120.0) - Score(0.5)) < 1e-9


class TestCompositeScore:
    def test_perfect_scores(self) -> None:
        result = composite_score(Score(1.0), Score(1.0), Score(1.0), Score(1.0))
        assert abs(result - 1.0) < 1e-9

    def test_zero_scores(self) -> None:
        assert composite_score(Score(0.0), Score(0.0), Score(0.0), Score(0.0)) == Score(0.0)

    def test_weights_applied(self) -> None:
        # Only background = 1.0, rest = 0.0 -> result should be 0.4
        result = composite_score(Score(1.0), Score(0.0), Score(0.0), Score(0.0))
        assert abs(result - 0.4) < 1e-9


class TestImageUtilities:
    def test_encode_decode_roundtrip(self) -> None:
        original = Image.new("RGB", (32, 32), (42, 84, 126))
        b64 = encode_png_b64(original)
        decoded = decode_png_b64(b64)
        assert decoded.size == original.size
        assert decoded.tobytes() == original.tobytes()

    def test_synthetic_image_is_rgb_512(self) -> None:
        img = generate_synthetic_image()
        assert img.mode == "RGB"
        assert img.size == (512, 512)
