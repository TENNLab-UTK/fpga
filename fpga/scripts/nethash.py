# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import pathlib as pl

import neuro

from fpga.network import hash_network

if __name__ == "__main__":
    args = argparse.ArgumentParser(prog="nethash", description="Get SHA256 of network.")
    args.add_argument("target", type=pl.Path, help="JSON network filepath")
    args = args.parse_args()

    net = neuro.Network()
    net.read_from_file(str(args.target))
    print(hash_network(net))
