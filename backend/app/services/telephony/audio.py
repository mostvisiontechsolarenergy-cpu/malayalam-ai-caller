import struct

_BIAS = 0x84
_CLIP = 32635


def mulaw_byte_to_pcm16(value: int) -> int:
    value = (~value) & 0xFF
    sample = ((value & 0x0F) << 3) + _BIAS
    sample <<= (value & 0x70) >> 4
    return _BIAS - sample if value & 0x80 else sample - _BIAS


def pcm16_to_mulaw_byte(sample: int) -> int:
    sign = 0x80 if sample < 0 else 0
    sample = min(abs(sample), _CLIP) + _BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not sample & mask:
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def mulaw_8khz_to_gemini_pcm_16khz(payload: bytes) -> bytes:
    samples = [mulaw_byte_to_pcm16(value) for value in payload]
    doubled: list[int] = []
    for index, sample in enumerate(samples):
        following = samples[index + 1] if index + 1 < len(samples) else sample
        doubled.extend((sample, (sample + following) // 2))
    return struct.pack(f"<{len(doubled)}h", *doubled) if doubled else b""


def gemini_pcm_24khz_to_mulaw_8khz(payload: bytes) -> bytes:
    usable = len(payload) - (len(payload) % 2)
    if not usable:
        return b""
    samples = struct.unpack(f"<{usable // 2}h", payload[:usable])
    downsampled = [
        sum(samples[index : index + 3]) // len(samples[index : index + 3])
        for index in range(0, len(samples), 3)
        if samples[index : index + 3]
    ]
    return bytes(pcm16_to_mulaw_byte(sample) for sample in downsampled)
