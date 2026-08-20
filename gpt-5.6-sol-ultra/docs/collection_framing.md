# Collection framing and multipart/audio-adjacent TLVs

Status: completed 2026-08-20.

This note reconstructs the byte-level collection envelope accepted by
`GSParseRecordsInRawData`, its TLV dispatch and stepping rules, and the
application semantics of records `0x50` through `0x54`. The result was
cross-checked between the physical-device ARM64 and iOS-simulator x86_64
objects. Kotlin/Native metadata and readable IR provide the field names and
the higher-level multipart behavior.

## Bottom line

- The parser accepts **three outer header encodings**:

  1. a 3-byte big-endian body length;
  2. an `0xff` marker followed by a 16-bit little-endian body length; or
  3. a 4-byte little-endian total length whose high byte is zero.

- Inner records are TLVs. All accepted records except audio use a 16-bit
  little-endian payload length. Audio types `0x50` and `0x51` use a 32-bit
  little-endian payload length.
- There is no collection terminator, CRC, envelope version, or multi-byte
  magic. Length alone ends the collection. The `0xff` byte is the only
  marker-like outer value; imported metadata names it
  `RECORDS_DATA_TRANSFER`.
- Multipart record `0x52` contains a **group start index**, not the current
  part index. The current collection index arrives separately from the
  transfer layer. Every part in one group is expected to repeat the same
  start index.
- The native parser is not a complete bounds validator. In particular, a TLV
  whose claimed end passes beyond the collection end is accepted as the last
  record.

## Evidence used

Primary native objects:

- Device ARM64:
  `extracted/iosarm64-cinterop-PPCommon/static_objects/PPParsing.o`
- Device ARM64:
  `extracted/iosarm64-cinterop-PPCommon/static_objects/PPCollection.o`
- Simulator x86_64:
  `extracted/iossimulatorarm64-native-objects/ppcommon-x86_64/PPParsing.o`
- Simulator x86_64:
  `extracted/iossimulatorarm64-native-objects/ppcommon-x86_64/PPCollection.o`

Readable supporting outputs:

- `analysis/iossimulatorarm64-ppparsing-x86_64-disassembly.txt`
- `analysis/iossimulatorarm64-ppcollection-x86_64-disassembly.txt`
- `analysis/toolchain_iosarm64_ppcommon_dump_metadata.txt`
- `analysis/toolchain_iosarm64_dump_ir.txt`

The ARM64 parser header logic is at function offsets `0x48..0xe4`, and its TLV
loop is at `0x1a0..0x424`. The simulator x86_64 equivalents are
`0x29..0xc5` and `0x24e..0x505`. The two jump tables select the same type
ranges and length widths. An unoptimized Android x86_64 copy in
`extracted/android-debug/jni/x86_64/libppcommon.so` independently exposes the
same source-level control flow at `GSParseRecordsInRawData`.

## Outer collection envelope

All offsets in this section are relative to the first byte passed to
`GSParseRecordsInRawData`. Let `inputLength` be the number of supplied bytes
and `end = data + inputLength`.

### Header selection

The exact decision tree is:

```text
if data == null:
    return PPSwingNoRawData (4)

if inputLength < 3:
    return PPIncompleteRawData (7)

if inputLength >= 4 and data[3] == 0:
    totalLength = data[0] | data[1] << 8 | data[2] << 16
    require totalLength == inputLength
    firstTLV = data + 4
else:
    if data[0] == 0xff:
        bodyLength = u16le(data + 1)
    else:
        bodyLength = u24be(data + 0)
    require bodyLength == inputLength - 3
    firstTLV = data + 3
```

An outer-length mismatch returns `PPInvalidRawData` (6).

The three accepted forms are therefore:

| Form | Header bytes | First TLV | Required relationship |
| --- | --- | ---: | --- |
| BE24 body length | `u24be bodyLength`, with byte 0 not `0xff` | `+3` | `inputLength = 3 + bodyLength` |
| Transfer marker + LE16 | `ff`, `u16le bodyLength` | `+3` | `inputLength = 3 + bodyLength` |
| LE32 total length | `u32le totalLength`, with its high byte necessarily `00` | `+4` | `inputLength = totalLength` |

For the third form, the implementation explicitly assembles only the low
three bytes after first proving `data[3] == 0`. It is consequently equivalent
to a little-endian 32-bit total-length field limited to values below
`0x01000000`.

