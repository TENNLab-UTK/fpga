# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import pathlib as pl
from concurrent.futures import ProcessPoolExecutor as PoolExecutor
from concurrent.futures import wait

from fpga.network import convert_file_sv


def main():
    parser = argparse.ArgumentParser(prog="nethdl", description="Network HDL Generator")
    parser.add_argument(
        "target", type=pl.Path, help="JSON network file or directory path"
    )
    parser.add_argument(
        "-o",
        dest="output",
        type=pl.Path,
        help="SystemVerilog file or directory path",
    )
    modname_arg = parser.add_mutually_exclusive_group()
    modname_arg.add_argument(
        "--mod-abstract",
        dest="module_naming",
        action="store_const",
        default="bare",
        const="bare",
        help='Bare abstract module name (default "network")',
    )
    modname_arg.add_argument(
        "--mod-filename",
        dest="module_naming",
        action="store_const",
        const="filename",
        help="Module name reflects HDL filename (aids heterogeneity)",
    )
    modname_arg.add_argument(
        "--mod-nethash",
        dest="module_naming",
        action="store_const",
        const="hash",
        help="Module name uses hash of network contents (most change-sensitive)",
    )
    args = parser.parse_args()

    if args.target.is_file():
        assert args.target.suffix == ".json" or args.target.suffix == ".txt"
        inp_files = [args.target]
        inp_root = args.target.parent
    else:
        inp_root = args.target
        inp_files = list(inp_root.rglob("*.json")) + list(inp_root.rglob("*.txt"))

    singleton_out = False
    if args.output:
        if args.output.suffix == "":
            out_root = args.output
        elif args.output.suffix == ".sv" and args.target.is_file():
            out_root = args.output.parent
            singleton_out = True
        else:
            raise RuntimeError(
                "Output must be a directory name or SystemVerilog filename: "
                f'"{args.output}".'
            )
    else:
        out_root = inp_root

    with PoolExecutor() as executor:
        futures = {}
        for inpf in inp_files:
            if singleton_out:
                outf = args.output
            else:
                outf = out_root.joinpath(inpf.relative_to(inp_root)).with_suffix(".sv")
                outf.parent.mkdir(parents=True, exist_ok=True)
            futures[str(inpf.relative_to(inp_root).with_suffix(""))] = executor.submit(
                convert_file_sv, str(inpf), str(outf), args.module_naming
            )
        wait(futures.values())


if __name__ == "__main__":
    main()
