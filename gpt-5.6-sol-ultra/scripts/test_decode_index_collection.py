#!/usr/bin/env python3

import struct
import unittest

from decode_index_collection import (
    DecodeError,
    decode_ddrice,
    decode_collection,
    parse_records,
    self_test,
)


def u24be_collection(records: bytes) -> bytes:
    return len(records).to_bytes(3, "big") + records


def ff_u16le_collection(records: bytes) -> bytes:
    return b"\xff" + len(records).to_bytes(2, "little") + records


def u32le_collection(records: bytes) -> bytes:
    total = len(records) + 4
    if total >= 1 << 24:
        raise ValueError("test envelope requires a zero high byte")
    return total.to_bytes(4, "little") + records


def tlv16(record_type: int, payload: bytes) -> bytes:
    return bytes([record_type]) + len(payload).to_bytes(2, "little") + payload


def tlv32(record_type: int, payload: bytes) -> bytes:
    return bytes([record_type]) + len(payload).to_bytes(4, "little") + payload


class CollectionDecoderTests(unittest.TestCase):
    def test_native_vectors(self) -> None:
        self_test()

    def test_decoder_accepts_encoder_noncanonical_high_cutoff(self) -> None:
        # The shipped encoder rejects configs above 0xef, but its decoder
        # accepts high-nibble 0xf. A one-bit zero-difference codeword is enough
        # to exercise the decoder-side distinction.
        self.assertEqual(decode_ddrice(b"\x80", 1, 0xF0), (0,))

    def test_uncompressed_and_multipart(self) -> None:
        multipart = tlv16(0x52, struct.pack("<IBB", 123, 1, 0))
        button_sequence = tlv16(0x53, struct.pack("<II", 0b101, 3))
        lifetime_count = tlv16(0x54, struct.pack("<I", 456))
        audio = tlv32(0x50, struct.pack("<Ihhh", 24_000, -32768, 0, 32767))
        decoded = decode_collection(
            u24be_collection(
                multipart + button_sequence + lifetime_count + audio
            )
        )
        self.assertEqual(decoded.sample_rate_hz, 24_000)
        self.assertEqual(decoded.samples, (-32768, 0, 32767))
        self.assertEqual(decoded.multipart.start_index, 123)
        self.assertTrue(decoded.multipart.is_multipart)
        self.assertFalse(decoded.multipart.is_final_part)
        self.assertEqual(decoded.button_sequence, "long short long")
        self.assertEqual(decoded.lifetime_collection_count, 456)

    def test_all_outer_headers(self) -> None:
        record = tlv16(0x01, b"x")
        for envelope, expected in (
            (u24be_collection, "u24be-payload-length"),
            (ff_u16le_collection, "ff-u16le-payload-length"),
            (u32le_collection, "u32le-total-length"),
        ):
            header, records = parse_records(envelope(record))
            self.assertEqual(header, expected)
            self.assertEqual(records[0].payload, b"x")

    def test_length_overrun_rejected(self) -> None:
        malformed = u24be_collection(b"\x50" + (99).to_bytes(4, "little"))
        with self.assertRaises(DecodeError):
            parse_records(malformed)


if __name__ == "__main__":
    unittest.main()
