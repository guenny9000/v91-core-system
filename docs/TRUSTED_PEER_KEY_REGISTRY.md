# V91 trusted peer-key registry

This is a small, fail-closed lookup helper for the Zero Trust peer handshake.

- A message signature checks that the message matches a private key.
- The registry lookup checks whether that public key is provisioned for the claimed peer and is currently active.
- Unknown peers, unknown key IDs, revoked keys, malformed encodings, unsupported algorithms, and wrong key lengths are rejected.
- The registry must be provisioned through an independently trusted administrative process. Do not accept a registry supplied by the peer or by an unauthenticated network response.
- This helper does not create identity trust, distribute keys, protect the registry file from host compromise, or prove production deployment. Those remain deployment responsibilities.
- The helper returns key bytes only. The caller must still verify the Ed25519 signature over the canonical message and then apply consent/capability policy.

Example structure:

```json
{
  "peers": {
    "peer-a": {
      "keys": {
        "key-2026-01": {
          "algorithm": "Ed25519",
          "public_key_b64": "<base64-encoded 32-byte public key>",
          "status": "active"
        }
      }
    }
  }
}
```

Set a key's status to `revoked` to make lookup fail closed. This is a code-level building block, not a claim that any real peer has already been authenticated.
