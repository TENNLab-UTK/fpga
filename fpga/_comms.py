# Copyright (c) 2025 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import time
from multiprocessing import Process, Value
from multiprocessing.shared_memory import SharedMemory
from queue import Empty

import psutil
from periphery import Serial

READ_SIZE = 1024


class SerialMill:
    def __init__(self, *args, **kwargs):
        size = kwargs.pop("size", psutil.virtual_memory().available // 2)
        if READ_SIZE > size:
            raise ValueError(
                f"Cannot have a buffer size ({size})"
                f" smaller than `READ_SIZE` ({READ_SIZE})"
            )
        self._super = (
            args[0] if isinstance(args[0], Serial) else Serial(*args, **kwargs)
        )
        self._shmem = SharedMemory(create=True, size=size)
        self._head = Value("Q", 0)
        self._tail = Value("Q", 0)
        self._reader = Process(target=self._read)
        self._reader.daemon = True
        self._reader.start()

    def read(self, length: int, timeout: float | None = None):
        # can be 0 here
        if timeout is not None:
            # will never be 0 after here (can use "not" to check if None)
            timeout += time.monotonic()

        old_tail = self._tail.value
        new_tail = old_tail + length
        imm_tail = min(new_tail, self.size * ((old_tail // self.size) + 1))

        while (self._head.value < new_tail) and (
            not timeout or time.monotonic() < timeout
        ):
            time.sleep(100e-9)

        ret = bytes(self._shmem.buf[old_tail % self.size : imm_tail % self.size])
        if new_tail - imm_tail:
            # wrap-around
            ret += bytes(self._shmem.buf[: new_tail % self.size])
        self._tail.value = new_tail

        return ret

    @property
    def size(self):
        return self._shmem.size

    def close(self):
        self._shmem.close()
        self._shmem.unlink()

    def _read(self):
        while True:
            rx = self._super.read(READ_SIZE, 0)
            if rx:
                old_head = self._head.value
                new_head = old_head + len(rx)
                if new_head - self._tail.value > self.size:
                    raise OverflowError()
                imm_head = min(new_head, self.size * ((old_head // self.size) + 1))
                self._shmem.buf[old_head % self.size : imm_head % self.size] = rx[
                    : (imm_head - old_head)
                ]
                if new_head - imm_head:
                    # wrap-around
                    self._shmem.buf[: new_head % self.size] = rx[
                        (imm_head - old_head) :
                    ]
                self._head.value = new_head

    def __getattr__(self, name):
        return getattr(self._super, name)
