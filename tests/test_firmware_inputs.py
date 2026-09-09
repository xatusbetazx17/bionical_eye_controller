import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from bionic_eye.firmware import canonical_manifest, verify_package
from bionic_eye.inputs import DwellSelector, HandPointer, VoiceListener, parse_voice


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.image, self.manifest, self.signature, self.key = [root/name for name in ("image.bin", "manifest.json", "signature.bin", "trusted.pub")]
        self.image.write_bytes(b"non-executable bench fixture")
        self.metadata = {"schema": 1, "product": "reference-bench", "version": 2,
                         "size": self.image.stat().st_size,
                         "sha256": hashlib.sha256(self.image.read_bytes()).hexdigest()}
        self.private = Ed25519PrivateKey.generate()
        self.key.write_bytes(self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        self.sign()

    def sign(self):
        self.manifest.write_bytes(canonical_manifest(self.metadata))
        self.signature.write_bytes(self.private.sign(canonical_manifest(self.metadata)))

    def verify(self, product="reference-bench", version=1):
        return verify_package(self.image, self.manifest, self.signature, self.key, product, version)

    def test_valid_signed_package_verified_but_never_flashed(self):
        result = self.verify().to_dict()
        self.assertTrue(result["signature_verified"])
        self.assertFalse(result["flashed"])
        self.assertFalse(result["device_compatibility_verified"])

    def test_payload_tampering_rejected(self):
        self.image.write_bytes(b"modified executable")
        with self.assertRaisesRegex(ValueError, "digest"):
            self.verify()

    def test_manifest_tampering_and_wrong_key_rejected(self):
        self.metadata["version"] = 3
        self.manifest.write_bytes(canonical_manifest(self.metadata))
        with self.assertRaisesRegex(ValueError, "signature"):
            self.verify()
        self.sign()
        self.key.write_bytes(Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        with self.assertRaisesRegex(ValueError, "signature"):
            self.verify()

    def test_product_and_rollback_rejected(self):
        with self.assertRaisesRegex(ValueError, "product"):
            self.verify(product="another-device")
        for version in (2, 3, -1, True):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.verify(version=version)

    def test_malformed_signature_and_manifest_rejected(self):
        self.signature.write_bytes(b"too-short")
        with self.assertRaises(ValueError):
            self.verify()
        for raw in (b"[]", b"{}", b"x"*4097, b'{"schema":1,"schema":1}', b'{"version":NaN}'):
            with self.subTest(raw=raw[:60]), self.assertRaises(ValueError):
                self.manifest.write_bytes(raw)
                self.verify()

    def test_canonical_whitespace_does_not_change_signature(self):
        self.manifest.write_text(json.dumps(self.metadata, indent=4))
        self.assertTrue(self.verify().to_dict()["signature_verified"])


class InputTests(unittest.TestCase):
    def test_only_exact_wake_word_commands_accepted(self):
        self.assertEqual(parse_voice(" EYE   stop "), ("stop", None))
        self.assertEqual(parse_voice("eye night off"), ("low_light", False))
        for text in ("night on", "please eye stop", "don't eye stop", "eye firmware update", "eye stimulate", "eye stop and reset"):
            with self.subTest(text=text):
                self.assertIsNone(parse_voice(text))

    def test_dwell_fires_once_until_leaving(self):
        selector = DwellSelector(1.2)
        self.assertIsNone(selector.update("button", 10))
        self.assertIsNone(selector.update("button", 11))
        self.assertEqual(selector.update("button", 11.3), "button")
        self.assertIsNone(selector.update("button", 20))
        selector.update(None, 21)
        selector.update("button", 22)
        self.assertEqual(selector.update("button", 24), "button")

    def test_tracking_loss_and_clock_rollback_reset_dwell(self):
        selector = DwellSelector(1)
        selector.update("first", 3)
        selector.update(None, 3.8)
        self.assertEqual(selector.progress(4), 0)
        self.assertIsNone(selector.update("first", 5))
        self.assertIsNone(selector.update("first", 2))
        self.assertIsNone(selector.update("second", 4))
        self.assertEqual(selector.update("second", 5), "second")

    def test_invalid_dwell_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                DwellSelector(value)

    def test_missing_models_fail_before_optional_hardware_imports(self):
        with self.assertRaises(ValueError):
            HandPointer("/nonexistent/model.task")
        with self.assertRaises(ValueError):
            VoiceListener("/nonexistent/vosk", lambda x: None, lambda x: None)
