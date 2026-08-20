#!/usr/bin/env python3
"""Decode an Index/Haversine collection's audio without Haversine.

This implementation is derived from the exact 03202f5 PPCommon native objects.
It intentionally models the native parser's audio-record selection rule:
the last uncompressed (0x50) record wins; otherwise the last compressed (0x51)
record wins.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


UNCOMPRESSED_16BIT_AUDIO = 0x50
COMPRESSED_16BIT_AUDIO = 0x51
COLLECTION_MULTI_PART_INFO = 0x52
BUTTON_PRESS_SEQUENCE = 0x53
LIFETIME_COLLECTION_COUNT = 0x54

# GSParseRecordsInRawData recognizes these record codes. Code 0x23 is a
# parser-control/sentinel case in the native switch and is not a normal TLV.
KNOWN_TLV_TYPES = (
    set(range(0x01, 0x13))
    | set(range(0x21, 0x2A))
    | set(range(0x30, 0x36))
    | set(range(0x50, 0x55))
)
LENGTH32_TLV_TYPES = {UNCOMPRESSED_16BIT_AUDIO, COMPRESSED_16BIT_AUDIO}


class DecodeError(ValueError):
    """Malformed or unsupported collection data."""


@dataclass(frozen=True)
class Record:
    type: int
    offset: int
    length_size: int
    payload: bytes


@dataclass(frozen=True)
class MultipartInfo:
    start_index: int
    is_multipart: bool
    is_final_part: bool


@dataclass(frozen=True)
class DecodedAudio:
    sample_rate_hz: int
    samples: tuple[int, ...]
    record_type: int
    codec: str
    config: int | None
    compressed_bit_count: int | None
    multipart: MultipartInfo | None
    button_sequence: str | None
    lifetime_collection_count: int | None
    outer_header: str


class BitReader:
    """MSB-first bounded bit reader, matching DDRiceDecompressionDecoder."""

    def __init__(self, data: bytes, bit_count: int) -> None:
        if bit_count < 0 or bit_count > len(data) * 8:
            raise DecodeError(
                f"bit count {bit_count} exceeds {len(data)} available bytes"
            )
        self._data = data
        self._bit_count = bit_count
        self._position = 0

    @property
    def remaining(self) -> int:
        return self._bit_count - self._position

    def read_bit(self) -> int:
        if self._position >= self._bit_count:
            raise EOFError
        byte = self._data[self._position >> 3]
        bit = (byte >> (7 - (self._position & 7))) & 1
        self._position += 1
        return bit

    def read_bits(self, count: int) -> int:
        value = 0
        for _ in range(count):
            value = (value << 1) | self.read_bit()
        return value


def _signed16(bits: int) -> int:
    bits &= 0xFFFF
    return bits if bits < 0x8000 else bits - 0x10000


def decode_ddrice(data: bytes, bit_count: int, config: int) -> tuple[int, ...]:
    """Decode the exact one-channel DD-Rice bitstream used by PPCommon.

    config[3:0] is the output left shift; config[7:4] is the unary cutoff.
    Predictor state starts at sample=0 and firstDifference=0 for every record.
    """

    shift = config & 0x0F
    unary_limit = config >> 4
    # The shipped encoder initializer limits canonical emitted configs to
    # <= 0xef. The collection decompressor does not repeat that validation and
    # mechanically supports unary_limit == 15, so accept all byte values here.

    reader = BitReader(data, bit_count)
    modulus = 1 << (16 - shift)
    sign_threshold = modulus >> 1
    first_difference = 0
    sample = 0
    output: list[int] = []

    while reader.remaining:
        try:
            first = reader.read_bit()
            if first == 1:
                encoded_difference = 0
            else:
                # The first zero has already been consumed.
                zero_count = 1
                terminator = 0
                while zero_count < unary_limit:
                    zero_count += 1
                    terminator = reader.read_bit()
                    if terminator:
                        break

                if terminator == 0:
                    # unary_limit zero bits (one zero minimum in the decoder),
                    # then a literal modular difference.
                    encoded_difference = reader.read_bits(16 - shift)
                else:
                    magnitude = zero_count - 1
                    sign = reader.read_bit()
                    encoded_difference = (
                        magnitude if sign == 0 else modulus - magnitude
                    )
        except EOFError as exc:
            raise DecodeError("truncated DD-Rice codeword at declared bit limit") from exc

        signed_difference = (
            encoded_difference
            if encoded_difference < sign_threshold
            else encoded_difference - modulus
        )
        first_difference = (first_difference + signed_difference) & 0xFFFF
        sample = (sample + first_difference) & 0xFFFF
        output.append(_signed16((sample << shift) & 0xFFFF))

    return tuple(output)


def parse_records(data: bytes) -> tuple[str, list[Record]]:
    """Parse the three collection-envelope forms and their TLV records."""

    size = len(data)
    if size < 3:
        raise DecodeError("collection is shorter than its minimum 3-byte header")

    if size >= 4 and data[3] == 0:
        declared = int.from_bytes(data[0:4], "little")
        if declared != size:
            raise DecodeError(
                f"legacy u32le total length says {declared}, received {size}"
            )
        cursor = 4
        outer_header = "u32le-total-length"
    else:
        if data[0] == 0xFF:
            declared = int.from_bytes(data[1:3], "little")
            outer_header = "ff-u16le-payload-length"
        else:
            declared = int.from_bytes(data[0:3], "big")
            outer_header = "u24be-payload-length"
        if declared != size - 3:
            raise DecodeError(
                f"3-byte header says {declared} payload bytes, received {size - 3}"
            )
        cursor = 3

    records: list[Record] = []
    while cursor < size:
        record_offset = cursor
        record_type = data[cursor]
        cursor += 1
        if record_type == 0x23:
            raise DecodeError("record code 0x23 is a native parser sentinel")
        if record_type not in KNOWN_TLV_TYPES:
            raise DecodeError(f"unknown record type 0x{record_type:02x}")

        length_size = 4 if record_type in LENGTH32_TLV_TYPES else 2
        if cursor + length_size > size:
            raise DecodeError(
                f"record 0x{record_type:02x} at {record_offset} has no full length"
            )
        payload_length = int.from_bytes(
            data[cursor : cursor + length_size], "little"
        )
        cursor += length_size
        payload_end = cursor + payload_length
        if payload_end > size:
            raise DecodeError(
                f"record 0x{record_type:02x} at {record_offset} overruns collection: "
                f"needs {payload_end}, size is {size}"
            )
        records.append(
            Record(
                type=record_type,
                offset=record_offset,
                length_size=length_size,
                payload=data[cursor:payload_end],
            )
        )
        cursor = payload_end

    return outer_header, records


def _parse_multipart(records: Iterable[Record]) -> MultipartInfo | None:
    selected = None
    for record in records:
        if record.type == COLLECTION_MULTI_PART_INFO:
            selected = record
    if selected is None:
        return None
    if len(selected.payload) < 6:
        raise DecodeError("multipart-info payload is shorter than 6 bytes")
    return MultipartInfo(
        start_index=int.from_bytes(selected.payload[0:4], "little"),
        is_multipart=selected.payload[4] != 0,
        is_final_part=selected.payload[5] != 0,
    )


def _parse_button_sequence(records: Iterable[Record]) -> str | None:
    selected = None
    for record in records:
        if record.type == BUTTON_PRESS_SEQUENCE:
            selected = record
    if selected is None:
        return None
    if len(selected.payload) < 8:
        raise DecodeError("button-sequence payload is shorter than 8 bytes")
    sequence = int.from_bytes(selected.payload[0:4], "little")
    count = int.from_bytes(selected.payload[4:8], "little")
    if count > 32:
        raise DecodeError(f"button-sequence count {count} exceeds its 32-bit word")
    # Exact PPCommon order and spelling, excluding its incidental trailing space.
    return " ".join(
        "long" if ((sequence >> bit) & 1) else "short"
        for bit in range(count)
    )


def _parse_lifetime_count(records: Iterable[Record]) -> int | None:
    selected = None
    for record in records:
        if record.type == LIFETIME_COLLECTION_COUNT:
            selected = record
    if selected is None:
        return None
    if len(selected.payload) < 4:
        raise DecodeError("lifetime-count payload is shorter than 4 bytes")
    return int.from_bytes(selected.payload[0:4], "little")


def decode_collection(data: bytes) -> DecodedAudio:
    outer_header, records = parse_records(data)
    uncompressed = [r for r in records if r.type == UNCOMPRESSED_16BIT_AUDIO]
    compressed = [r for r in records if r.type == COMPRESSED_16BIT_AUDIO]
    multipart = _parse_multipart(records)
    button_sequence = _parse_button_sequence(records)
    lifetime_count = _parse_lifetime_count(records)

    # Exact native priority: an uncompressed pointer is checked first, even if a
    # compressed pointer is also present. Each parser slot retains the last TLV.
    if uncompressed:
        selected = uncompressed[-1]
        if len(selected.payload) < 4:
            raise DecodeError("uncompressed audio payload is shorter than 4 bytes")
        sample_rate = int.from_bytes(selected.payload[0:4], "little")
        sample_bytes = selected.payload[4:]
        if len(sample_bytes) & 1:
            raise DecodeError("uncompressed PCM16 payload has an odd byte count")
        samples = tuple(
            value[0] for value in struct.iter_unpack("<h", sample_bytes)
        )
        return DecodedAudio(
            sample_rate_hz=sample_rate,
            samples=samples,
            record_type=selected.type,
            codec="pcm_s16le",
            config=None,
            compressed_bit_count=None,
            multipart=multipart,
            button_sequence=button_sequence,
            lifetime_collection_count=lifetime_count,
            outer_header=outer_header,
        )

    if compressed:
        selected = compressed[-1]
        if len(selected.payload) < 9:
            raise DecodeError("compressed audio payload is shorter than 9 bytes")
        config = selected.payload[0]
        bit_count = int.from_bytes(selected.payload[1:5], "little")
        sample_rate = int.from_bytes(selected.payload[5:9], "little")
        bitstream = selected.payload[9:]
        if bit_count > len(bitstream) * 8:
            raise DecodeError(
                f"compressed bit count {bit_count} exceeds {len(bitstream)} bytes"
            )
        return DecodedAudio(
            sample_rate_hz=sample_rate,
            samples=decode_ddrice(bitstream, bit_count, config),
            record_type=selected.type,
            codec="custom_ddrice_second_difference",
            config=config,
            compressed_bit_count=bit_count,
            multipart=multipart,
            button_sequence=button_sequence,
            lifetime_collection_count=lifetime_count,
            outer_header=outer_header,
        )

    raise DecodeError("collection has neither audio record 0x50 nor 0x51")


def pcm16le(samples: Sequence[int]) -> bytes:
    return b"".join(struct.pack("<h", sample) for sample in samples)


def write_wav(path: Path, audio: DecodedAudio) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(audio.sample_rate_hz)
        output.writeframes(pcm16le(audio.samples))


def _metadata(audio: DecodedAudio) -> dict[str, object]:
    result: dict[str, object] = {
        "sample_rate_hz": audio.sample_rate_hz,
        "sample_count": len(audio.samples),
        "channels": 1,
        "sample_format": "signed 16-bit PCM",
        "byte_order": "little-endian when serialized",
        "record_type": f"0x{audio.record_type:02x}",
        "codec": audio.codec,
        "ddrice_config": (
            None if audio.config is None else f"0x{audio.config:02x}"
        ),
        "compressed_bit_count": audio.compressed_bit_count,
        "button_sequence": audio.button_sequence,
        "lifetime_collection_count": audio.lifetime_collection_count,
        "outer_header": audio.outer_header,
        "multipart": (
            None if audio.multipart is None else asdict(audio.multipart)
        ),
    }
    return result


def self_test() -> None:
    """Check against bitstreams emitted by the exact ARM64 native encoder."""

    input_words = (
        0, 0, 1, 3, 6, 10, 9, 7, 4, 0, -5, -11, -18, -26,
        -35, -30, -20, -5, 15, 40, 70, 50, 20, -20, -70, 32767,
        -32768, 1234, -2345, 0,
    )
    vectors = (
        (
            0x30,
            342,
            "d2487ffdb6db6d8000e0000a000140002800050000a3ff387ffb0fff61ffec201dc3fde084d10da6605c90",
            input_words,
        ),
        (
            0x40,
            358,
            "d2483ffedb6db6c0003800014000140001400014000143ff383ffd83ffd83ffd8201dc1fef0213441b4cc05c90",
            input_words,
        ),
        (
            0x51,
            262,
            "d3299a734e0000c2209081ff9c1ffec1ffec1ffec100ec0ff7c109a00da6802e44",
            (
                0, 0, 2, 2, 6, 10, 10, 6, 4, 0, -4, -12, -18, -26,
                -34, -30, -20, -6, 16, 40, 70, 50, 20, -20, -70,
                32766, -32768, 1234, -2344, 0,
            ),
        ),
        (
            0x72,
            188,
            "eaf7b4682944807fe4c660201c00ff90084c40369e005c80",
            (
                0, 0, 0, 4, 8, 8, 8, 8, 4, 0, -4, -12, -16, -28,
                -36, -28, -20, -4, 12, 40, 72, 48, 20, -20, -68,
                32764, -32764, 1232, -2344, 0,
            ),
        ),
    )
    for config, bits, encoded_hex, expected in vectors:
        actual = decode_ddrice(bytes.fromhex(encoded_hex), bits, config)
        if actual != expected:
            raise AssertionError(
                f"native vector mismatch for config 0x{config:02x}:\n"
                f"expected={expected}\nactual={actual}"
            )
    print(f"PASS: {len(vectors)} exact-native vectors")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collection", nargs="?", type=Path)
    parser.add_argument("--pcm", type=Path, help="write raw mono PCM16LE")
    parser.add_argument("--wav", type=Path, help="write a mono WAV")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="validate against exact native-encoder bitstreams",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        if args.collection is None:
            return 0
    if args.collection is None:
        parser.error("collection is required unless --self-test is used")

    try:
        audio = decode_collection(args.collection.read_bytes())
        if args.pcm:
            args.pcm.write_bytes(pcm16le(audio.samples))
        if args.wav:
            write_wav(args.wav, audio)
        print(json.dumps(_metadata(audio), indent=2, sort_keys=True))
        return 0
    except (DecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
