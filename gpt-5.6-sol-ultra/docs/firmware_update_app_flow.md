# Index 01 firmware-update acquisition and app flow

Status: complete static trace for the app revision and Haversine artifact used
by the reverse-engineering brief.

## Scope and provenance

This note traces the Index/ring update path in:

- Pebble mobile app commit
  `6d6e2ebb010006e24959f300755516b84843b936`;
- Maven dependency
  `io.github.coredevices.haversine:haversine:03202f5`;
- Android AAR SHA-256
  `6d41a5d0ec410646d9a903997a1a8a73e6ef0fc281cae07216a6a230c0e76989`;
- the exact iOS ARM64 Kotlin/Native IR and Haversine native objects already
  extracted in this workspace.

The app pins Haversine `03202f5` at
`analysis/mobileapp_repo/gradle/libs.versions.toml:56` and maps the Maven
coordinate at the same file's line 154. Both Android and iOS inject a
`KMPHaversineSatelliteManager` into the ring module:

- `analysis/mobileapp_repo/experimental/src/androidMain/kotlin/coredevices/ringModule.android.kt:39-48`;
- `analysis/mobileapp_repo/experimental/src/iosMain/kotlin/coredevices/ringModule.ios.kt:50-58`.

Both pass `RingSync.SATELLITE_HW_VER`, which is `(11, 0)` at
`analysis/mobileapp_repo/experimental/src/commonMain/kotlin/coredevices/ring/service/RingSync.kt:116-123`.

## Result in one paragraph

The app does not discover a firmware filename and then download a separate
`.bin`. Haversine performs an unauthenticated HTTPS `GET` of one hard-coded,
public GitHub Raw JSON document:

```text
https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json
```

That JSON document contains version/hardware metadata and the **entire
firmware image in its `image` field as Base64**. Haversine decodes it in
memory, automatically compares it to an advertising ring, and gives the raw
bytes to its native `SuotaOperation`. Despite that class name, this build
programs the image through the existing Haversine/Telesto virtual-memory
transport rather than a separate app-visible download or file-import path.

## End-to-end sequence

```text
KMPHaversineSatelliteManager construction
  |
  +-- asynchronous initial firmwareUpdateFor(null) / getFirmwareUpdate(null)
       |
       +-- Ktor HTTPS GET GitHub Raw haversine_update.json
       +-- parse JSON
       +-- decode JSON.image from Base64
       +-- retain candidate in process memory

subsequent eligible ring advertisement
  |
  +-- HaversineSatellite.handleAdvertisement()
       |
       +-- update delegate returns cached FirmwareUpdate
       +-- RSSI >= -85 dBm?
       +-- manifest hardware == ring hardware?
       +-- manifest firmware > ring firmware?
       |
       +-- HaversineSatellite.programFirmware()
            |
            +-- SuotaOperation(major, minor, raw image bytes)
            +-- Telesto read initial platform versions
            +-- enter streaming/configured state
            +-- erase stationary data
            +-- erase primary image at virtual address 0x40060000
            +-- program raw image bytes at 0x40060000
            +-- reset ring
            +-- reconnect/read final platform versions
            +-- report Started / Success / Failed to RingSync and UI
```

## 1. Update endpoint and HTTP behavior

The endpoint is an exact constant in both platform artifacts:

- Android:
  `analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManagerKt.java:13-18`;
- iOS exact IR:
  `analysis/toolchain_iosarm64_dump_ir.txt:2499-2507`.

Android bytecode and the iOS IR both show a plain Ktor `GET`. The iOS request
construction and URL are at
`analysis/toolchain_iosarm64_dump_ir.txt:6108-6133`. The Android equivalent
is in the exact class bytecode for
`KMPHaversineSatelliteManager$updateDelegate$1.requestUpdate`; the CFR file
marks that coroutine as undecompilable at
`analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManager.java:350-390`,
but its bytecode has the same URL, method, response-status test, body read,
and `JSONObject` construction.

There is no request-header, bearer-token, cookie, signed-URL, Firebase, or
user-authentication setup in this request. Access control is therefore:

- HTTPS transport to `raw.githubusercontent.com`;
- no application-supplied authentication;
- whatever availability/rate policy GitHub Raw applies to a public URL.

A non-2xx response is logged and yields no update. An exception is logged,
the coroutine waits two seconds, and then yields no update. The corresponding
iOS error path is visible at
`analysis/toolchain_iosarm64_dump_ir.txt:6440-6475`.

## 2. Manifest schema and firmware representation

The Android value object documents the complete schema directly:

`analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/HaversineEnvironment.java:63-85`

Required JSON keys are:

```json
{
  "firmwareVersionMajor": 0,
  "firmwareVersionMinor": 0,
  "hardwareVersionMajor": 0,
  "hardwareVersionMinor": 0,
  "image": "<Base64 firmware bytes>"
}
```

Android calls `Base64.decode(image, 0)` at
`HaversineEnvironment.java:78-85`. iOS reads the same five keys, uses
`Base64.Default.decode`, copies the resulting `ByteArray` into `NSData`, and
constructs `HaversineFirmwareUpdate`; see:

