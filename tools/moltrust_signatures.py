"""Check MolTrust's two signatures against its two published keys.

A trust registry's output is only worth anything if a third party can verify it without
asking the registry. MolTrust publishes a JWS on every trust score and an
Ed25519Signature2020 proof on every credential, plus two keys — a registry key at
/.well-known/registry-key.json and a did:web key at /.well-known/did.json. This checks all of
it and says which claims hold.

    python tools/moltrust_signatures.py            # uses the saved score and credential
    python tools/moltrust_signatures.py <did>      # fetches a live score for any DID
"""
import base64
import copy
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

API = 'https://api.moltrust.ch'
H = {'User-Agent': 'does-it-pay/1.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
MULTICODEC_ED25519_PUB = bytes([0xed, 0x01])


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return json.loads(r.read().decode())


def b64u(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def from_multibase(mb):
    n = 0
    for c in mb[1:]:
        n = n * 58 + B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return raw[2:] if raw[:2] == MULTICODEC_ED25519_PUB else raw


def verifies(key, sig, msg):
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(sig, msg)
        return True
    except (InvalidSignature, ValueError):
        return False


def canonical(obj, integral_floats=True):
    """JCS-shaped: sorted keys, no whitespace. RFC 8785 renders 0.0 as 0, so do both."""
    def norm(x):
        if isinstance(x, float) and x == int(x):
            return int(x)
        if isinstance(x, dict):
            return {k: norm(v) for k, v in x.items()}
        if isinstance(x, list):
            return [norm(v) for v in x]
        return x
    payload = norm(obj) if integral_floats else obj
    return json.dumps(payload, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode()


def credential_constructions(cred, proof):
    """Every way an Ed25519Signature2020 proof over this credential might be built."""
    doc = copy.deepcopy(cred)
    doc.pop('proof', None)
    cfg = copy.deepcopy(proof)
    cfg.pop('proofValue', None)
    cfg_ctx = copy.deepcopy(cfg)
    cfg_ctx['@context'] = cred.get('@context')
    with_cfg = copy.deepcopy(cred)
    with_cfg['proof'] = cfg

    out = {}
    for iname, integral in (('int', True), ('raw', False)):
        d = canonical(doc, integral)
        out[f'document/{iname}'] = d
        out[f'document-with-proof-config/{iname}'] = canonical(with_cfg, integral)
        out[f'credentialSubject/{iname}'] = canonical(cred['credentialSubject'], integral)
        out[f'sha256(document)/{iname}'] = hashlib.sha256(d).digest()
        out[f'sha256(document)-hex/{iname}'] = hashlib.sha256(d).hexdigest().encode()
        for cname, c in (('config', cfg), ('config+context', cfg_ctx)):
            cb = canonical(c, integral)
            out[f'data-integrity {cname}||doc/{iname}'] = (hashlib.sha256(cb).digest()
                                                           + hashlib.sha256(d).digest())
            out[f'data-integrity doc||{cname}/{iname}'] = (hashlib.sha256(d).digest()
                                                           + hashlib.sha256(cb).digest())
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    jwk = get(f'{API}/.well-known/registry-key.json')
    registry_key = b64u(jwk['x'])
    diddoc = get(f'{API}/.well-known/did.json')
    didweb_key = from_multibase(diddoc['verificationMethod'][0]['publicKeyMultibase'])
    print(f"registry key  {jwk['kid']}  {registry_key.hex()}")
    print(f"did:web key   {diddoc['verificationMethod'][0]['id']}  {didweb_key.hex()}")
    print(f"the two published keys are "
          f"{'THE SAME' if registry_key == didweb_key else 'DIFFERENT KEYS'}\n")
    keys = [('registry', registry_key), ('did:web', didweb_key)]

    if len(sys.argv) > 1:
        score = get(f'{API}/skill/trust-score/{urllib.parse.quote(sys.argv[1])}')
    else:
        score = json.load(open(os.path.join(ROOT, 'data', 'moltrust_trust_score.json'),
                               encoding='utf-8'))
    header_b64, payload_b64, sig_b64 = score['registry_jws'].split('.')
    jws_sig = b64u(sig_b64)
    signing_input = f'{header_b64}.{payload_b64}'.encode()
    print(f"trust score for {score['did']}")
    print(f"  jws header  {json.loads(b64u(header_b64))}")
    print(f"  jws payload {json.loads(b64u(payload_b64))}")
    hit = [n for n, k in keys if verifies(k, jws_sig, signing_input)]
    print(f"  registry_jws: {'VERIFIES under ' + hit[0] if hit else 'DOES NOT VERIFY'}")

    detached = b64u(score['registry_signature'])
    hit = [f'{n} over the jws payload bytes' for n, k in keys
           if verifies(k, detached, b64u(payload_b64))]
    print(f"  registry_signature: {'VERIFIES under ' + hit[0] if hit else 'not reproduced'}\n")

    keyfile = os.path.join(ROOT, 'secrets', 'moltrust.json')
    if not os.path.exists(keyfile):
        print('no saved credential; skipping the credential proof')
        return 0
    cred = json.load(open(keyfile, encoding='utf-8'))['registration_response']['credential']
    proof = cred['proof']
    sig = bytes.fromhex(proof['proofValue'])
    print(f"credential proof  {proof['type']} / {proof['canonicalizationAlgorithm']} / "
          f"{proof['verificationMethod']}")
    tried = credential_constructions(cred, proof)
    found = [(n, kn) for n, msg in tried.items() for kn, k in keys if verifies(k, sig, msg)]
    if found:
        for n, kn in found:
            print(f'  VERIFIES: {n} under the {kn} key')
    else:
        print(f'  could not reproduce: {len(tried)} canonicalisations x {len(keys)} keys, '
              f'no match')
        print('  this is "not reproducible from published data", not "invalid" - the exact '
              'signing input is not documented')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
