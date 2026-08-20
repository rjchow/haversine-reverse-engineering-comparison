# Pebble Index 01 firmware acquisition

Investigation date: 2026-08-20 (Asia/Singapore)

## Result

The production Index update image is publicly and anonymously downloadable.
It is not embedded in the Maven KLIB. The KLIB downloads a one-line JSON
manifest from a public GitHub repository, Base64-decodes its `image` field, and
passes those bytes to the native Haversine SUOTA updater.

The current public Core Ring image at investigation time is:

| Field | Value |
|---|---|
| Firmware version | `3.75` |
| Target hardware | `11.0` |
| Manifest `creationDate` | `1785874793` / `2026-08-04T20:19:53Z` |
| Decoded image size | `29,288` bytes |
| SUOTA executable size | `29,224` bytes |
| Image SHA-256 | `993ec97e0db831e3f35d5c53ed8809a6dbe2db08879637f981cdda0e2c4ba090` |
| Manifest SHA-256 | `6e078a03ac84eff086825218038451c8fccbbe52ccd104930835221b916a0b91` |
| Git commit | `e8c7e2352460eeb87f7b905e12e7808abd2c5cce` |
| Commit time | `2026-08-05T14:45:55-04:00` |
| Commit subject | `Core Ring 3.75` |
| Manifest Git blob | `0e5034fbb9cacadcd073c5ba74728c9b0d78498c` |

Preserved files:

- `artifacts/firmware/index01-core-ring-3.75-hw11.0-manifest.json`
- `artifacts/firmware/index01-core-ring-3.75-hw11.0.bin`
- `artifacts/firmware/SHA256SUMS`
- `artifacts/firmware/history/` (18 reachable Core Ring revisions)

## Provenance

The exact iOS ARM64 KLIB IR contains this URL:

```text
https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json
```

Evidence:

- `analysis/toolchain_iosarm64_dump_ir.txt:2502` contains the constant.
- The `requestUpdate` body around lines 6,130-6,448 performs an HTTP GET,
  requires a successful HTTP status, parses the body as JSON, Base64-decodes
  `image`, reads the four firmware/hardware version fields, and constructs
  `HaversineFirmwareUpdate`.
- The app enables Ktor `HttpCache`; the image is not bundled in the KLIB.

The upstream repository identifies itself as “Public Hyperion firmware
releases”:

- Repository:
  <https://github.com/HyperionSensing/firmware_releases>
- Mutable production manifest:
  <https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json>
- Immutable manifest used for the preserved copy:
  <https://raw.githubusercontent.com/HyperionSensing/firmware_releases/e8c7e2352460eeb87f7b905e12e7808abd2c5cce/haversine_update.json>
- Immutable commit:
  <https://github.com/HyperionSensing/firmware_releases/commit/e8c7e2352460eeb87f7b905e12e7808abd2c5cce>

The endpoint returned HTTP 200 without credentials. `git ls-remote` resolved
`refs/heads/core_ring` to
`e8c7e2352460eeb87f7b905e12e7808abd2c5cce` at acquisition time.

The repository stores no separate `.bin`: the exact binary is the standard
Base64 decoding of the JSON `image` string. The manifest is 39,203 bytes and
the Base64 value is 39,052 characters.

## Container and integrity validation

The decoded file is a 64-byte Dialog/Renesas single-image SUOTA header followed
by the executable. The current header begins:

```text
00000000  70 51 aa 00 28 72 00 00  dd 51 35 1e 31 2e 32 30
00000010  00 ff ff ff ff ff ff ff  ff ff ff ff 00 ff ff ff
```

Parsed fields:

| Offset | Bytes | Meaning |
|---:|---|---|
| `0x00` | `70 51` | SUOTA single-image signature |
| `0x02` | `aa` | valid-image flag |
| `0x03` | `00` | image identifier |
| `0x04` | `28 72 00 00` | little-endian executable size `29,224` |
| `0x08` | `dd 51 35 1e` | little-endian CRC-32 `0x1e3551dd` |
| `0x0c` | `31 2e 32 30 00 ...` | header version string `1.20` |
| `0x20` | `00` | signing/encryption flags |

The size relation is exact:

```text
64-byte header + 29,224-byte executable = 29,288-byte file
```

CRC validation was performed over precisely the executable bytes:

```python
import struct
import zlib

code_size = struct.unpack_from("<I", image, 4)[0]
stored_crc = struct.unpack_from("<I", image, 8)[0]
calculated_crc = zlib.crc32(image[64:64 + code_size]) & 0xffffffff
assert stored_crc == calculated_crc == 0x1e3551dd
```

The same header-size and CRC checks pass for all 18 archived Core Ring images.

Renesas documents this exact single-image layout, including the `70 51`
signature, valid flag, executable size, CRC, and security flags:

<https://lpccs-docs.renesas.com/Tutorial_SDK6/suota_memory.html#single-image-header>

## Signing and encryption status

The image header security flag at byte 32 is `0x00`. Under the documented
Renesas layout:

- `0x00`: not signed or encrypted;
- `0x01`: encrypted;
- `0x02`: signed;
- `0x03`: signed and encrypted.

Therefore the acquired image declares itself **neither signed nor encrypted**.
All 18 reachable Core Ring history images also use flag `0x00`.

Additional corroboration:

