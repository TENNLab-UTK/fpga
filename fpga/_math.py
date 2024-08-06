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


def width_padding_to_byte(bits: int) -> int:
    return width_nearest_byte(bits) - bits


def unsigned_to_bools(value: int, width: int = 0) -> list[bool]:
    if not width:
        width = clog2(value + 1)
    if value >= 2**width:
        raise ValueError(f"Value of {value} is too large for width {width}")
    elif value < 0:
        raise ValueError(f"Value of {value} is negative")
    return signed_to_bools(value, width + 1)[1:]


def bools_to_unsigned(value: list[bool]) -> int:
    return bools_to_signed([False] + value)


def signed_to_bools(value: int, width: int = 0) -> list[bool]:
    if not width:
        width = clog2(value + 1) + 1
    if value >= 2 ** (width - 1) or value < -(2 ** (width - 1)):
        raise ValueError(f"Absolute value of {value} is too large for width {width}")
    return [value < 0] + [bool(value & (1 << i)) for i in range(width - 2, -1, -1)]


def bools_to_signed(value: list[bool]) -> int:
    return sum(
        [int(bool(value[i])) << (len(value) - i - 1) for i in range(1, len(value))]
    ) - (value[0] * 2 ** (len(value) - 1))