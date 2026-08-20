# Pairing, registration, persistence, and crypto audit

Date: 2026-08-20
Target release: `03202f5`

## Bottom line

The inspected Haversine release does **not** create, receive, derive, persist, or use an application-level shared secret during Index registration.

Registration writes a versioned record containing:

1. a non-cryptographic 32-bit fingerprint of the Firebase UID,
2. a 32-bit Unix timestamp, and
3. the Firebase UID itself in a fixed 129-byte character array.

The serialized record is 141 bytes. Haversine adds a four-byte Telesto length prefix and sends the resulting 145 bytes with a Telesto erase-and-program request to virtual address `0x40000000`.

There is no challenge, nonce, random generation, public/private key exchange, KDF, cipher, authentication tag, or returned key in this path. The DD-Rice/collection decoder also accepts only collection bytes and an index; it has no key or registration-state input.

The only cryptographic relationship evidenced during pairing is the platform-controlled BLE bond/link security. Its keys are generated and retained by the OS/Bluetooth stacks on the phone and ring, not by Haversine or the app preferences inspected here.

Physical flash encryption inside the ring remains a separate firmware/hardware question. These client binaries prove there is no Haversine-managed recording cipher, but they cannot rule out transparent encryption below the Telesto virtual-memory interface.

## Artifact provenance

Relevant exact artifacts:

| Artifact | SHA-256 |
|---|---|
| `haversine-iosarm64-03202f5.klib` | `4f14675b857cff246dbc8ad607c3003972cc04506823e5ab40a42055eb7ec576` |
| `haversine-iossimulatorarm64-03202f5.klib` | `9ba0534f81762d59c2e73b24f053933836fe10cbdf7497d578f8e950f53e46a7` |
| `haversine-iosarm64-03202f5-cinterop-PPCommon.klib` | `d77e25abb94f8a199dab7857cb8250d0022460e0319a843fc8805c46244d2732` |
| `haversine-iossimulatorarm64-03202f5-cinterop-PPCommon.klib` | `d6ada452614b9c178206f3ca81ed9c70499dc021b70fd21af15dd11442aa117b` |
| `haversine-iosarm64-03202f5-cinterop-haversineSatelliteLibrary.klib` | `d515f1a62ad2ed7479fa964cbeb2f63e68443d4309d83c87fed4ba8f9ab1dc21` |
| `haversine-iossimulatorarm64-03202f5-cinterop-haversineSatelliteLibrary.klib` | `98cf6bad80999aa22bc58597b43bf5400ce7e0a486481199b8a757f0f54555bf` |
| same-release Android debug AAR used as cross-platform corroboration | `6d41a5d0ec410646d9a903997a1a8a73e6ef0fc281cae07216a6a230c0e76989` |

The public app checkout is commit:

`6d6e2ebb010006e24959f300755516b84843b936`
`index: provide paired ring to haversine for targeting, update haversine fixes MOB-6143`

The exact device and simulator main-KLIB IR dumps are byte-identical. The physical ARM64 `PPRingApplicationData.o` and simulator variants have different object hashes because of target/build metadata, but implement the same record and fingerprint logic.

## End-to-end registration flow

### Public app

`RingPairing.pairRing(satelliteId)`:

1. obtains `Firebase.auth.currentUser.uid`;
2. on iOS, writes the selected device identifier to local `ring_paired` preferences before connecting (the source comment says this enables the service because the connection attempt pairs);
3. clears the last successful collection index;
4. marks existing transfers as belonging to the previous index iteration; and
5. calls `KMPHaversineSatelliteManager.programSatelliteWithUserID(satelliteId, uid)`.

Evidence:

- `analysis/mobileapp_repo/experimental/src/commonMain/kotlin/coredevices/ring/service/RingPairing.kt`, lines 31-50.
- `analysis/mobileapp_repo/experimental/src/commonMain/kotlin/coredevices/ring/database/Preferences.kt`, lines 45-70 and 117-137.

Android performs the OS relationship first:

1. `CompanionDeviceManager.associate(...)`;
2. `BluetoothDevice.createBond()`;
3. wait for a matching `Bonded` event;
4. persist `ring_paired`;
5. invoke the Haversine registration flow above.

The app does not set a PIN, inject a key, receive a bond key, or read Android's bond material.