- `analysis/toolchain_iosarm64_dump_ir.txt:6140-6199` for `image`;
- `analysis/toolchain_iosarm64_dump_ir.txt:6200-6415` for the four numeric
  fields;
- `analysis/toolchain_iosarm64_dump_ir.txt:6416-6440` for `NSData` and the
  update-object constructor.

The parser does **not** consume:

- a binary URL;
- a filename;
- an image length;
- a CRC or cryptographic digest;
- a signature or certificate;
- a release channel or minimum-app version.

Consequently the retrievable firmware is the Base64-decoded `image` value
itself. Naming it, for example, `index01-fw-MAJOR.MINOR-hw-MAJOR.MINOR.bin`
would be a local investigator convention, not a filename supplied by the
manifest.

## 3. Prefetch, caching, and local paths

Manager construction attaches the update delegate and immediately launches
an asynchronous prefetch by calling `getFirmwareUpdate(null)`:

`analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManager.java:553-609`.

The first call has no candidate to return. It starts a download job; a later
advertisement sees the populated cache. Concurrent calls return `null` while
that job is active. A successful candidate is considered fresh for three
hours:

`analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManager.java:395-515`.

The iOS implementation is behaviorally the same:

- explicit `cachedUpdate`, `cachedUpdateTime`, and `updateDownloadJob` fields
  at `analysis/toolchain_iosarm64_dump_ir.txt:6476-6533`;
- three-hour age test and single active job at
  `analysis/toolchain_iosarm64_dump_ir.txt:6534-6624`;
- initial prefetch at
  `analysis/toolchain_iosarm64_dump_ir.txt:7318-7360`.

The Ktor client also installs `HttpCache` with default configuration:

- Android decompilation:
  `analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManager.java:535-538`;
- iOS IR: `analysis/toolchain_iosarm64_dump_ir.txt:6078-6107`.

No app or Haversine code in this artifact writes the JSON or decoded image to
a named file. The explicit update candidate and decoded bytes are process
memory. A `CACHE_SUBDIRECTORY = "haversine_download"` constant exists at:

- Android:
  `analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManagerKt.java:13-18`;
- iOS:
  `analysis/toolchain_iosarm64_dump_ir.txt:2490-2498`.

However, it has no reference elsewhere in either exact IR dump or the
decompiled AAR. It is dead/residual in `03202f5`, not evidence that a firmware
file is saved under that name. There is therefore no supported on-disk
firmware path or stable `.bin` cache to copy from this app revision.

## 4. When the app installs an update

This is an automatic advertisement-driven path, not a manual settings
action. `HaversineSatellite.handleAdvertisement` asks the update delegate for
a candidate while servicing an allowed satellite, then queues the firmware
operation:

`analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/HaversineSatellite.java:149-211`.

`shouldProgramFirmware` imposes three checks:

1. advertisement RSSI must be at least `-85 dBm`;
2. `(manifest hardware major << 8 | minor)` must exactly equal the ring's
   reported hardware version;
3. manifest firmware `(major << 8 | minor)` must be strictly greater than the
   ring's reported firmware version.

Exact code:

`analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/HaversineSatellite.java:231-243`.

This normal path therefore does not intentionally downgrade or reinstall the
same version. The hardware values passed into the app-side manager are 11.0,
and the manifest still has to match the ring-reported hardware before
programming.

## 5. Handoff from app memory to the native updater

Android's decoded `FirmwareUpdate.data` is passed unchanged to:

```java
new SuotaOperation(
    firmwareUpdate.firmwareVersionMajor,
    firmwareUpdate.firmwareVersionMinor,
    firmwareUpdate.data
)
```

Evidence:

- call and update callbacks:
  `analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/HaversineSatellite.java:286-346`;
- Java-to-native constructor:
  `analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/operations/SuotaOperation.java:8-21`.

`HaversineSuotaOperation_init` copies the supplied image into its own native
allocation. Exact native objects:

- `extracted/iossimulatorarm64-native-objects/satellite-arm64/HaversineSuotaOperation.o`;
- `extracted/iossimulatorarm64-native-objects/satellite-x86_64/HaversineSuotaOperation.o`.

The DWARF identifies the original source as
`HaversineSatelliteLibrary/Sources/Shared/HaversineSuotaOperation.c`.
Relevant recovered source-line mappings are:

| Native behavior | Original source line(s) from DWARF |
|---|---:|
| phase enumeration | 14 |
| operation state, image pointer and length | 34-55 |
| receive initial/final version bytes | 75-105 |
| child completion, retry and version verification | 109-256 |
| construct next child operation | 262-371 |
| initializer/copy image | 417-446 |
| `shouldRetry` | 449-451 |

The phase enum is:

```text
READ_INITIAL_PLATFORM_VERSIONS
CONFIGURE_STATE
ERASE_STATIONARY_DATA
ERASE_PRIMARY_IMAGE
PROGRAM_PRIMARY_IMAGE
RESET_SATELLITE
VERIFY_RESET
READ_FINAL_PLATFORM_VERSIONS
FINISHED
```