For an input of exactly three bytes, the parser does not inspect `data[3]` and
uses one of the two 3-byte forms. Thus `00 00 00` and `ff 00 00` are both
accepted empty collections. `04 00 00 00` is the corresponding empty LE32
total-length collection.

### Why byte 3 disambiguates the forms

In a 3-byte-length collection, byte 3 is the first inner record type. Inner
type zero is invalid. In the LE32 form, byte 3 is the zero high byte of the
total length. The parser uses that otherwise-invalid zero to distinguish the
four-byte header without a separate version field.

Byte 3 is therefore **not** a terminator. In the LE32 form the parser advances
past it and begins TLV parsing at offset 4.

### Worked equivalent headers

One nominal multipart-info TLV is nine bytes:

```text
52 06 00 34 12 00 00 01 00
```

It can be wrapped in any of the three accepted ways:

```text
00 00 09  52 06 00 34 12 00 00 01 00
ff 09 00  52 06 00 34 12 00 00 01 00
0d 00 00 00  52 06 00 34 12 00 00 01 00
```

The first two headers say “nine bytes follow”; the third says “thirteen bytes
total.”

## Inner TLV grammar

Both recovered architectures are little-endian. Native unaligned `u16` and
`u32` loads are used for every inner length and for the adjacent fixed-width
fields.

The general record grammar is:

```text
ordinary TLV:
    u8    type
    u16le payloadLength
    u8    payload[payloadLength]

audio TLV:
    u8    type                 // 0x50 or 0x51
    u32le payloadLength
    u8    payload[payloadLength]
```

The dispatch table is exact:

| Type values | Parser action |
| --- | --- |
| `0x01..0x12` | accept, read `u16le` length |
| `0x13..0x20` | `PPInvalidRawData` (6) |
| `0x21..0x22` | accept, read `u16le` length |
| `0x23` (`FULL_CLUB_SETTINGS`) | return `PPFail` (1) immediately |
| `0x24..0x29` | accept, read `u16le` length |
| `0x2a..0x2f` | `PPInvalidRawData` (6) |
| `0x30..0x35` | accept, read `u16le` length |
| `0x36..0x4f` | `PPInvalidRawData` (6) |
| `0x50..0x51` | accept, read `u32le` length |
| `0x52..0x54` | accept, read `u16le` length |
| `0x00` or anything above `0x54` | `PPInvalidRawData` (6) |

Imported enum metadata gives these relevant names:

| Type | Name |
| ---: | --- |
| `0x23` | `FULL_CLUB_SETTINGS` |
| `0x50` | `UNCOMPRESSED_16BIT_AUDIO` |
| `0x51` | `COMPRESSED_16BIT_AUDIO` |
| `0x52` | `COLLECTION_MULTI_PART_INFO` |
| `0x53` | `BUTTON_PRESS_SEQUENCE` |
| `0x54` | `LIFETIME_COLLECTION_COUNT` |
| `0xff` | `RECORDS_DATA_TRANSFER` |

`0xff` is meaningful only in the outer three-byte header. If it is reached as
an inner type, it is above the dispatch-table maximum and is invalid.

### Exact stepping rule

For each accepted TLV:

```text
lengthField = cursor + 1
payloadLength = u16le(lengthField) or u32le(lengthField)
recordSlot[type] = lengthField
cursor += 1 + lengthFieldWidth + payloadLength
```

The stored pointer targets the length field, not the type byte and not the
first payload byte. Duplicate record types are allowed by this loop; the
latest occurrence overwrites the earlier pointer for that type.

After advancing, the loop continues only while `cursor < end`. Any
`cursor >= end` result returns success.

### Native validation gaps

These are implementation facts important for compatibility and for a safe
independent decoder:

- The parser verifies the outer length exactly.
- It does **not** verify that enough bytes remain before reading an inner
  `u16` or `u32` length.
- It does **not** require `cursor == end` after a TLV. A claimed TLV end beyond
  `end` is treated as successful termination.
- It does **not** validate a type-specific minimum, maximum, or exact payload
  length.
- A zero payload length is accepted for any otherwise accepted type, even
  where a downstream consumer expects fixed fields.
- There is no CRC, checksum, trailing marker, or record count.