- The JSON schema contains only
  `firmwareVersionMajor`, `firmwareVersionMinor`,
  `hardwareVersionMajor`, `hardwareVersionMinor`, `creationDate`, and `image`.
  It exposes no checksum, signature, key ID, or detached-signature URL.
- The app fetch/decode path consumes no hash or signature field.
- The upstream Git commit has no `gpgsig` header and `git show
  --show-signature` reports no signature.

The SUOTA CRC detects accidental corruption but is not an authenticity
mechanism. A CRC can be recomputed after a malicious modification.

HTTPS transport and the immutable Git commit provide useful acquisition
provenance for this analysis, but they do not turn the firmware itself into a
cryptographically signed image. The production app’s branch URL is mutable.

## Historical archive

Eighteen Core Ring revisions reachable from the current `core_ring` branch
were preserved, each as the original JSON plus decoded image:

| Version | Commit | Image bytes | CRC-32 | Image SHA-256 |
|---:|---|---:|---:|---|
| 3.6 (commit says 3.06) | `5959240b` | 26,864 | `2144df1c` | `ed1a696e38f16e5c163f313f4f297ae7ab09c74ba4c146e894b207fabbe66271` |
| 3.10 | `4efe0f50` | 26,916 | `2144df1c` | `438726a399f1c1b8584a38ca2e9a0156f7f1608bbe1994001e52b51819692f7f` |
| 3.13 | `f6766c67` | 27,516 | `2144df1c` | `5d4e3322226d1b45f208c300c40183fe95a30f8b869467661bd5736a8d662956` |
| 3.14 | `454008b1` | 27,524 | `2144df1c` | `3f0872f8dd26a80eed37e697ff2d2078a557a13530976ec0d1180d1698860830` |
| 3.17 | `63bd1e64` | 27,648 | `2144df1c` | `e241e82c96d842fb0734b4f0c228fe130994a8b5c13d52ddc1f2301c3a5aee37` |
| 3.18 | `f601752a` | 27,744 | `6f77992e` | `aa546dc7ec0ec35ae1e5ac3d0dd34dcbe61f891fdb201fc2f522ee9254880d96` |
| 3.35 | `6c3495dd` | 28,356 | `ce914519` | `bef5dac067c948cb33e58ad62c67459edd3fd42174576b1c5c2e4826af0699ed` |
| 3.41 | `0e19bc33` | 29,104 | `15ac93ab` | `bf23e520a8ea3ca45ccb976d4c451296e91ada2c20f1374c31ea04e6deb25251` |
| 3.49 | `594264c2` | 29,316 | `d5169546` | `ba9483c60ff31d4f955771e8a31b1179bfbc07b633e2277de06b1c0e21fbe231` |
| 3.56 | `e60f982d` | 29,468 | `f8a26fb6` | `92946d38c0cba08e87faad8635e09442bf5df0f44412177fec25b711089c7b79` |
| 3.58 | `4ed4e6fa` | 29,532 | `1b117b76` | `631de508e3829d1a767aff4529ba54624bc567a45585dc42f57f8c38315a7e6e` |
| 3.60 | `95352ed1` | 29,412 | `915c8a55` | `848c7ad335fd6e7c4fdf8a8bbc2414f73a9b495593b542e653e1519f877bf375` |
| 3.62 | `1eb89f3a` | 29,548 | `274f0325` | `d1acaae64fa88fc29d121cb1c981213baaa640391ab808ac5d80dcaea7d56ecc` |
| 3.63 | `9617bc0a` | 29,580 | `2afc24b5` | `99bceaac560ac5ba364d5b22f41393757892c0adb7ed0ac4488d8008cd43c15d` |
| 3.67 | `4196fc01` | 29,580 | `588c18b9` | `ee711c67f9e1618cc52098f305b5302bf7b07bbbed636f206badd1d76882ac3b` |
| 3.73 | `72850541` | 29,580 | `8f66b391` | `7ed7c0db83a5aa402c9ed33c03f19beaf3984a3c9f5d63a68cbb6600ef3f573e` |
| 3.74 | `1bf2b241` | 29,224 | `c7c25d37` | `e2d1a1f731dae07e91b1d37439f81343e4f26750f7d210e19d4e8e428b4f12dd` |
| 3.75 | `e8c7e235` | 29,288 | `1e3551dd` | `993ec97e0db831e3f35d5c53ed8809a6dbe2db08879637f981cdda0e2c4ba090` |

The 3.73 commit subject says it is a re-release of 3.67 intended to override
3.72. No 3.72 commit is reachable from the repository’s currently advertised
refs, so it is not included and should not be silently inferred.

`artifacts/firmware/SHA256SUMS` contains full hashes for every preserved
manifest and image and passes `sha256sum -c`.

## Safety caveats

1. The image is explicitly for hardware `11.0`. Do not assume it is safe for
   a different Index hardware revision.
2. A raw `.bin` being available does not make arbitrary manual flashing safe.
   Normal update sequencing, GATT/SUOTA status handling, battery state, and
   reboot behavior still matter.
3. The public image is unsigned and the app fetches a mutable branch URL.
   Preserve and verify the SHA-256 before analysis or any controlled test.
4. The header string `1.20` is not the release version. The release version
   used by Haversine is the manifest’s `3.75`.
5. The decoded image is the complete SUOTA image, including its 64-byte
   header. Stripping that header would not reproduce what the app sends.
