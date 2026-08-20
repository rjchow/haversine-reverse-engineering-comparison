# Index 01 firmware acquisition and update protocol

Date: 2026-08-20
Artifact release: `03202f5`

## Executive result

The app obtains an update manifest from a public, hard-coded GitHub Raw URL:

```text
https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json
```

The manifest supplies four version bytes and a Base64 `image` string. The app
decodes `image` directly to bytes and passes the complete byte array to the
Haversine satellite library.

Despite the native class name `HaversineSuotaOperation`, this is **not** the
standard Dialog Semiconductor/Renesas SUOTA GATT service. It uses the normal
Haversine service and the normal Telesto virtual-memory request protocol:

```text
read platform versions
  -> enter streaming state
  -> erase stationary-data virtual object
  -> erase primary-image virtual object
  -> program the raw image bytes
  -> send PANIC/reset system input
  -> reconnect
  -> read platform versions and compare the reported firmware version
```

The client performs no firmware-magic, vector-table, internal-header,
checksum, cryptographic-hash, signature, encryption, or compression
validation. It does not extract the version or hardware target from the image.
The ring firmware/bootloader may perform validation that is invisible to these
client artifacts, but its rules cannot be recovered from this library alone.

## 1. Update acquisition

### 1.1 Exact network request

The Kotlin/Native IR in
`analysis/toolchain_iosarm64_dump_ir.txt`, around lines 6108--6474, recovers
`KMPHaversineSatelliteManager.updateDelegate.requestUpdate`.

It:

1. makes an unauthenticated HTTPS `GET` to the URL above;
2. requires an HTTP success status;
3. reads the response as UTF-8 JSON;
4. Base64-decodes JSON member `image`;
5. reads:
   - `firmwareVersionMajor`;
   - `firmwareVersionMinor`;
   - `hardwareVersionMajor`;
   - `hardwareVersionMinor`;
6. constructs a `HaversineFirmwareUpdate` from those values and the decoded
   bytes.

The relevant hard-coded URL occurs in the recovered IR at approximately line
6130. The exact Android AAR independently exposes the same data model in:

```text
analysis/decompiled_android_debug/
  com/wtlp/haversinesatellitelibrary/HaversineEnvironment.java
```

Its `FirmwareUpdate(JSONObject)` reads the same four numeric members and
decodes `image` with Android `Base64.DEFAULT`.

The KMP manager installs Ktor's HTTP cache and keeps a parsed update in memory.
The Android implementation refreshes it when absent or older than three hours;
it also starts an initial asynchronous download when the manager is created.
No API token, cookie, device identity, or request signature is attached by this
code.

### 1.2 Transport authenticity versus firmware authenticity

The manifest is protected in transit by ordinary HTTPS to GitHub. The app does
not:

- pin a GitHub certificate or public key;
- verify a detached manifest signature;
- consume a manifest SHA-256 field;
- compare a compiled-in firmware digest;
- verify a signature embedded in the decoded image.

This does **not** prove the ring bootloader accepts an unsigned image. It only
proves that authenticity enforcement, if present, is below this client layer.

## 2. When the app decides to update

On an advertisement, the native Android library asks its update delegate for
an update. `HaversineSatellite.shouldProgramFirmware` permits it only when:

- RSSI is at least `-85 dBm`;
- manifest hardware major/minor exactly match the ring's cached hardware
  major/minor;
- manifest firmware `(major << 8) | minor` is strictly greater than the
  ring's cached version.

It queues the update at the lowest operation priority. Before performing
destructive work, native `HaversineSuotaOperation` independently reads the
ring's platform versions. With `force == false`, it exits successfully without
writing when the requested version is not greater than the live version. This
is a stale-cache/race safeguard.

The update image's bytes are not consulted in either comparison. Version and
hardware compatibility come from manifest metadata.

## 3. Native operation interface and defaults

The exact iOS device and iOS simulator `HaversineSuotaOperation.o` objects have
the same text layout and symbols:

| Symbol | Object-relative text offset |
| --- | ---: |
| `HaversineSuotaOperation_init` | `0x000` |
| `_SuotaOperation_start` | `0x114` |
| `_SuotaOperation_cancel` | `0x16c` |
| `_SuotaOperation_free` | `0x1f8` |
| `HaversineSuotaOperation_shouldRetry` | `0x230` |
| `complete` | `0x240` |
| `_SuotaOperation_startNextChild` | `0x2bc` |
| `_SuotaOperation_handleReceivedDataFromChild` | `0x448` |
| `_SuotaOperation_handleCompletionFromChild` | `0x4e4` |