Evidence:

- `RingCompanionDeviceManager.android.kt`, lines 74-122.
- `RingPairingViewModel.kt`, lines 120-190.

iOS has no application-visible BLE key exchange. The current public code scans for service `607B5C9B-3700-4E94-F44A-2DF900BCB0C3`, records the CoreBluetooth UUID, and invokes `RingPairing`. Its comment explicitly treats the connection attempt as the action that prompts/platform-pairs.

Evidence:

- `IosRingPairingViewModel.kt`, lines 67-75 and 108-170.
- `RingPairing.kt`, lines 35-38.

### Exact KLIB implementation

The exact iOS KLIB IR for `programSatelliteWithUserID` shows:

```text
PPRingUser_init(userId)
timestamp = time(NULL).toUInt()
appData = PPRingApplicationData_init(user, timestamp)
bufferSize = PPRingApplicationData_serializedSize(appData)
PPRingApplicationData_serialize(appData, buffer, bufferSize)
programSatelliteWithApplicationData(satellite, NSData(buffer))
```

On Android, the same-release decompilation uses `System.currentTimeMillis() / 1000` and the same PPCommon calls.

No cryptographic or secure-storage call occurs between the UID and the program operation.

Both the public `RingPairing` code and the KMP manager interpolate the UID into log messages. That is further evidence it is treated as an identifier rather than secret key material; whether those messages persist depends on the host app's logger configuration.

Evidence:

- `analysis/toolchain_iosarm64_dump_ir.txt`, lines 7889-8045.
- `analysis/decompiled_android_debug/coredevices/haversine/KMPHaversineSatelliteManager.java`, lines 1083-1355.
- The iOS branch waits up to 15 seconds for rediscovery/programming when the satellite is not already discovered; the Android branch uses 30 seconds. `PendingProgrammingOperation` holds only satellite ID, serialized application-data bytes, and a continuation in memory.

## Exact application-data record

The C interop metadata describes the in-memory value as:

```c
struct {
    uint32_t fingerprint;
    uint32_t timestamp;
    struct {
        char uid[129];
    } user;
};
```

The in-memory struct is 140 bytes after tail padding. Serialization version 1 deliberately produces 141 bytes:

| Offset | Size | Encoding | Meaning |
|---:|---:|---|---|
| `0x00` | 4 | `uint32_le` | record version, exactly `1` |
| `0x04` | 4 | `uint32_le` | non-cryptographic UID fingerprint |
| `0x08` | 4 | `uint32_le` | Unix time in seconds |
| `0x0c` | 129 | bytes | UID, NUL-terminated/zero-padded by `strncpy` |
|  | **141** |  | total |

`PPRingApplicationData_serializedSize()` returns `0x8d` (141). Serialization rejects a UID longer than 128 bytes. There is no field for a key, secret, IV, nonce base, public key, registration token, or authentication tag.

Exact physical ARM64 evidence:

- `extracted/iosarm64-cinterop-PPCommon/static_objects/PPRingApplicationData.o`
- symbols:
  - `_mixBits32` at object offset `0x000`
  - `__fingerprint` at `0x064`
  - `_PPRingApplicationData_fingerprintMatchesUserId` at `0x160`
  - `_PPRingApplicationData_init` at `0x1bc`
  - `_PPRingUser_init` at `0x240`
  - `__serialize_v1` at `0x250`
  - `_PPRingApplicationData_serializedSize` at `0x38c`
  - `_PPRingApplicationData_serialize` at `0x394`

The simulator x86-64 object independently shows the same layout and total size:

- `extracted/iossimulatorarm64-native-objects/ppcommon-x86_64/PPRingApplicationData.o`

## Fingerprint algorithm and why it is not a secret

The UID is copied into a zero-padded 132-byte scratch buffer and interpreted as 33 little-endian 32-bit words. Each word is passed through this fixed integer mixer, and the 33 results are XORed:

```text
mix(x):
    x = x + (x << 12) + 0x7ed55d16
    x = (x ^ (x >> 19)) ^ 0xc761c23c
    x = x + (x << 5)                         // 33*x
    x = ((x << 9) + 0xaccf6200)
        ^ (x + 0xe9f8cc1d)
    x = x + (x << 3) + 0xfd7046c5           // 9*x + constant
    return (x ^ (x >> 16)) ^ 0xb55a4f09

fingerprint(uid):
    scratch = uid, zero-padded to 132 bytes
    return XOR(mix(u32le(scratch[i:i+4])) for i = 0,4,...,128)
```

