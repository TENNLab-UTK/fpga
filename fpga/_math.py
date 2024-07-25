# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from math import ceil, log2


def clog2(count: int) -> int:
    return int(ceil(log2(count)))


def width_bits_to_bytes(bits: int) -> int:
    return int(ceil(bits / 8))


def width_bytes_to_bits(bytes: int) -> int:
    return int(bytes * 8)


def width_nearest_byte(bits: int) -> int:
    return width_bytes_to_bits(width_bits_to_bytes(bits))


def width_is_byte_aligned(bits: int) -> bool:
    return bits % 8 == 0


def width_padding_to_byte(bits: int) -> int:
    return width_nearest_byte(bits) - bits


def uint_to_bool_list(value: int, width: int = 0) -> list[bool]:
    if not width:
        width = clog2(value + 1)
    if value >= 2 ** width:
        raise ValueError(f"Value {value} is too large for width {width}")
    return [bool(value & (1 << i)) for i in range(width - 1, -1, -1)]

def bool_list_to_uint(value: list[bool]) -> int:
    return sum([int(bool(value[i])) << (len(value) - i - 1) for i in range(len(value))])