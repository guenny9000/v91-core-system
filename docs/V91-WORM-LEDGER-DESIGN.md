# V91 Ledger: tamper evidence, immutability, and WORM design

**Status:** design proposal only. No WORM storage or immutable retention is implemented by this document.

## 1. Current baseline

`controller/ledger.py` implements a local JSONL SHA-256 hash chain. It serializes payload dictionaries with sorted keys and compact separators, links each record to the previous digest, verifies the chain on open, and flushes/fsyncs each append.

This is useful tamper evidence, but it is not WORM. The current process-local thread lock does not serialize multiple processes. A user with sufficient filesystem privileges can replace the entire file and recompute every hash. The ledger has no independent trusted timestamp, signature on checkpoints, retention lock, external witness, or demonstrated crash-recovery protocol for a partial final record.

Do not rename or describe the current implementation as WORM.

## 2. Security properties must be separated

| Property | Meaning | Required mechanism |
|---|---|---|
| Deterministic encoding | Same logical event produces same bytes | Versioned canonical JSON profile |
| Tamper evidence | Changes can be detected against a trusted head | Hash chain + independently retained checkpoint |
| Writer authenticity | Identify which key signed a record/checkpoint | Digital signature + key lifecycle |
| Append serialization | Concurrent writers cannot reuse sequence/head | Transactional lock or conditional append |
| Crash consistency | Torn writes are detected and recovery is explicit | Framing, fsync, recovery protocol |
| Retention immutability | Stored versions cannot be altered/deleted during retention | WORM-capable storage with retention lock |
| Independent time | Time claim is not solely writer-controlled | Trusted timestamping or independent witness |

No one mechanism supplies all of these properties.

## 3. Proposed record format

Use a versioned, typed envelope:

- `schema_version`
- `ledger_id`
- `sequence`
- `event_id` (unique, replay-detection identifier)
- `recorded_at_utc` (writer timestamp; not independently trusted)
- `writer_key_id`
- `event_type`
- `payload`
- `previous_record_hash`
- `record_hash`
- optional `writer_signature`

Hash input must be unambiguous and domain-separated, for example:

`SHA256("V91-LEDGER-RECORD-v1\0" || canonical_record_bytes_without_hash_or_signature)`

The canonicalization profile must be explicit and versioned. Prefer RFC 8785 JSON Canonicalization Scheme (JCS) with strict input constraints; do not assume Python `json.dumps(sort_keys=True)` is equivalent to JCS. Reject duplicate object keys, non-finite numbers, unsupported numeric forms, invalid Unicode, and ambiguous encodings before hashing.

A record hash proves integrity relative to the supplied previous hash. It does not prove the event is true.

## 4. Append protocol

1. Validate schema and size limits before acquiring the writer lock.
2. Acquire a cross-process serialization primitive. For a single local file, use a platform-specific OS lock and document its filesystem limits; for multiple hosts, use a transactional database or object-store conditional write.
3. Re-read and verify the current head while holding the lock.
4. Enforce the next sequence and reject duplicate `event_id` values.
5. Serialize canonical bytes and compute the domain-separated record hash.
6. Write one framed record; flush and fsync the file. Where supported, fsync the containing directory after file creation/rotation.
7. Read back and verify the appended record before reporting success.
8. Release the lock in a guaranteed cleanup path.
9. On malformed/torn final record, fail closed and require explicit recovery; never silently truncate or rewrite prior history.

A process-local Python threading lock is insufficient for multiple processes.

## 5. Independent checkpoints and retention

At bounded intervals, create a checkpoint containing ledger ID, sequence, head hash, schema version, key ID, and checkpoint time. Sign it with a managed asymmetric signing key (for example Ed25519). Publish the signed checkpoint to a separately administered immutable destination.

WORM retention requires a storage service or appliance with independently configured retention lock / object lock and separate administrative control. The application writer should have append/create permission only; it must not have permission to shorten retention or delete prior versions. Verify provider semantics, retention mode, legal hold, versioning, and privileged-admin bypass conditions before claiming compliance.

An external witness should retain checkpoints independently. If the local ledger is rewritten, comparison with the previously anchored checkpoint must detect rollback or divergence.

## 6. Key lifecycle

- Keys are generated and held outside the repository and source code.
- Each signature/checkpoint records a non-secret key identifier.
- Rotation has an explicit activation time and overlap policy.
- Revocation is recorded and independently anchored.
- Historical verification uses the public key valid for the signing time; do not silently replace historical trust roots.
- Secret material must never be placed in fixtures that resemble production credentials, logs, PR text, or committed configuration.

HMAC is useful for shared-secret authentication between known parties, but it is not a non-repudiable writer signature: every party holding the shared secret can create valid MACs. Prefer asymmetric signatures for independently verifiable ledger checkpoints.

## 7. Verification states

Use explicit results:

- `EMPTY_LEDGER`: no records exist; not a pass.
- `CHAIN_VALID_UNANCHORED`: local chain verifies, but no trusted external head was checked.
- `CHECKPOINT_MATCH`: local head matches an independently retrieved signed checkpoint.
- `SIGNATURE_VALID`: signature verifies under the selected public key; identity trust remains a separate question.
- `RETENTION_POLICY_CONFIRMED`: storage provider reports active retention controls and the configuration was independently checked.
- `UNKNOWN`: evidence unavailable.
- `FAILED_CLOSED`: malformed data, broken chain, invalid signature, sequence conflict, missing key, or failed anchor check.

Never return a generic `SECURE` or `WORM_VERIFIED` value based only on a local hash-chain check.

## 8. Acceptance tests before implementation is called verified

- Deterministic bytes for fixed valid payloads and canonicalization test vectors.
- Duplicate-key, NaN/Infinity, invalid Unicode, and unsupported numeric input rejection.
- Tamper with payload, sequence, previous hash, record hash, and record order.
- Delete or roll back the tail and compare against an external checkpoint.
- Two concurrent writer processes attempting to append at the same time.
- Process termination during write, followed by explicit torn-record detection.
- Disk-full and permission-denied behavior; no false success response.
- Key rotation, revoked key, unknown key ID, and signature mismatch.
- Retention lock cannot be shortened or bypassed by the application writer role.
- Restore from backup and verify against independently retained checkpoints.

## 9. Implementation sequence

1. Add strict schema and canonicalization test vectors without changing the existing ledger format.
2. Add cross-process append serialization and crash-recovery behavior behind a new versioned ledger implementation.
3. Add signed checkpoint generation and offline verification.
4. Add an independently administered WORM backend adapter only after the provider and retention model are selected.
5. Run adversarial, concurrency, crash, and restore tests in disposable environments.
6. Migrate no existing ledger automatically. Preserve old files and provide a separately reviewed, verifiable migration tool.

**Exit criterion:** call the implementation tamper-evident only when local chain verification is tested; call it anchored only when independent signed checkpoints are checked; call it WORM only when the storage retention lock and administrative separation are independently evidenced.