A defensive reimplementation should bounds-check the length field before
reading it and require
`1 + lengthFieldWidth + payloadLength <= remainingBytes`. Requiring exact
equality at final termination is stricter than the native implementation but
avoids accepting its overshoot case.

### Parser result codes

`GSParseRecordsInRawData` clears all 296 bytes of its output pointer table
before validation. Its framing-related returns are:

| Result | Meaning in this function |
| ---: | --- |
| `0` (`PPSuccess`) | header accepted and TLV loop terminated |
| `1` (`PPFail`) | inner type `0x23` encountered |
| `4` (`PPSwingNoRawData`) | null input data pointer |
| `6` (`PPInvalidRawData`) | outer length mismatch or invalid/unsupported type |
| `7` (`PPIncompleteRawData`) | fewer than three input bytes |

`PPCollection_createFromBinaryData` copies the supplied bytes, invokes this
parser, and returns the parser result through its error output. The Kotlin
`PPCollection(index, data)` wrapper throws when that returned value is
nonzero, so parser errors are not silently ignored at that boundary.

## Audio and adjacent records: `0x50` through `0x54`

Offsets below are relative to the record type byte. `payloadLength` excludes
the type and its own length field.

### `0x50` — uncompressed 16-bit audio

```text
+0x00  u8       type = 0x50
+0x01  u32le    payloadLength
+0x05  u32le    sampleRateHz
+0x09  i16le[]  samples
```

The nominal relationship for `N` samples is:

```text
payloadLength = 4 + 2*N
total TLV bytes = 1 + 4 + payloadLength
```

`PPCollection_createAudioTimeline` computes
`sampleCount = (payloadLength - 4) >> 1`, returns the sample rate unchanged,
and copies `payloadLength - 4` sample bytes. The parser does not check that the
length is at least four or that the sample byte count is even. Those are
required preconditions for safe, meaningful downstream decoding.

If both `0x50` and `0x51` are present, the native timeline function chooses
the uncompressed `0x50` record.

### `0x51` — DD-Rice compressed 16-bit audio

```text
+0x00  u8       type = 0x51
+0x01  u32le    payloadLength
+0x05  u8       DD-Rice channel configuration
+0x06  u32le    compressedBitCount
+0x0a  u32le    sampleRateHz
+0x0e  u8[]     compressed bitstream
```

The non-bitstream payload header is nine bytes:

```text
payloadLength = 9 + compressedByteCapacity
compressedBitCount <= compressedByteCapacity * 8
```

`PPCollection_createAudioTimeline` contains the latter bound as an assertion.
It initializes one decoder and one channel, consumes bits MSB-first within
each byte, and stops successfully when decoder status 3 is returned. No
sample count is stored in the record. The full DD-Rice reconstruction is
documented in `analysis/device_inventory.md`.

The generic parser itself only recognizes the 32-bit TLV length; it does not
validate the nine-byte compressed header.

### `0x52` — collection multipart information

The imported packed C structure is exactly:

```c
struct {
    unsigned short size;
    unsigned int startIndex;
    unsigned char isMultiPart;
    unsigned char isFinalPart;
} __attribute__((packed));
```

Its wire form is:

```text
+0x00  u8       type = 0x52
+0x01  u16le    payloadLength       // nominally 6
+0x03  u32le    startIndex
+0x07  u8       isMultiPart
+0x08  u8       isFinalPart
```

The C struct starts at the length field and is eight bytes total. Thus its
nominal TLV payload is six bytes and the full TLV is nine bytes.

Both native architectures read `startIndex` at struct offset `+2`,
`isMultiPart` at `+6`, and `isFinalPart` at `+7`. Each flag is a separate
byte, not a bit within a shared flags word. Any nonzero byte becomes Kotlin
`true`; neither flag is constrained to 0 or 1.

Neither the parser nor `PPCollection_createAudioTimeline` checks that
`payloadLength == 6`. If the record is absent but an audio record is present,
the returned timeline defaults to:

```text
collectionStartIndex = 0
isMultiPart = false
isFinalPart = false
```

### `0x53` — button press sequence

The packed record is:

```text
+0x00  u8       type = 0x53
+0x01  u16le    payloadLength       // nominally 8
+0x03  u32le    sequence
+0x07  u32le    count
```

The imported C struct is ten bytes from the length field, so the full TLV is
nominally eleven bytes.