This is an unkeyed fixed integer mixer, not a cryptographic hash, MAC, KDF, or password verifier.

Additional exact behavior:

- `fingerprintMatchesUserId(advertised, uid)` compares only the low 16 bits.
- `fingerprintMatchesNoUser(fingerprint)` accepts values whose low 16 bits are `0xffff`.
- `fingerprintMatchesFailsafe(fingerprint)` checks the full value `0xdeaddead`.
- `PPRingApplicationData_hasUser(...)` returns `true` unconditionally in this build.

The UID itself is stored alongside the fingerprint, so the fingerprint cannot serve as concealed key material even in principle.

## How the record is programmed

The Android native bridge provides a particularly clear, symbolized implementation:

`Java_com_wtlp_haversinesatellitelibrary_operations_ProgramApplicationDataOperation_init` at VA `0xd180`:

1. copies the 141-byte Java array;
2. calls `TelestoLengthPrefixedData_create`;
3. constructs a packed Telesto request with:
   - type `5` (`erase + program`);
   - address `0x40000000` (`TELESTO_APPLICATION_DATA_STORE`);
   - offset `0`;
   - length `145`;
4. submits the 145-byte data payload.

`TelestoLengthPrefixedData_create` at VA `0x18820` allocates `input_length + 4`, writes that total length as a little-endian `uint32`, then copies the input bytes.

The resulting payload for a normal registration is:

| Offset | Size | Meaning |
|---:|---:|---|
| `0x00` | 4 | total Telesto object length, `145` / `0x00000091` |
| `0x04` | 141 | serialized version-1 application-data record |

Thus the first eight bytes are normally:

```text
91 00 00 00 01 00 00 00
```

The control request is the normal 13-byte Telesto request (`type`, `address`, `offset`, `length`). The response is the normal 12-byte Telesto response (`error`, `info`, `length`). Neither structure has an authentication, challenge, key, or nonce field. The KMP programming callback ignores received data and consumes only success/failure.

Erasing registration data is a separate ordinary Telesto erase request to the same virtual address, offset `0`, length `1` (`HaversineSatellite.eraseApplicationData`). The public app checkout does not call it.

## Relationship to the observed one-byte `00` write

The exact Android wrapper identifies the observed UUIDs as:

| UUID | Haversine meaning |
|---|---|
| `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` | Haversine GATT service |
| `DAAD3D52-237C-90A7-B54B-8854A134D801` | Telesto **data** channel |
| `C0EF558A-2058-FABF-A140-8D5ACDE50B39` | Telesto control channel |
| `1D1F4039-23F5-33B2-C24E-704351F20585` | system-input channel |

`DAAD...` is not a dedicated secret-exchange or pairing characteristic; it is the generic Telesto payload channel. The full Haversine application registration operation is 145 bytes, not one byte, and uses both the control and data channels.

Therefore an isolated observed `00` write can trigger protected-characteristic access/OS pairing or belong to another operation, but it is not the complete Haversine registration record and is not key material. Assigning its exact intent requires a synchronized BLE/HCI trace from that app revision.

Evidence:

- `analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/transport/HaversineUUID.java`
- `analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/transport/LinkTransport.java`

## Persistence inventory

### Ring-side application data

The client supplies the 145-byte length-prefixed record above to virtual address `0x40000000`. The visible content is UID/fingerprint/timestamp only.

What is physically written to flash, and whether firmware transparently encrypts that flash page, cannot be proven from these client artifacts. Any such encryption would be firmware/hardware-managed and would not be based on an application secret found here.

### Haversine Android SDK cache

Storage:

- SharedPreferences file: `com.wtlp.haversinecache`
- entry key: `HaversineSatelliteId.rawValue`
  - on Android this is the device MAC with colons removed
- value: Base64 of Java object serialization, not encryption

Cached fields:

- platform hardware/firmware versions,
- serial number,
- sensor-config version,
- opaque `applicationData` bytes read from the ring,
- advertised fingerprint, and
- last transfer end index.

