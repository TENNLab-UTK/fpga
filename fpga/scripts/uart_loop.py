# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import os
import pathlib as pl
import random
import sys
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
from importlib import resources
from json import dump, load

from edalize.edatool import get_edatool
from periphery import Serial
from tqdm import tqdm

import fpga

RATES = [
    # rates slower than 115200 are of no interest and not supported
    115200,
    230400,
    460800,
    500000,
    576000,
    921600,
    1000000,
    1152000,
    1500000,
    2000000,
    2500000,
    3000000,
    3500000,
    4000000,
]


def main():
    parser = argparse.ArgumentParser(
        prog="uart-loop", description="UART Loopback Baud Rate Test"
    )
    parser.add_argument("target", type=str, help="Target device name (e.g. 'basys3')")
    parser.add_argument(
        "dev", type=pl.Path, help="cdev path for UART (e.g. '/dev/ttyS1')"
    )
    parser.add_argument(
        "-j",
        dest="jobs",
        type=int,
        default=4,
        help="Number of parallel jobs to run (defaults to 4)",
    )
    parser.add_argument(
        "-n",
        dest="num_bytes",
        type=int,
        default=1048576,
        help="Number of bytes to test at each baud rate (defaults to 1MiB)",
    )
    parser.add_argument(
        "-c",
        dest="chunk_size",
        type=int,
        default=4096,
        help="Number of bytes per chunk to send over UART (defaults to 4KiB)",
    )
    parser.add_argument(
        "-s",
        dest="seed",
        type=int,
        default=random.randint(0, 2**32 - 1),
        help="Random seed for test data generation",
    )
    args = parser.parse_args()

    random.seed(args.seed)

    config_fname = resources.files(fpga.config).joinpath("targets.json")
    with open(config_fname) as f:
        target_config = load(f)[args.target]

    proj_path_parent = fpga.eda_build_path / args.target / "uart" / "loop"

    rtl_path = ".." / pl.Path(
        os.path.relpath(
            (pl.Path(resources.files(fpga.rtl))).resolve(),
            start=proj_path_parent.resolve(),
        )
    )
    config_path = ".." / pl.Path(
        os.path.relpath(
            (pl.Path(resources.files(fpga.config))).resolve(),
            start=proj_path_parent.resolve(),
        )
    )

    files = []
    files.extend(
        [
            {
                "name": str(rtl_path / f"{module}.v"),
                "file_type": "verilogSource",
            }
            for module in [
                "axis_adapter",
                "axis_uart",
            ]
        ]
    )
    files.extend(
        [
            {
                "name": str(rtl_path / f"{module}.sv"),
                "file_type": "systemVerilogSource",
            }
            for module in [
                "axis_loop_proc",
                "uart_processor",
            ]
        ]
    )

    tool_options = target_config["tools"]
    tool = target_config["default_tool"]
    tool_options[tool]["include_dirs"] = [str(rtl_path)]

    if tool == "vivado":
        tool_options["vivado"]["source_mgmt_mode"] = "All"
        files.extend(
            [
                {
                    "name": str(
                        config_path / f"{args.target}" / "uart_processor_top.v"
                    ),
                    "file_type": "verilogSource",
                },
                {
                    "name": str(config_path / f"{args.target}" / f"{args.target}.xdc"),
                    "file_type": "xdc",
                },
            ]
        )

    def build_eda(rate: int):
        proj_path = proj_path_parent / f"{rate :07d}"
        proj_path.mkdir(parents=True, exist_ok=True)
        print(
            f"Compiling baudrate: {rate : >7} Log: {proj_path.absolute() / 'build.log'}"
        )
        parameters = {
            "CLK_FREQ": {
                "datatype": "str",
                "default": f"{target_config['parameters']['clk_freq']}",
                "paramtype": "vlogparam",
            },
            "BAUD_RATE": {
                "datatype": "str",
                "default": f"{rate}",
                "paramtype": "vlogparam",
            },
        }
        edam = {
            "files": files,
            "name": "uart_loop",
            "parameters": parameters,
            "toplevel": "uart_top",
            "tool_options": tool_options,
        }
        backend = get_edatool(tool)(edam=edam, work_root=proj_path, verbose=False)
        with open(proj_path / "build.log", "w", buffering=1) as log:
            backend.stdout = log
            backend.stderr = log
            backend.configure()
            # https://github.com/olofk/edalize/issues/423
            if tool == "vivado":
                (proj_path / pl.Path(f"{edam['name']}_synth.tcl")).resolve().touch()
            backend.build()
        print(
            f"Completed baudrate: {rate : >7} Log: {proj_path.absolute() / 'build.log'}"
        )
        return backend

    futures = {}
    throughputs = dict()
    with PoolExecutor(max_workers=args.jobs) as executor:
        for rate in RATES:
            futures[rate] = executor.submit(
                build_eda,
                rate,
            )

        for rate in RATES:
            backend = futures[rate].result()
            backend.stdout = sys.stdout
            backend.stderr = sys.stderr
            print(
                f"TESTING BAUD RATE {rate}".center(os.get_terminal_size().columns, "=")
            )
            print("PROGRAMMING START".center(os.get_terminal_size().columns, "-"))
            backend.run()
            print("PROGRAMMING END".center(os.get_terminal_size().columns, "-"))

            print("UART LOOPBACK START".center(os.get_terminal_size().columns, "-"))
            # 10 bauds per byte
            bps_max = int(rate * 8 / 10)
            print(f"Baud rate: \t{rate : >7} \tMax bit rate: \t{bps_max:,d} bps")
            passing = True
            with Serial(str(args.dev), rate) as serial:
                serial.flush()
                while serial.input_waiting() > 0:
                    serial.read(serial.input_waiting(), 1)
                tx = random.randbytes(args.num_bytes)

                with tqdm(total=(8 * len(tx)), unit="bit", unit_scale=True) as pbar:
                    for chunk in range(0, len(tx), args.chunk_size):
                        serial.write(tx[chunk : chunk + args.chunk_size])
                        serial.flush()
                        # 20 = 10 bauds per byte times 2 directions
                        rx = serial.read(args.chunk_size, 20 * args.chunk_size / rate)
                        if tx[chunk : chunk + args.chunk_size] != rx:
                            passing = False
                            break
                        pbar.update(8 * args.chunk_size)
                    bps = int(8 * len(tx) / pbar.format_dict["elapsed"])

            print(
                f"Result: \t{'PASS' if passing else 'FAIL'}"
                + (f" \t\tNet bit rate: \t{bps:,d} bps" if passing else "")
            )
            if passing:
                throughputs[rate] = bps / bps_max
                print(f"\t\t\t\tThroughput: \t{100 * throughputs[rate]:.1f}%")

            print("UART LOOPBACK END".center(os.get_terminal_size().columns, "-"))
            print(
                f"TESTED  BAUD RATE {rate}".center(os.get_terminal_size().columns, "=")
            )
            print("")
            if (rate == RATES[0]) and not passing:
                raise RuntimeError(
                    f"TEST FAILED: Failure at standard rate of {rate}."
                    "Higher baud rates will not be tested."
                )

    pass_rates = sorted(throughputs.keys())
    print("")
    print("REPORT".center(65, "="))
    for rate in RATES:
        print(
            f"Baud rate: \t{rate : >7}"
            f" \tResult: {'PASS' if rate in pass_rates else 'FAIL'}"
            + (
                f" \tThroughput: {100 * throughputs.get(rate):.1f}%"
                if rate in pass_rates
                else ""
            )
        )
    print("".center(65, "="))

    with open(config_fname, "r") as f:
        config = load(f)
    old_pass_rates = config[args.target]["parameters"]["uart"]["baud_rates"]

    if pass_rates != old_pass_rates:
        yn = input(
            f"Baud rates in {args.target} config: {old_pass_rates}\n"
            f"Baud rates passing loopback: {pass_rates}\n"
            f"Would you like to alter the {args.target} config? [y/N]: "
        )

        if "y" in yn.lower():
            config[args.target]["parameters"]["uart"]["baud_rates"] = pass_rates
            with open(config_fname, "w") as f:
                dump(config, f, indent=4)
            print(f"Updated {args.target} config with working baud rates.")

    print("")
    print("DONE")


if __name__ == "__main__":
    main()
