You are investigating two compiled Kotlin/Native binaries used by the Pebble Index iOS app. Your job is to persistently reverse-engineer them and answer a very specific set of protocol questions with evidence.

Do not stop at surface-level strings, class names, or guesses. Follow call chains, inspect binary contents, decompile/disassemble relevant functions, compare both binaries, and keep narrowing hypotheses until you can give the strongest evidence-supported answer possible.

## Artifacts to investigate

Download these two Maven Central artifacts:

Physical iPhone / iOS ARM64:

`https://repo1.maven.org/maven2/io/github/coredevices/haversine/haversine-iosarm64/03202f5/haversine-iosarm64-03202f5.klib`

Apple Silicon iOS Simulator ARM64:

`https://repo1.maven.org/maven2/io/github/coredevices/haversine/haversine-iossimulatorarm64/03202f5/haversine-iossimulatorarm64-03202f5.klib`

The library is called **Haversine** and is published under:

`io.github.coredevices.haversine`

It is used by the Pebble/Core Devices mobile application to communicate with the **Pebble Index 01** BLE voice-recording ring.

## Primary question

Determine, as precisely as possible:

> What format are recordings in when they are transmitted by the Pebble Index ring?

Ignore the BLE Link Layer transport itself. I want to know the application/protocol payload that the Index actually sends to Haversine and what transformations Haversine performs before the Pebble app receives the recording.

Specifically determine:

1. What representation is used for audio **on the ring**, if the binaries reveal it.
2. What representation is sent **over the Haversine protocol**.
3. Whether the transmitted recording is:

   * raw PCM,
   * ADPCM,
   * Speex,
   * Opus,
   * another known audio codec,
   * delta encoded,
   * custom compressed,
   * encrypted,
   * or some combination.
4. The recording sample rate before the app resamples it.
5. Sample width, channel count, frame size, packet/frame layout, and byte order where determinable.
6. Whether audio is transferred incrementally in frames/chunks or as a complete stored object.
7. How Haversine reconstructs the final audio.
8. What integrity mechanisms exist:

   * CRC,
   * checksum,
   * sequence numbers,
   * hashes,
   * acknowledgements,
   * retransmission,
   * FEC,
   * etc.

## Cryptography question

This is equally important.

Determine whether recordings are **encrypted at rest on the Index** and/or **encrypted at the Haversine application layer during transfer**.

Do not confuse normal BLE link encryption with application-level encryption.

The distinctions are:

### BLE link encryption

Handled by BLE/CoreBluetooth and the ring's Bluetooth stack.

Conceptually:

`Haversine plaintext -> BLE encrypted link -> CoreBluetooth decrypts -> Haversine plaintext`

This does NOT count as Haversine/application-layer recording encryption.

### Application-level encryption

What I want you to look for is something like:

`stored/audio bytes -> AES/ChaCha/etc. using an Index-specific secret -> ciphertext -> Haversine transfer`

followed by:

`Haversine receives ciphertext -> decrypt(secret) -> audio decoder`

Determine whether anything like this exists.

Search for evidence of:

* AES
* AES-CCM outside BLE
* AES-GCM
* ChaCha20
* Poly1305
* Salsa20
* CTR
* CBC
* XTS
* HKDF
* HMAC
* SHA-256
* Curve25519
* X25519
* P-256
* ECDH
* key derivation
* nonce generation
* IV generation
* authentication tags
* key storage
* device secrets
* pairing secrets
* registration tokens
* symmetric keys

Do not conclude that something is encrypted merely because crypto-related functions exist somewhere in the binary. Trace whether they are actually in the recording-transfer path.

## Registration/shared-secret hypothesis

Test this hypothesis explicitly:

> During Index registration/pairing, the app and ring exchange or derive a persistent application-level shared secret, and recordings stored on the ring are encrypted using that secret. Haversine later decrypts transferred recordings using the secret.

Find evidence either supporting or disproving this.

Questions to answer:

1. Is any application-level secret generated during registration?
2. Is a secret received from the ring?
3. Is a public/private key exchange performed?
4. Is any persistent key stored by Haversine?
5. Where is that key stored?
6. How is the key indexed to a particular Index ring?
7. Does recording decoding reference that key?
8. Does removal/reset of pairing information invalidate the ability to decode old recordings?
9. Is Bluetooth bonding itself the only persistent cryptographic relationship?

If there is no application-level shared secret, say so clearly and explain the evidence.

## Known behavior from the open-source Pebble app

Use these facts as anchor points.

The open-source app eventually receives Haversine events similar to:

`TransferStatus.TransferComplete`

containing, among other metadata:

`ShortArray samples`

and:

`sampleRate`

The application then performs processing conceptually like:

`transferStatus.samples`

-> DC-bias removal

-> resampling from `transferStatus.sampleRate`

-> 16000 Hz

-> conversion of `ShortArray` samples to little-endian bytes

-> stored as raw mono PCM16

Therefore, by the time `TransferComplete` reaches the application, Haversine has already converted the ring's representation into signed 16-bit samples.

Your job is to work backward from that boundary.