The cached `applicationData` can contain the registration record/UID. No secret-specific field exists. Clearing this cache causes a future cache refresh; it does not erase the ring or affect decoding.

Evidence:

- `HaversineSharedPreferencesCache.java`, lines 27-105.
- `HaversineSatelliteCacheableState.java`, lines 28-143.
- `HaversineSatellite.java`, lines 72-123 and 149-168.

### Haversine iOS SDK cache

The exact Swift object uses:

- `NSUserDefaults.standard`
- key prefix: `HaversineSatelliteState_`
- full key: prefix plus the ring's CoreBluetooth UUID string
- value: `JSONEncoder` output stored as `NSData`

Cached fields recovered from the Codable symbols:

- `satelliteName`,
- `platformVersions`,
- `serialNumber`,
- `sensorConfigVersion`,
- `applicationData`,
- `advertisedFingerprint`, and
- `lastTransferEndIndex`.

This is standard UserDefaults JSON storage, not Keychain storage and not encrypted by Haversine.

Exact object evidence:

- `extracted/iossimulatorarm64-native-objects/satellite-x86_64/HaversineEnvironment.o`
- `cacheKeyPrefix` getter at object offset `0x0a70` returns `HaversineSatelliteState_`.
- `fetchCachedState` at `0x0aa0` calls `dataForKey:` and `JSONDecoder`.
- `cacheState` at `0x0ca0` calls `JSONEncoder` and `setObject:forKey:`.

### Public app preferences

The app constructs the default multiplatform `Settings()` implementation without a secure-storage wrapper.

Relevant keys:

| Key | Type | Purpose |
|---|---|---|
| `ring_paired` | string or absent | selected Android MAC/CoreBluetooth UUID |
| `last_sync_index` | integer or absent | last successfully handled collection index |

`ring_pairedOld` is migration code that attempts to read the same `ring_paired` key as a Boolean; it is not a separate secret.

Pairing clears `last_sync_index`. Neither value is key material.

Evidence:

- `Preferences.kt`, lines 45-70 and 117-137.
- app DI: `composeApp/.../di/utilModule.kt`, `single { Settings() }`.
- `PrefsCollectionIndexStorage.kt`, lines 12-25.

### OS association and bond state

Android additionally persists:

- a Companion Device Manager association; and
- OS Bluetooth bond state created by `BluetoothDevice.createBond()`.

The app sees association metadata and `Bonded`/`Unbonded` events, not the BLE Long Term Key. `CompanionDeviceManager.disassociate()` removes association metadata but is not itself a Bluetooth `removeBond()` call. No `removeBond`, PIN injection, or bond-key export exists in the inspected code.

On iOS, CoreBluetooth owns the peripheral relationship and any bond keys. No Keychain/Security-framework API is invoked by Haversine to store a per-ring key.

### Other key-like state excluded from the registration hypothesis

- The exact Swift satellite archive contains an `apiKey` property in `HaversineDefaultDebugDelegate`. Symbols and adjacent methods show it belongs to debug-info HTTP/Mongo Atlas upload. It is not reached from registration, Telesto transfer, PPCollection parsing, or audio decoding.
- The public app has an iOS `IntegrationTokenStorage` that uses Keychain for unrelated third-party integration tokens. It is not used by `RingPairing`, `KMPHaversineSatelliteManager`, Haversine transfer, or PPCommon.
- Firebase manages account authentication and supplies a UID. Firebase's own auth-token storage is outside Haversine and is not converted into a ring encryption key.

## Permission and “ownership” checks are identifiers, not authentication

`KMPHaversinePermissionsDelegate.shouldHandleAdvertisement` accepts an advertisement if any of these hold:

1. fingerprint is the failsafe value;
2. fingerprint is an old-firmware constant (`1102124456`);
3. device ID matches an in-memory pending programming request; or
4. device ID case-insensitively matches `pairedSatelliteIdProvider()`.

`shouldTransferCollections` checks only that the satellite ID matches the locally stored paired ID.

Although PPCommon exposes `fingerprintMatchesUserId`, this delegate does not call it in this release. The fingerprint is used as a cache/state marker and special-mode discriminator, not a cryptographic client authenticator.

Evidence:

- `KMPHaversinePermissionsDelegate.java`, lines 75-205 and 218-255.
- corresponding exact KLIB IR around lines 2122-2481.

