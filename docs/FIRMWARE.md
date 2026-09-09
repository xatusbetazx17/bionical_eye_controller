# Offline firmware-package verification

`firmware-verify` checks local files. It **never downloads, executes, stages or flashes** a binary. A valid signature does not establish device compatibility or clinical safety. The old `update_firmware()` method now raises an unsupported-feature error.

The manifest requires exactly `schema`, `product`, `version`, `size`, and `sha256`:

```json
{"schema":1,"product":"reference-bench","version":2,"size":1234,"sha256":"REPLACE_WITH_ACTUAL_64_CHARACTER_LOWERCASE_SHA256"}
```

The example digest is a placeholder, not a valid package. Version is an integer release sequence, not a dotted version. Size must match the binary and be between 1 byte and 64 MiB.

Canonical signing bytes are UTF-8 `json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)`. Sign with Ed25519; provide the detached **raw 64-byte signature** and an independently trusted **raw 32-byte public key**. A package must not establish trust in its own signing key. Development keys are not authorized production keys.

```bash
python -m bionic_eye firmware-verify \
  --image image.bin --manifest manifest.json --signature manifest.sig \
  --public-key independently-trusted-key.pub \
  --product reference-bench --current-version 1
```

The checker verifies schema, product, a version newer than the supplied current version, signature, size and digest. The success result explicitly includes `signature_verified: true` and `flashed: false`. Failures exit nonzero.

The caller supplies the trusted key, expected product and current version independently. The version comparison is not a persistent hardware rollback counter. A real updater additionally requires authorized target identity/key provisioning, compatibility evidence, interruption-safe installation, recovery, and validated bootloader behavior; none is supplied.

Tests generate temporary random keys for valid, tampered, wrong-key, wrong-product and rollback cases. No production keys or firmware are committed. Reference: [cryptography Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