The exact device object is:

```text
extracted/iosarm64-cinterop-haversineSatelliteLibrary/
  static_objects/HaversineSuotaOperation.o
```

DWARF gives this initializer:

```c
HaversineOperationInterface *HaversineSuotaOperation_init(
    uint8_t imageVersionMajor,
    uint8_t imageVersionMinor,
    const uint8_t *imageDataIN,
    uint32_t imageDataSize,
    bool force,
    bool skipVerification
);
```

It allocates a private copy of exactly `imageDataSize` bytes. There is no parse
or transformation between the input `memcpy` and the later Telesto program
request.

### Defaults in the shipping wrappers

The Android JNI function
`Java_com_wtlp_haversinesatellitelibrary_operations_SuotaOperation_init`
is at ELF VA `0xd260` in the x86-64 library. It calls the native initializer
with:

```text
force = false
skipVerification = false
```

The iOS Swift closure that creates the operation is at object offset `0x16e04`
in `HaversineSatellite.o`; its call to `HaversineSuotaOperation_init` is at
`0x16ed4`. It sets:

```text
force = false
skipVerification = caller's Boolean
```

The automatic app update uses normal verification. The native `force`
capability is present but no examined production wrapper exposes it as true.

`force == true` would bypass only the live “new version must be greater”
comparison. It does not bypass any ring-side validation.

## 4. Telesto wire format used by the updater

Every memory operation starts with the normal packed, 13-byte Telesto request
on the control characteristic:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 1 | operation |
| 1 | 4 | virtual address, little-endian |
| 5 | 4 | offset, little-endian |
| 9 | 4 | length, little-endian |

Relevant operations are:

| Value | Meaning |
| ---: | --- |
| `1` | erase memory |
| `2` | program memory |
| `3` | read memory |

The ring returns the normal packed, 12-byte Telesto response:

```text
u32le error
u32le info
u32le length
```

A nonzero response error is surfaced as a Haversine operation error. For a
read, `length` tells the client how many data-characteristic bytes to collect.
For a program, the request is followed by the raw `imageData` bytes on the data
characteristic.

There is no update-specific packet header between the Telesto request and the
image:

- no per-block offset;
- no block number;
- no block checksum;
- no firmware total-size prefix beyond `request.length`;
- no app-level ACK for each BLE fragment;
- no app-level sliding window.

BLE/GATT performs its own link-layer integrity and retransmission. That should
not be mistaken for an update protocol checksum.

## 5. Phase-by-phase state machine

The phase enum recovered from DWARF is:

| Phase | Name |
| ---: | --- |
| 0 | `READ_INITIAL_PLATFORM_VERSIONS` |
| 1 | `CONFIGURE_STATE` |
| 2 | `ERASE_STATIONARY_DATA` |
| 3 | `ERASE_PRIMARY_IMAGE` |
| 4 | `PROGRAM_PRIMARY_IMAGE` |
| 5 | `RESET_SATELLITE` |
| 6 | `VERIFY_RESET` |
| 7 | `READ_FINAL_PLATFORM_VERSIONS` |
| 8 | `FINISHED` |

The phase jump tables begin at object offsets `0x810`, `0x818`, `0x821`, and
`0x829`. The fixed Telesto parameter structures begin at `0x838` and `0x850`.

### Phase 0: read live platform versions

```text
Telesto operation: READ (3)
address:           0x40030006  TELESTO_PLATFORM_VERSIONS
offset:            0
length:            4
dataToSend:        null
```

The returned bytes are:

```text
u8 hardwareVersionMajor
u8 hardwareVersionMinor
u8 firmwareVersionMajor
u8 firmwareVersionMinor
```

The handler accepts exactly four accumulated bytes for the initial structure.
It compares the live firmware version to the requested manifest version.

If the update is not newer and `force` is false, the operation completes
successfully without erasing or programming anything.

If the requested major version is zero, the implementation jumps directly to
phase 3. This special branch is proven by the code at `0x61c`--`0x628`; its
product rationale is not present in the client artifact.

### Phase 1: configure state

