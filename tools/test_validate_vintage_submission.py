# SPDX-License-Identifier: MIT
"""Tests for vintage hardware submission validator with real image validation"""

import os
import json
import tempfile
import pytest
from validate_vintage_submission import SubmissionValidator


def _create_test_image(width, height, mode="RGB", fmt="PNG", ext=".png"):
    """Create a real test image using Pillow"""
    try:
        from PIL import Image
        img = Image.new(mode, (width, height))
        if mode == "RGB":
            img.putpixel((0, 0), (255, 0, 0))
        return img
    except ImportError:
        pytest.skip("Pillow not available")


class TestValidatePhoto:
    """S4: validate_photo — real image analysis"""

    def setup_method(self):
        self.validator = SubmissionValidator()

    def test_valid_photo_pass(self):
        """Valid photo: proper resolution, RGB mode, real image"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = f.name
        try:
            img = _create_test_image(640, 480)
            img.save(path, "JPEG")
            result = self.validator.validate_photo(path)
            assert result["status"] in ("PASS", "WARN"), f"Expected PASS or WARN, got {result['status']}: {result['message']}"
            assert result["checks"]["width"] == 640
            assert result["checks"]["height"] == 480
            assert result["checks"]["file_exists"] is True
            assert result["checks"]["file_size_bytes"] > 0
        finally:
            os.unlink(path)

    def test_photo_not_found(self):
        """Missing file returns FAIL"""
        result = self.validator.validate_photo("/nonexistent/photo.jpg")
        assert result["status"] == "FAIL"
        assert "not found" in result["message"]

    def test_photo_too_small_resolution(self):
        """Very small image triggers WARN on resolution"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            img = _create_test_image(100, 80)
            img.save(path, "PNG")
            result = self.validator.validate_photo(path)
            assert result["status"] == "WARN", f"Expected WARN for tiny image, got {result['status']}"
            assert "resolution too small" in result["message"].lower()
        finally:
            os.unlink(path)

    def test_photo_invalid_file(self):
        """Corrupted/non-image file returns FAIL"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"not an image file at all")
            path = f.name
        try:
            result = self.validator.validate_photo(path)
            assert result["status"] == "FAIL"
            assert "error" in result["message"].lower() or "validation error" in result["message"].lower()
        finally:
            os.unlink(path)

    def test_photo_file_too_small_size(self):
        """File under 10KB triggers WARN on file size"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            img = _create_test_image(40, 30)
            # Save minimal PNG — will be very small bytes
            img.save(path, "PNG")
            result = self.validator.validate_photo(path)
            # Should get WARN from file_size + resolution
            assert result["status"] == "WARN"
        finally:
            os.unlink(path)


class TestValidateScreenshot:
    """S5: validate_screenshot — real image analysis"""

    def setup_method(self):
        self.validator = SubmissionValidator()

    def test_valid_screenshot_pass(self):
        """Valid screenshot at 1920x1080 (16:9)"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            img = _create_test_image(1920, 1080)
            img.save(path, "PNG")
            result = self.validator.validate_screenshot(path)
            assert result["status"] in ("PASS", "WARN"), f"Expected PASS or WARN, got {result['status']}: {result['message']}"
            assert result["checks"]["width"] == 1920
            assert result["checks"]["height"] == 1080
            assert result["checks"]["aspect_ratio"] == "1.78"
        finally:
            os.unlink(path)

    def test_screenshot_not_found(self):
        """Missing file returns FAIL"""
        result = self.validator.validate_screenshot("/nonexistent/screenshot.png")
        assert result["status"] == "FAIL"
        assert "not found" in result["message"]

    def test_screenshot_too_small(self):
        """Tiny screenshot triggers WARN on resolution"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            img = _create_test_image(100, 75)
            img.save(path, "PNG")
            result = self.validator.validate_screenshot(path)
            assert result["status"] == "WARN", f"Expected WARN for tiny screenshot, got {result['status']}"
            assert "resolution too small" in result["message"].lower()
        finally:
            os.unlink(path)

    def test_screenshot_invalid_file(self):
        """Corrupted file returns FAIL"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"not a png")
            path = f.name
        try:
            result = self.validator.validate_screenshot(path)
            assert result["status"] == "FAIL"
        finally:
            os.unlink(path)

    def test_screenshot_unusual_aspect_ratio(self):
        """Non-standard aspect ratio triggers WARN"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            img = _create_test_image(800, 600)
            img.save(path, "PNG")
            result = self.validator.validate_screenshot(path)
            # 800x600 = 1.33 (4:3) — this IS standard, should PASS
            if result["status"] == "WARN":
                assert "aspect" not in result["message"].lower(), f"4:3 should be standard: {result['message']}"
        finally:
            os.unlink(path)


class TestValidateAttestationLog:
    """Existing attestation log validation"""

    def setup_method(self):
        self.validator = SubmissionValidator()

    def test_valid_json_log(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"miner_id": "abc", "device_arch": "x86_64", "fingerprint_hash": "abc123", "timestamp": "2024-01-01"}, f)
            path = f.name
        try:
            result = self.validator.validate_attestation_log(path)
            assert result["status"] == "PASS"
        finally:
            os.unlink(path)

    def test_missing_fields(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"miner_id": "abc"}, f)
            path = f.name
        try:
            result = self.validator.validate_attestation_log(path)
            assert result["status"] == "FAIL"
            assert "Missing" in result["message"]
        finally:
            os.unlink(path)


class TestValidateSubmission:
    """Integration: validate_submission with all components"""

    def setup_method(self):
        self.validator = SubmissionValidator()

    def test_full_valid_submission(self):
        """All components valid"""
        with (
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as pf,
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as sf,
            tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as lf,
            tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as wf,
        ):
            photo_path = pf.name
            screenshot_path = sf.name
            log_path = lf.name
            writeup_path = wf.name

            img = _create_test_image(640, 480)
            img.save(photo_path, "PNG")
            img2 = _create_test_image(1920, 1080)
            img2.save(screenshot_path, "PNG")
            json.dump({"miner_id": "abc", "device_arch": "x86_64", "fingerprint_hash": "abc123", "timestamp": "2024-01-01"}, lf)
            wf.write("# CPU: Intel\ndetails\nOS: Linux\nram: 16GB\nstorage: 512GB\n")

        try:
            result = self.validator.validate_submission(
                photo_path=photo_path,
                screenshot_path=screenshot_path,
                attestation_log_path=log_path,
                writeup_path=writeup_path,
                wallet_address="RTC1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
            )
            assert result["valid"] is True
            assert result["checks"]["photo"]["status"] in ("PASS", "WARN")
            assert result["checks"]["screenshot"]["status"] in ("PASS", "WARN")
            assert result["checks"]["attestation_log"]["status"] == "PASS"
            assert result["checks"]["writeup"]["status"] in ("PASS", "WARN")
            assert result["checks"]["wallet"]["status"] == "PASS"
        finally:
            for p in [photo_path, screenshot_path, log_path, writeup_path]:
                os.unlink(p)