## Crypto reachability audit

### Positive trace

Registration:

```text
Firebase UID
  -> fixed integer fingerprint + Unix timestamp
  -> 141-byte versioned record
  -> Telesto length prefix
  -> erase-and-program 0x40000000
```

Recording decode:

```text
Telesto collection bytes
  -> HaversineTransferDelegate.handleDidFinish
  -> PPCollection(index, data)
  -> PPCollection_createAudioTimeline
  -> PCM samples / TransferComplete
```

No key, preferences/cache object, UID, fingerprint, or registration record is an argument to `PPCollection`, `PPCollection_createAudioTimeline`, the DD-Rice decoder, or `TransferComplete`.

### Negative searches

The following were absent from the exact Haversine/PPCommon path:

- `javax.crypto`, `java.security`, Android Keystore, `Cipher`, `SecretKey`, `MessageDigest`, `KeyAgreement`;
- CryptoKit, CommonCrypto, `CCCrypt`, Security-framework `SecItem`/`SecKey`;
- AES, CCM, GCM, ChaCha, Poly1305, HKDF, HMAC, ECDH, Curve25519;
- nonce/IV/session-key/shared-secret handling;
- random-number generation used by registration or transfer.

The Android native dependencies are:

```text
libhaversinesatellitelibrary.so:
  libppcommon.so, liblog.so, libc.so, libm.so, libdl.so

libppcommon.so:
  liblog.so, libc.so, libm.so, libstdc++.so, libdl.so
```

There is no crypto/TLS library dependency in either native library. The exact Apple object archives likewise have no CommonCrypto, CryptoKit, or Security-framework undefined symbol used by this path.

This absence is supporting evidence, not the sole basis for the conclusion. The decisive evidence is the complete, keyless registration and decode call paths and the recovered record layout.

## Answers to the shared-secret hypothesis

| Question | Finding |
|---|---|
| Is an application-level secret generated during registration? | **No.** Only UID fingerprint and timestamp are computed. |
| Is a secret received from the ring? | **No.** Programming completes with an ordinary Telesto status response; the callback ignores response data. |
| Is there a public/private key exchange? | **No.** No exchange messages, key APIs, random values, or key fields exist. |
| Is a persistent Haversine key stored? | **No.** Persisted Haversine/app state is identifier, cache metadata, application-data bytes, and transfer index. |
| How would such a key be indexed? | Not applicable. Ordinary state is indexed by MAC/CoreBluetooth UUID. |
| Does recording decoding reference registration state? | **No.** It consumes collection bytes directly. |
| Does clearing pairing state make old captured recordings undecodable? | **No.** The codec has no key dependency. It can prevent future device discovery/access until re-paired. |
| Is Bluetooth bonding the only evidenced persistent cryptographic relationship? | **Yes, within these artifacts.** Its keys and security method are OS/firmware controlled. |

## Layer-by-layer crypto conclusion

| Layer | Finding | Confidence / limitation |
|---|---|---|
| BLE link encryption | **Platform controlled; likely active after bonding when characteristic permissions require it.** | Client code explicitly bonds on Android and relies on connection-triggered pairing on iOS, but GATT permission bits/SMP mode require firmware or a capture. |
| Haversine application-layer encryption in transit | **No.** | Telesto bytes go directly to collection parsing and decoding; no decrypt/key stage exists. |
| Haversine-managed recording encryption at rest | **No.** | No secret/key/cipher exists, and returned collection bytes are directly parseable. |
| Firmware/hardware-transparent physical flash encryption | **Unknown.** | It could be below the Telesto virtual address and invisible to the app; requires firmware or flash analysis. |

Conceptually, the supported path is:

```text
Haversine plaintext Telesto request/data
  -> optional OS BLE link encryption
  -> ring Telesto virtual-memory service

ring collection bytes
  -> optional OS BLE link encryption on air
  -> CoreBluetooth/BluetoothGatt plaintext bytes
  -> Haversine parser + DD-Rice decoder
```

## Reset and replacement behavior