The operation sends the packed seven-byte `HaversineSystemInput` with type:

```text
INPUT_ENTER_STREAMING_STATE = 7
```

to the system-input characteristic. The remaining parameter bytes are zero.

### Phase 2: erase stationary data

```text
Telesto operation: ERASE (1)
address:           0x40000002  TELESTO_STATIONARY_DATA
offset:            0
length:            0x1000
dataToSend:        null
```

This fixed request is stored at object offset `0x838`. It erases the
stationary-data virtual object, not the collection-address range.

### Phase 3: erase primary image

```text
Telesto operation: ERASE (1)
address:           0x40060000  TELESTO_PRIMARY_IMAGE
offset:            0
length:            imageDataSize
dataToSend:        null
```

The client asks to erase exactly the decoded image length. Sector rounding, a
maximum slot size, or other constraints are ring-side behavior and are not
visible here.

### Phase 4: program primary image

```text
Telesto operation: PROGRAM (2)
address:           0x40060000  TELESTO_PRIMARY_IMAGE
offset:            0
length:            imageDataSize
dataToSend:        imageData
```

The bytes are exactly the Base64-decoded `image`, in order, with no client-side
prefix, padding, compression, encryption, checksum, or signature attachment.

### Phase 5: reset the ring

The updater sends `HaversineSystemInput` type:

```text
INPUT_PANIC = 12
```

The normal Android representation is seven packed bytes with zeroed
parameters. It is written to the system-input characteristic. The expected
result is that the ring resets and the BLE connection fails/disconnects.

### Phase 6: verify that reset occurred

If the reset write appears to complete without disconnecting, the updater
starts another read of `TELESTO_PLATFORM_VERSIONS`.

This phase is intentionally expected to fail due to the reboot. If that read
unexpectedly succeeds, `_SuotaOperation_handleCompletionFromChild` creates a
Haversine operation error rather than treating it as a successful reset.

### Phase 7: reconnect and read final platform versions

After the expected disconnect, the same operation object retains phase 7. On
the next connection it sends:

```text
Telesto operation: READ (3)
address:           0x40030006  TELESTO_PLATFORM_VERSIONS
offset:            0
length:            4
```

The handler stores the four returned bytes as `finalPlatformVersions`. It
compares only final firmware major/minor with requested image major/minor.
Mismatch becomes a Haversine operation error. There is:

- no byte-for-byte flash readback;
- no check of an image digest;
- no comparison of final hardware version;
- no inspection of a bootloader status/signature result beyond Telesto errors
  and the reported version.

### Phase 8: complete

On equality, the operation returns the final platform-version structure to the
Swift/Java wrapper, which reports success and updates its cached version.

## 6. Reconnect, retry, and `skipVerification`

The disconnect caused by `INPUT_PANIC` is explicitly treated as expected.
Native error handling advances the retained operation to phase 7 and returns
the transport error outward without marking the operation complete.

The high-level Android `HaversineSatellite.programFirmware` runs the same
`SuotaOperation` again on error, twice, for at most three total
`performOperation` calls. Its log message says reconnect during firmware
update is expected. A resumed operation starts from its retained phase, so the
post-reset attempt reads final platform versions rather than erasing and
programming the image again.

`HaversineSuotaOperation_shouldRetry` at `0x230` returns true precisely while
the operation has not been marked complete. Ordinary terminal errors set
`isCompleted`; the expected reset path does not.

With `skipVerification == true`, after programming/reset the native operation:

1. does not require the reconnect/read-final sequence;
2. copies the initial hardware bytes;
3. substitutes the requested firmware major/minor as the returned final
   version;
4. reports success.

Thus “skip verification” really does skip observation of the rebooted firmware;
it is not a cryptographic-signature bypass. The shipping automatic updater and
the Android JNI constructor use `false`.

## 7. BLE characteristics and chunking

The updater uses the standard Haversine service, accepting either service UUID:

```text
0000FCC9-0000-1000-8000-00805F9B34FB
607B5C9B-3700-4E94-F44A-2DF900BCB0C3
```

Characteristics:

| Purpose | UUID |
| --- | --- |
| Telesto data | `DAAD3D52-237C-90A7-B54B-8854A134D801` |
| Telesto control | `C0EF558A-2058-FABF-A140-8D5ACDE50B39` |
| system input | `1D1F4039-23F5-33B2-C24E-704351F20585` |