Find the code path that creates `TransferComplete(samples, sampleRate, ...)`.

## Pairing behavior already observed

On iOS, the visible Pebble app pairing code roughly performs:

1. Connect to Index.
2. Find Haversine service:

`607B5C9B-3700-4E94-F44A-2DF900BCB0C3`

3. Find characteristic:

`DAAD3D52-237C-90A7-B54B-8854A134D801`

4. Write one byte:

`00`

with response.

5. Disconnect.

The visible app code does not appear to explicitly receive or save an application secret during this operation.

Do not assume that proves no secret exists inside Haversine. Investigate whether Haversine itself performs additional operations before, during, or after this visible write.

## Investigation strategy

Proceed systematically.

### Phase 1: unpack everything

Determine the exact structure of each `.klib`.

Try standard archive inspection first:

`file`
`unzip -l`
`zipinfo`
`tar`
`strings`

Extract every member.

Record:

* manifest files
* LLVM bitcode
* IR
* object files
* metadata
* symbol tables
* serialized Kotlin metadata
* resources
* linker options
* dependency manifests

Do this for both artifacts.

Compare the iOS ARM64 and simulator ARM64 contents.

Do not assume `.klib` means all useful implementation details are stripped.

### Phase 2: inventory symbols and strings

Search all extracted content for terms including:

`TransferComplete`
`TransferStarted`
`TransferInProgress`
`TransferFailed`
`IrrecoverableDataDetected`
`samples`
`sampleRate`
`audio`
`codec`
`decode`
`decoder`
`encode`
`frame`
`packet`
`collection`
`collectionIndex`
`chunk`
`PCM`
`ADPCM`
`IMA`
`Speex`
`Opus`
`CELT`
`SILK`
`delta`
`predictor`
`quant`
`bitstream`
`bitreader`
`bitwriter`
`compress`
`decompress`
`encrypt`
`decrypt`
`cipher`
`key`
`secret`
`nonce`
`IV`
`AES`
`ChaCha`
`HKDF`
`HMAC`
`SHA`
`CRC`
`checksum`
`sequence`
`ack`
`retransmit`
`Telesto`
`Haversine`
`Satellite`
`Transfer`
`Recording`

Also search for constants suggestive of sample rates:

`8000`
`16000`
`24000`
`32000`
`44100`
`48000`

Search both decimal representations and binary constants where practical.

### Phase 3: locate TransferComplete creation

This is a priority.

Find the implementation or equivalent symbol corresponding to:

`TransferStatus.TransferComplete`

Then answer:

* Where is its `samples` field populated?
* What function produces the `ShortArray`?
* What input type feeds that function?
* Where did those bytes come from?
* Is the sample rate encoded in the transferred data, inferred from a transfer type, or hardcoded?

Follow this call chain backward as far as possible:

`TransferComplete.samples`

<- audio decoder

<- collection parser

<- Haversine packet/frame reconstruction

<- characteristic notification/read payload

Produce the call chain with function names and offsets/symbols.

### Phase 4: identify the audio codec

Once you find the byte-to-`ShortArray` transformation, characterize it precisely.

Look for:

* bit widths
* predictor state
* step-size tables
* delta reconstruction
* lookup tables
* fixed block sizes
* LPC coefficients
* entropy coding
* frame headers
* sync words
* known codec magic
* third-party codec functions

If it uses a known codec, prove it through implementation details, imported symbols, constants, or algorithm structure.

For example, do not merely say "looks like ADPCM." Show things such as:

* 4-bit nibbles
* predictor update
* IMA step table
* index table

or whatever the actual evidence is.

If it uses Speex, find the actual decoder call path and parameters.

If it is custom, reconstruct the algorithm enough to describe the input and output mathematically or in pseudocode.

### Phase 5: reconstruct framing

Identify how recordings are represented before decoding.

For each frame/chunk, attempt to determine:

* header size
* magic/version
* recording/collection identifier
* frame type
* sequence number
* payload length
* timestamp
* codec indicator
* sample-rate indicator
* flags
* CRC/checksum
* terminator
* acknowledgement behavior

If data passes through multiple protocol layers, distinguish them.

For example:

`BLE characteristic payload`

-> `Haversine transport frame`

-> `collection fragment`

-> `audio frame`

Do not collapse these into one structure.

### Phase 6: cryptographic analysis

Search for cryptographic libraries, imports, algorithms, constants, and call paths.

For every potential crypto implementation, establish:

1. What function calls it?
2. What data goes into it?
3. What key goes into it?
4. Where does the key come from?
5. Is it related to recording transfer?
6. Is it merely a checksum/hash?
7. Is it platform BLE security machinery rather than application crypto?

A crypto function only matters if it is actually reachable from the recording transfer path.

### Phase 7: investigate persistent state

Look for anything that stores per-ring data such as:

* key
* identity
* token
* UUID
* secret
* nonce base
* registration data
* bond-related state

Find persistence mechanisms.

On iOS this could potentially involve:

* NSUserDefaults
* Keychain
* files
* SQLite
* Kotlin settings/preferences abstraction
* platform-native APIs

