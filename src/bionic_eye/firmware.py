"""Offline signature verification only. There is no device flashing implementation."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .protocol import _reject_constant, _unique_object

MAX_FIRMWARE_BYTES = 64 * 1024 * 1024


def _read_bounded(path, maximum):
    with Path(path).open("rb") as handle:
        data = handle.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"File exceeds the allowed size: {maximum} bytes.")
    return data


def canonical_manifest(manifest):
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class VerificationResult:
    product: str
    version: int
    size: int
    sha256: str

    def to_dict(self):
        return {"product": self.product, "version": self.version, "size": self.size,
                "sha256": self.sha256, "signature_verified": True, "flashed": False,
                "device_compatibility_verified": False, "clinical_validation": False}


def verify_package(image_path, manifest_path, signature_path, public_key_path,
                   expected_product, current_version):
    """Verify detached Ed25519 signature, target, monotonic version, size and digest.

    The caller supplies the trusted public key independently of the package and the
    current version from an authoritative source. This function does not prove device
    compatibility, maintain a device rollback counter, install, download, or execute code.
    """
    if type(current_version) is not int or current_version < 0:
        raise ValueError("Current version must be a non-negative integer.")
    if not isinstance(expected_product, str) or not expected_product:
        raise ValueError("Expected product must be supplied independently of the manifest.")
    try:
        manifest = json.loads(_read_bounded(manifest_path, 4096),
                              parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Manifest is not valid UTF-8 JSON.") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "product", "version", "size", "sha256"}:
        raise ValueError("Manifest requires exactly schema, product, version, size, sha256.")
    if type(manifest["schema"]) is not int or manifest["schema"] != 1:
        raise ValueError("Unsupported firmware manifest schema.")
    if manifest["product"] != expected_product:
        raise ValueError("Firmware product does not match the expected product.")
    if type(manifest["version"]) is not int or manifest["version"] <= current_version:
        raise ValueError("Firmware version must be newer than the supplied current version.")
    if type(manifest["size"]) is not int or not 1 <= manifest["size"] <= MAX_FIRMWARE_BYTES:
        raise ValueError("Firmware size must be between 1 byte and 64 MiB.")
    if not isinstance(manifest["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", manifest["sha256"]):
        raise ValueError("Firmware SHA-256 digest must be 64 lowercase hex characters.")
    public_key = _read_bounded(public_key_path, 32)
    signature = _read_bounded(signature_path, 64)
    if len(public_key) != 32 or len(signature) != 64:
        raise ValueError("Use a raw 32-byte trusted public key and a raw 64-byte signature.")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical_manifest(manifest))
    except InvalidSignature as exc:
        raise ValueError("Firmware manifest signature verification failed.") from exc
    payload = _read_bounded(image_path, MAX_FIRMWARE_BYTES)
    if len(payload) != manifest["size"] or hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
        raise ValueError("Firmware size or SHA-256 digest does not match the signed manifest.")
    return VerificationResult(manifest["product"], manifest["version"], len(payload), manifest["sha256"])