## 6. What “SUOTA” means in this build

The native operation uses Haversine's existing Telesto request/data channel.
Its important child operations, recovered from exact object code and DWARF,
are:

| Phase | Request |
|---|---|
| read versions | Telesto READ (`3`), `TELESTO_PLATFORM_VERSIONS` = `0x40030006`, length 4 |
| configure | system input `INPUT_ENTER_STREAMING_STATE` (`7`) |
| erase stationary state | Telesto ERASE (`1`), `TELESTO_STATIONARY_DATA` = `0x40000002`, length `0x1000` |
| erase image | Telesto ERASE (`1`), `TELESTO_PRIMARY_IMAGE` = `0x40060000`, length = decoded image size |
| program image | Telesto PROGRAM (`2`), `0x40060000`, length = decoded image size, data = decoded `image` bytes |
| reset | system input `INPUT_PANIC` (`12`) |
| verify | reconnect and read final platform versions |

The object-code locations in the x86_64 object are:

- `_HaversineSuotaOperation_init`: `0x000-0x112`;
- `_SuotaOperation_startNextChild`: `0x26b-0x413`;
- `_SuotaOperation_handleReceivedDataFromChild`: `0x414-0x4b7`;
- `_SuotaOperation_handleCompletionFromChild`: `0x4b8-0x797`;
- `HaversineSuotaOperation_shouldRetry`: `0x25e-0x26a`.

Thus, “SUOTA” here is Haversine's multi-phase firmware-update operation over
Telesto. The app does not expose a second firmware-specific BLE download
service. BLE packetization remains the same Haversine link-controller path
described in the main reverse-engineering report.

## 7. Completion, reconnects, and UI

The updater is expected to disconnect when the ring resets. Android retries
the same native operation across as many as two reconnect attempts after the
initial attempt:

`analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/HaversineSatellite.java:314-345`.

After the final version read, Haversine reports success or failure and updates
its cached platform version on success:

`analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/HaversineSatellite.java:296-310`.

The KMP delegate converts those callbacks into
`SatelliteStatus.FirmwareUpdating.Started/Success/Failed`:

`analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManager.java:518-528`.

`RingSync` logs and republishes those as app-level events at
`analysis/mobileapp_repo/experimental/src/commonMain/kotlin/coredevices/ring/service/RingSync.kt:579-639`.
During pairing, the UI replaces the pairing controls with a non-cancellable
“Firmware Update in Progress” display and asks the user to keep the ring
nearby:

- Android:
  `analysis/mobileapp_repo/experimental/src/androidMain/kotlin/coredevices/ring/ui/screens/RingPairing.android.kt:75-120`;
- iOS:
  `analysis/mobileapp_repo/experimental/src/iosMain/kotlin/coredevices/ring/ui/screens/RingPairing.ios.kt:89-160`.

## 8. Integrity and trust boundary

At the app/Haversine acquisition layer:

- HTTPS authenticates the GitHub Raw host in the usual platform TLS model;
- the URL selects a mutable branch (`core_ring`), not an immutable commit;
- no image hash, CRC, detached signature, or signing key is parsed by this
  exact app-side manifest reader;
- version/hardware fields are trusted from the same JSON that supplies the
  image;
- native Haversine verifies the reported firmware version after reset, but
  that is not a cryptographic authenticity check.

The ring bootloader/firmware might perform an additional image-format,
checksum, signature, or boot validation internally. Client-side artifacts
alone cannot prove or disprove that firmware-side behavior. It should not be
claimed that arbitrary modified bytes will boot merely because the app will
send them.

## 9. Can a firmware binary be obtained?

Yes, if the public manifest remains accessible. The exact acquisition is:

1. download `haversine_update.json` with an ordinary HTTPS GET;
2. record its four version fields;
3. Base64-decode the `image` string without textual transformation;
4. save those decoded bytes under a locally chosen `.bin` name;
5. record hashes of both the downloaded JSON and decoded image.

No Pebble login, Firebase token, paired ring, phone cache, or BLE session is
needed merely to retrieve the bytes. A paired, compatible ring is needed only
for the app's installation path.

Because `core_ring` is a mutable Git branch, a retrieved image is a snapshot
of whatever that branch serves at retrieval time. A reproducible evidence
copy should include retrieval time, final resolved HTTP URL, headers such as
ETag/Last-Modified if present, manifest bytes, decoded image bytes, sizes, and
SHA-256 hashes.

## 10. Concise answer to the user's question

The app receives the ring firmware as a Base64 field embedded directly in a
public GitHub Raw JSON manifest. It prefetches that document in the
background, keeps the candidate in memory for up to three hours, and
automatically sends it to a nearby compatible ring through Haversine's
Telesto-based `SuotaOperation`. There is no authenticated firmware API and no
stable app-created `.bin` cache path in this revision. A copy of the current
firmware can be obtained by downloading the manifest and decoding its
`image` field.