- Clearing `ring_paired` changes local targeting/permission policy only.
- Clearing the Haversine SDK cache changes only cached metadata and forces reread.
- Reprogramming a ring uses erase-and-program and overwrites its application-data record.
- The Haversine SDK exposes `eraseApplicationData`; the inspected public pairing/settings flow does not call it.
- The Android app's `disassociate` code does not explicitly remove the Bluetooth bond.
- A failed programming attempt may leave `ring_paired` set because both Android and iOS persist the ID before Haversine programming succeeds.
- None of these actions cryptographically invalidate already captured collection bytes.

## Remaining unknowns and discriminating evidence

1. **BLE SMP/security mode:** determine characteristic permissions, Just Works vs passkey/numeric comparison, LE Secure Connections vs legacy, MITM requirement, and bond flags from firmware/GATT metadata or an HCI trace.
2. **Physical at-rest security:** inspect ring firmware and raw flash, or compare flash bytes with Telesto-returned bytes.
3. **Observed one-byte write:** capture a complete connection with timestamps for control and data characteristics to identify which operation owns it.
4. **Firmware use of UID:** the app writes UID/fingerprint/timestamp, but client artifacts cannot prove every firmware-side policy attached to them.
5. **Exact cached `applicationData` boundary:** wrappers prove it is opaque registration/application data, but a capture or the full native update-cache decompilation is needed to state whether the local cache retains the Telesto four-byte length prefix.

## Reproducible commands used

```sh
# Locate high-level registration and persistence calls.
rg -n -i \
  'programSatelliteWithUserID|PPRingApplicationData|PPRingUser|ring_paired|last_sync_index|createBond|Keychain|secret|cipher|encrypt|decrypt' \
  analysis/decompiled_android_debug analysis/toolchain_iosarm64_dump_ir.txt \
  analysis/mobileapp_repo/experimental/src

# Inspect exact physical PPCommon application-data implementation.
xcrun llvm-nm -nm \
  extracted/iosarm64-cinterop-PPCommon/static_objects/PPRingApplicationData.o
xcrun llvm-objdump --macho --disassemble \
  extracted/iosarm64-cinterop-PPCommon/static_objects/PPRingApplicationData.o

# Inspect Android native programming and length-prefix construction.
xcrun llvm-objdump \
  --disassemble-symbols=Java_com_wtlp_haversinesatellitelibrary_operations_ProgramApplicationDataOperation_init \
  --x86-asm-syntax=intel \
  extracted/android-debug/jni/x86_64/libhaversinesatellitelibrary.so
xcrun llvm-objdump \
  --disassemble-symbols=TelestoLengthPrefixedData_create \
  --x86-asm-syntax=intel \
  extracted/android-debug/jni/x86_64/libhaversinesatellitelibrary.so

# Confirm iOS cache implementation and prefix.
xcrun llvm-nm -nm \
  extracted/iossimulatorarm64-native-objects/satellite-x86_64/HaversineEnvironment.o
xcrun llvm-objdump --macho --disassemble --x86-asm-syntax=intel \
  extracted/iossimulatorarm64-native-objects/satellite-x86_64/HaversineEnvironment.o

# Check native dynamic dependencies.
objdump -p extracted/android-debug/jni/arm64-v8a/libhaversinesatellitelibrary.so
objdump -p extracted/android-debug/jni/arm64-v8a/libppcommon.so

# Search exact Java/KLIB material for crypto APIs and whole-word algorithm names.
# Whole-word matching avoids "AES" substrings in unrelated Swift mangled symbols.
rg -n -i -P \
  'javax\.crypto|java\.security|android\.security|CryptoKit|CommonCrypto|SecItem|\b(Cipher|SecretKey|KeyStore|MessageDigest|KeyAgreement|HKDF|HMAC|AES|ChaCha|Poly1305|Curve25519|ECDH|nonce|encrypt|decrypt)\b' \
  analysis/decompiled_android_debug analysis/toolchain_iosarm64_dump_ir.txt

for f in \
  extracted/iossimulatorarm64-native-objects/ppcommon-arm64/*.o \
  extracted/iossimulatorarm64-native-objects/satellite-arm64/*.o
do
  xcrun llvm-nm -u "$f"
done | rg -i \
  '^(_CCCrypt|_CCKey|_CC_SHA|_SecItem|_SecKey|_SecRandom|.*CryptoKit|.*CommonCrypto|.*ChaCha|.*Poly1305|.*HKDF|.*HMAC|.*Curve25519|.*ECDH|_EVP_)'
```