`PPCollection_buttonPressSequenceString` examines bits from least significant
to most significant for `count` iterations:

```text
bit 1 -> "long "
bit 0 -> "short "
```

The result retains a trailing space. There is no parser-level check that the
payload is eight bytes or that `count` is within the 32-bit sequence width.

### `0x54` — lifetime collection count

```text
+0x00  u8       type = 0x54
+0x01  u16le    payloadLength       // nominally 4
+0x03  u32le    count
```

The imported packed C struct is six bytes from the length field, so the full
TLV is nominally seven bytes. `PPCollection_lifetimeCollectionCount` returns
the `u32` at struct offset `+2`. This is a device lifetime collection counter;
the multipart code does not use it as a part count.

Again, the native parser does not enforce the nominal four-byte payload.

## Multipart index and flag semantics

### `startIndex` is the group origin

The Kotlin public constructor is `PPCollection(index: Int, data: ByteArray)`.
Its `index` property comes directly from the transfer event and is not read
from TLV `0x52`.

For multipart audio:

1. The first part creates `MultipartCollection(startIndex)` from
   `timeline.collectionStartIndex`, which came from `0x52`.
2. The individual part is added under `collection.index`, the externally
   supplied transfer index.
3. Subsequent parts compare their `0x52 startIndex` to the current group's
   original `startIndex`.
4. A mismatch flushes the current group and starts a new one using the new
   `0x52 startIndex`.

Therefore all parts in one logical multipart collection should repeat the
same `0x52 startIndex`; it is not incremented per part.

### Flags

- `isMultiPart != 0` chooses the multipart accumulation path.
- `isMultiPart == 0` treats the audio as a single-part collection. The
  single-part accumulator uses the external current index as its start.
- `isFinalPart != 0` causes the current multipart buffer to be emitted and
  clears the active group.
- There is no total-part count or final index in `0x52`.

The final flag is a completion signal, not proof that all intermediate parts
arrived.

### Contiguity behavior

`MultipartCollection` keeps the externally supplied part indices in a set.
Duplicate indices fail a Kotlin `check`.

For `N` unique received parts, `isContiguous()` requires the set to be exactly:

```text
startIndex .. startIndex + N - 1
```

When a final part arrives, the library still emits a nonempty completed audio
buffer if this check fails, but logs the gap and marks the emitted result
`isContiguous = false`. The `0x52` record itself does not supply enough
information to identify the expected total `N`.

Samples are appended as parts are processed; the contiguity set does not sort
or reorder sample buffers by index.

## Terminator, version, and magic audit

- **Terminator:** none. Type zero is invalid, and parsing stops only when the
  computed cursor reaches or passes the outer end pointer.
- **Envelope version:** none checked.
- **Magic:** no multi-byte magic is checked. `0xff`
  (`RECORDS_DATA_TRANSFER`) is a one-byte marker selecting the LE16 body-length
  form.
- **Four-byte header zero:** byte 3 is the high zero byte of an LE32 total
  length, not a terminator or version.
- **Checksum/CRC:** none in this parser.
- **Record-level version:** type `0x31` is named
  `STATIONARY_DATA_VERSION`, but it is an ordinary inner TLV and does not
  version the collection envelope.

## Architecture parity

The relevant independent instruction matches are:

| Behavior | Device ARM64 | Simulator x86_64 |
| --- | ---: | ---: |
| null/minimum/header checks | `0x48..0xe4` | `0x29..0xc5` |
| TLV type dispatch | `0x1a0..0x1c4` | `0x24e..0x26a` |
| common cursor advance | `0x414..0x424` | `0x4f8..0x505` |
| `0x50` `u32` length case | `0x3c8` | `0x4a7` |
| `0x51` `u32` length case | `0x3d8` | `0x4b7` |
| `0x52` `u16` length case | `0x3e8` | `0x4c7` |
| `0x53` `u16` length case | `0x3f8` | `0x4d8` |
| `0x54` `u16` length case | `0x408` | `0x4e9` |
| multipart reads at `+2/+6/+7` | `0x3f4..0x418` in `PPCollection` | `0x3b5..0x3d0` in `PPCollection` |

The ARM64 byte jump table and x86_64 signed-offset jump table also agree on
every accepted, invalid, and special type entry, including the explicit
`FULL_CLUB_SETTINGS`/`PPFail` path.