The app subscribes to notifications on Telesto control and data before
declaring the connection ready.

Android's exact AAR:

- sets Telesto control and data to `WRITE_TYPE_NO_RESPONSE`;
- sets system input to `WRITE_TYPE_DEFAULT`/with response;
- fragments every outgoing buffer into fixed chunks of at most 20 bytes;
- waits for its Android GATT write callback before submitting the next chunk.

Consequently, the 13-byte Telesto control request normally occupies one write,
while the firmware image is sent as a long sequence of at-most-20-byte writes
to the Telesto data characteristic.

iOS uses `maximumWriteValueLength(for:)`, so its fragment size follows the
negotiated CoreBluetooth write limit. It normally uses `.withoutResponse`, and
after three such packets may insert a `.withResponse` packet when supported as
a pacing mechanism. These fragment boundaries do not change Telesto's
`imageDataSize` or appear in the firmware byte stream.

## 8. What the client proves about image format

The app-facing input format is:

```text
JSON envelope
  -> Base64 decode `image`
  -> opaque binary byte array
  -> raw Telesto programming bytes at virtual address 0x40060000
```

Positive facts:

- the client expects a single contiguous byte array;
- its byte length must fit the native `uint32_t imageDataSize`;
- it does not expect a ZIP, TAR, Intel HEX, UF2, or multipart container at this
  layer;
- it does not alter byte order or strip any prefix/footer;
- if the published byte array itself contains a vendor header, checksum,
  signature, or vector table, those bytes are forwarded unchanged.

Unknown without the actual published image or ring firmware:

- CPU/SoC and executable format;
- load address and vector-table layout;
- bootloader header fields;
- checksum or signature algorithm enforced by the bootloader;
- public key material;
- anti-rollback policy;
- slot capacity/alignment;
- whether `0x40060000` maps directly to raw flash or is a virtual programming
  command.

## 9. Safety implications for an independent updater

An independent implementation can reproduce the client-side exchange from
this evidence, but destructive testing should not proceed from static analysis
alone. In particular:

- erasing `0x40060000` before confirming the exact target hardware can brick
  the ring;
- the app's manifest/hardware check is metadata-based, not derived from the
  image;
- the maximum safe image length and erase alignment are unknown;
- power-loss recovery and fail-safe boot behavior are firmware-side;
- forcing a downgrade is supported by the native state machine but is not
  exercised by the shipping app;
- client evidence does not establish whether an arbitrary modified image will
  pass the bootloader.

The safest next evidence is a copy of the public manifest/image plus offline
format analysis. A BLE capture of one official update would then confirm the
static state machine without attempting a modified image.

## 10. Evidence index

Primary exact-release evidence:

```text
analysis/toolchain_iosarm64_dump_ir.txt
analysis/decompiled_android_debug/
  com/wtlp/haversinesatellitelibrary/HaversineEnvironment.java
analysis/decompiled_android_debug/
  com/wtlp/haversinesatellitelibrary/HaversineSatellite.java
analysis/decompiled_android_debug/
  com/wtlp/haversinesatellitelibrary/operations/SuotaOperation.java
analysis/decompiled_android_debug/
  com/wtlp/haversinesatellitelibrary/transport/LinkTransport.java
analysis/decompiled_android_debug/
  com/wtlp/haversinesatellitelibrary/transport/HaversineUUID.java
extracted/iosarm64-cinterop-haversineSatelliteLibrary/
  static_objects/HaversineSuotaOperation.o
extracted/iossimulatorarm64-native-objects/
  satellite-arm64/HaversineSuotaOperation.o
extracted/android-debug/jni/x86_64/libhaversinesatellitelibrary.so
```

Cross-checked generic Telesto/BLE reconstruction:

```text
analysis/sim_inventory.md
analysis/independent_client_spec.md
```

Confidence classification:

- **Directly proven:** URL, JSON fields, Base64 decode, state-machine phases,
  requests, virtual addresses, offsets/lengths, raw image forwarding,
  reconnect/version verification, wrapper defaults, BLE characteristics, and
  platform-specific chunking.
- **Strong inference:** the update URL can supply a complete restorable copy of
  the client-visible firmware programming payload.
- **Unknown:** ring-side file authentication/validation and the relationship
  between the virtual primary-image object and physical flash.
