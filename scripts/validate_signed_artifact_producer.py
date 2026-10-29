"""Qualify a native test producer's ephemeral signature; never a production trust policy."""

import base64
import hashlib
import json
import sys
from pathlib import Path

from artifact_signing import signing_input
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


def validate(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if set(value) != {"manifest", "content_base64", "test_public_point_hex"}:
        raise ValueError("unexpected native diagnostic fields")
    reference = json.loads((Path(__file__).resolve().parents[1] /
                            "fixtures/artifacts/signing-v2.json").read_text())
    manifest = value["manifest"]
    expected = {k: v for k, v in reference["manifest"].items() if k != "authorization"}
    actual = {k: v for k, v in manifest.items() if k != "authorization"}
    if actual != expected:
        raise ValueError("native manifest disagrees with central exact-byte fixture")
    content = base64.b64decode(value["content_base64"], validate=True)
    if (content != base64.b64decode(reference["content_base64"], validate=True)
            or len(content) != manifest["content_bytes"]
            or hashlib.sha256(content).hexdigest() != manifest["sha256"]):
        raise ValueError("native content disagreement")
    point = bytes.fromhex(value["test_public_point_hex"])
    if len(point) != 65 or hashlib.sha256(point).hexdigest()[:16] != manifest["authorization"]["key_id"]:
        raise ValueError("native key identity disagreement")
    raw = base64.b64decode(manifest["authorization"]["signature"], validate=True)
    if len(raw) != 64:
        raise ValueError("invalid raw signature length")
    der = utils.encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point).verify(
        der, signing_input(manifest), ec.ECDSA(hashes.SHA256()))


if __name__ == "__main__":
    validate(sys.argv[1])
    print("Native manifest, exact bytes, hash, key identity and ES256 signature verified.")
