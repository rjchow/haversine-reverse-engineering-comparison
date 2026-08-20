#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * Test harness for the exact DDRiceCompression.o shipped in the simulator
 * cinterop KLIB. The native structs are deliberately opaque; their sizes come
 * from the object code's initializers.
 */
typedef struct { uint8_t bytes[56]; } DDRiceCompressionEncoder;
typedef struct { uint8_t bytes[16]; } DDRiceCompressionChannel;
typedef struct { uint8_t bytes[24]; } DDRiceDecompressionDecoder;
typedef struct { uint8_t bytes[120]; } DDRiceDecompressionChannel;

extern int DDRiceCompressionChannel_init(DDRiceCompressionChannel *, uint8_t *);
extern void DDRiceCompressionEncoder_init(DDRiceCompressionEncoder *);
extern int DDRiceCompressionEncoder_attachOutputBuffer(
    DDRiceCompressionEncoder *, uint8_t *, uint64_t);
extern uint64_t DDRiceCompressionEncoder_detachOutputBuffer(
    DDRiceCompressionEncoder *);
extern int DDRiceCompressionChannel_encodeWord(
    DDRiceCompressionEncoder *, DDRiceCompressionChannel *, uint16_t);
extern int DDRiceCompressionEncoder_close(DDRiceCompressionEncoder *);
extern uint64_t DDRiceCompressionEncoder_compressedBitCount(
    DDRiceCompressionEncoder *);

extern void DDRiceDecompressionDecoder_init(
    DDRiceDecompressionDecoder *, const uint8_t *, uint64_t, uint64_t);
extern void DDRiceDecompressionChannel_init(
    DDRiceDecompressionChannel *, const uint8_t *, uint32_t, uint32_t);
extern int DDRiceDecompressionChannel_decodeDiff(
    DDRiceDecompressionChannel *, DDRiceDecompressionDecoder *, uint16_t *);
extern uint16_t DDRiceDecompressionChannel_nextWord(
    DDRiceDecompressionChannel *, uint16_t);

static const int16_t input_words[] = {
    0, 0, 1, 3, 6, 10, 9, 7, 4, 0, -5, -11, -18, -26,
    -35, -30, -20, -5, 15, 40, 70, 50, 20, -20, -70, 32767,
    -32768, 1234, -2345, 0
};

static int run_config(uint8_t config) {
    uint8_t encoded[4096] = {0};
    DDRiceCompressionEncoder encoder;
    DDRiceCompressionChannel enc_channel;
    DDRiceDecompressionDecoder decoder;
    DDRiceDecompressionChannel dec_channel;
    const size_t word_count = sizeof(input_words) / sizeof(input_words[0]);

    memset(&enc_channel, 0, sizeof(enc_channel));
    int error = DDRiceCompressionChannel_init(&enc_channel, &config);
    if (error != 0) {
        fprintf(stderr, "compression channel init failed: config=%02x error=%d\n",
                config, error);
        return 1;
    }
    DDRiceCompressionEncoder_init(&encoder);
    error = DDRiceCompressionEncoder_attachOutputBuffer(
        &encoder, encoded, sizeof(encoded));
    if (error != 0) {
        fprintf(stderr, "attach failed: error=%d\n", error);
        return 1;
    }
    for (size_t i = 0; i < word_count; ++i) {
        error = DDRiceCompressionChannel_encodeWord(
            &encoder, &enc_channel, (uint16_t)input_words[i]);
        if (error != 0) {
            fprintf(stderr, "encode failed: index=%zu error=%d\n", i, error);
            return 1;
        }
    }
    const uint64_t bit_count = DDRiceCompressionEncoder_compressedBitCount(&encoder);
    error = DDRiceCompressionEncoder_close(&encoder);
    if (error != 0) {
        fprintf(stderr, "close failed: error=%d\n", error);
        return 1;
    }
    const uint64_t byte_count = DDRiceCompressionEncoder_detachOutputBuffer(&encoder);

    printf("config=%02x bits=%" PRIu64 " bytes=%" PRIu64 " hex=",
           config, bit_count, byte_count);
    for (uint64_t i = 0; i < byte_count; ++i) {
        printf("%02x", encoded[i]);
    }
    putchar('\n');

    DDRiceDecompressionDecoder_init(&decoder, encoded, bit_count, 0);
    DDRiceDecompressionChannel_init(&dec_channel, &config, 0, 0);
    for (size_t i = 0; i < word_count; ++i) {
        uint16_t difference = 0;
        error = DDRiceDecompressionChannel_decodeDiff(
            &dec_channel, &decoder, &difference);
        if (error != 0) {
            fprintf(stderr, "decode failed: index=%zu error=%d\n", i, error);
            return 1;
        }
        const int16_t decoded = (int16_t)DDRiceDecompressionChannel_nextWord(
            &dec_channel, difference);
        printf("%d%s", decoded, i + 1 == word_count ? "\n" : ",");
    }
    uint16_t ignored = 0;
    error = DDRiceDecompressionChannel_decodeDiff(
        &dec_channel, &decoder, &ignored);
    if (error != 3) {
        fprintf(stderr, "expected end-of-bits error 3, got %d\n", error);
        return 1;
    }
    return 0;
}

static int run_decoder_edge_cases(void) {
    DDRiceDecompressionDecoder decoder;
    DDRiceDecompressionChannel channel;
    uint16_t difference = 0;

    /*
     * The encoder initializer rejects configs above 0xef, but the shipped
     * decoder has no corresponding check and supports a high-nibble cutoff of
     * 15. A single leading one is a complete zero-difference codeword.
     */
    const uint8_t high_cutoff_config = 0xf0;
    const uint8_t zero_codeword[] = {0x80};
    DDRiceDecompressionDecoder_init(&decoder, zero_codeword, 1, 0);
    DDRiceDecompressionChannel_init(
        &channel, &high_cutoff_config, 0, 0);
    int error = DDRiceDecompressionChannel_decodeDiff(
        &channel, &decoder, &difference);
    if (error != 0 || difference != 0 ||
        DDRiceDecompressionChannel_nextWord(&channel, difference) != 0) {
        fprintf(stderr,
                "decoder high-cutoff case failed: error=%d difference=%u\n",
                error, difference);
        return 1;
    }

    /*
     * PPCollection treats decoder status 3 as successful end-of-stream. The
     * decoder returns that same status when the declared bit limit ends after
     * a leading zero but before the rest of that codeword.
     */
    const uint8_t normal_config = 0x30;
    const uint8_t truncated_codeword[] = {0x00};
    difference = 0;
    DDRiceDecompressionDecoder_init(&decoder, truncated_codeword, 1, 0);
    DDRiceDecompressionChannel_init(&channel, &normal_config, 0, 0);
    error = DDRiceDecompressionChannel_decodeDiff(
        &channel, &decoder, &difference);
    if (error != 3) {
        fprintf(stderr, "expected mid-codeword status 3, got %d\n", error);
        return 1;
    }

    puts("decoder-edge-cases=PASS config=f0 mid-codeword-status=3");
    return 0;
}

int main(void) {
    static const uint8_t configs[] = {0x30, 0x40, 0x51, 0x72};
    for (size_t i = 0; i < sizeof(configs); ++i) {
        if (run_config(configs[i]) != 0) {
            return 1;
        }
    }
    return run_decoder_edge_cases();
}