Determine whether Haversine itself stores any secret.

If possible, identify persistence keys/string names.

### Phase 8: compare simulator and device binaries

Use one binary to illuminate the other.

The simulator binary may preserve symbols or structures differently.

Diff:

* strings
* exported symbols
* metadata
* LLVM IR/bitcode
* function names
* dependency references

If the same protocol implementation exists in both, use whichever is easier to understand but verify important conclusions against the other.

## Useful tools

Use whatever is available, including:

* `file`
* `strings`
* `nm`
* `otool`
* `llvm-nm`
* `llvm-objdump`
* `llvm-dis`
* `llvm-bcanalyzer`
* `objdump`
* `readelf` where relevant
* Kotlin/Native tooling
* `klib` utility from Kotlin/Native
* Ghidra
* Hopper
* IDA
* Binary Ninja
* radare2 / rizin
* Python scripts
* hex editors
* recursive grep
* archive utilities

If a tool fails, try another route rather than stopping.

If the `.klib` contains LLVM bitcode, prioritize recovering and inspecting that before relying entirely on machine-code disassembly.

If Kotlin metadata exposes class/function structure, use it to label the native disassembly.

## Persistence requirement

You are expected to be persistent.

Do not stop after statements such as:

* "the source isn't available"
* "the binary is stripped"
* "Kotlin/Native is difficult to decompile"
* "I found no obvious strings"
* "it probably uses BLE encryption"

If one approach fails:

1. inspect archive structure,
2. inspect metadata,
3. inspect symbols,
4. inspect strings,
5. inspect bitcode,
6. inspect native objects,
7. inspect dependencies,
8. compare architectures,
9. write small parsers/scripts,
10. trace calls manually.

Continue until you have exhausted realistic approaches.

## Avoid these reasoning mistakes

Do not infer:

* encryption from BLE bonding,
* encryption from the presence of AES strings,
* a codec solely from a dependency name,
* sample rate solely from the app's final 16 kHz output,
* ring storage format from the app's post-transfer PCM representation,
* multi-layer packet boundaries from BLE notification sizes.

Clearly distinguish:

**known**

directly evidenced in binary/code.

**strong inference**

multiple pieces of evidence support it.

**speculation**

plausible but not established.

## Desired final output

Produce a technical report with the following sections.

### 1. Executive answer

In a few paragraphs, answer:

* What does the Index store?
* What does it transmit?
* What does Haversine receive?
* What does Haversine output to the app?
* Is recording data encrypted at rest?
* Is it application-layer encrypted in transit?
* Is there a registration-derived shared secret?

Use `unknown` where genuinely unresolved.

### 2. End-to-end data path

Give a pipeline like:

`microphone`

-> `[ring codec/storage format]`

-> `[Haversine recording representation]`

-> `[framing]`

-> `[optional encryption]`

-> `BLE characteristic`

-> `Haversine parser`

-> `[decoder]`

-> `ShortArray PCM`

-> Pebble application

Include sample rates and formats at each known point.

### 3. Codec analysis

State the codec/encoding and provide the evidence.

If custom, provide pseudocode sufficient to implement a decoder if possible.

### 4. Frame/protocol structure

Document byte structures in tables such as:

| Offset | Size | Meaning  |
| -----: | ---: | -------- |
|      0 |    1 | type     |
|      1 |    2 | sequence |
|    ... |  ... | ...      |

Only include fields supported by evidence.

### 5. Cryptography analysis

Explicitly separate:

* BLE link encryption
* Haversine/application-layer encryption
* storage-at-rest encryption

For each, state:

`yes / no / unknown`

and why.

### 6. Key-management analysis

Answer:

* Is there a per-ring shared secret?
* How is it created?
* Where is it stored?
* How is it used?
* Does registration exchange it?
* Does recording decoding depend on it?

### 7. Relevant symbols/functions

List important symbols, function names, classes, offsets, or recovered pseudocode.

Especially identify the chain leading to:

`TransferStatus.TransferComplete(samples, sampleRate, ...)`

### 8. Evidence

For every major conclusion, cite concrete evidence such as:

* binary filename
* archive member
* symbol
* string
* function
* disassembly offset
* relevant pseudocode
* metadata entry

Do not make major claims without showing where they came from.

### 9. Remaining unknowns

List anything that could not be determined and exactly what additional artifact would resolve it, such as:

* ring firmware
* Haversine source
* captured GATT traffic
* an actual transferred recording
* app binary
* debug symbols

### 10. Independent-client implications

Conclude with what would be necessary to implement a completely independent iOS client that:

1. discovers an Index,
2. connects to it,
3. authenticates/pairs,
4. enumerates recordings,
5. downloads one,
6. decodes it to PCM,
7. acknowledges/deletes it safely.

Explicitly identify which parts are already understood and which still require reverse engineering.

## Standard of proof

The target is not merely a plausible description.

The target is an answer strong enough that another engineer could begin implementing an independent Index client from your report without Haversine.

When uncertain, continue tracing rather than filling gaps with assumptions.
