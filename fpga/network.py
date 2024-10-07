# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pathlib as pl
import re
from hashlib import sha256
from json import dumps
from math import ceil, log2, log10

import neuro

import fpga

HASH_LEN = 10


def charge_width(net: neuro.Network) -> int:
    proc_params = net.get_data("proc_params")
    if not isinstance(proc_params, dict):
        proc_params = proc_params.to_python()
        
    return int(
        ceil(
            log2(
                max(
                    abs(proc_params["max_weight"] + 1),  # +1 for perfect powers of 2
                    abs(proc_params["min_weight"]),
                )
            )
        )
        + 1  # +1 for the sign bit
    )


def _num_inp_ports(node: neuro.Node) -> int:
    return len(node.incoming) + (1 if (node.input_id > -1) else 0)


def _write_risp_network_sv(f, net: neuro.Network, suffix: str = "") -> None:
    proc_params = net.get_data("proc_params")
    if not isinstance(proc_params, dict):
        proc_params = proc_params.to_python()

    net_charge_width = charge_width(net)
    if not proc_params["discrete"]:
        # TODO: imlement conversion from non-discrete net
        if net_charge_width < 3:
            net_charge_width = 32
            # scale_factor = (2 ** (net_charge_width - 1) - 1) / abs_max_weight
        raise NotImplementedError(
            "Non-discrete network targeting FPGA not yet supported."
        )

    num_inp = net.num_inputs()
    num_out = net.num_outputs()

    if "fire_like_ravens" in proc_params and proc_params["fire_like_ravens"]:
        raise NotImplementedError("RAVENS firing pattern is not yet supported.")

    f.write(f"package network{suffix}_config;\n")
    f.write(f"    localparam int NET_CHARGE_WIDTH = {net_charge_width};\n")
    f.write(f"    localparam int NET_NUM_INP = {num_inp};\n")
    f.write(f"    localparam int NET_NUM_OUT = {num_out};\n")
    f.write(f"endpackage\n\n")

    f.write(f"import network{suffix}_config::*;\n\n")

    f.write(f"module network{suffix} (\n")
    f.write(f"    input logic clk,\n")
    f.write(f"    input logic arstn,\n")
    f.write(f"    input logic en,\n")
    f.write(f"    input logic signed [NET_CHARGE_WIDTH-1:0] inp [0:NET_NUM_INP-1],\n")
    f.write(f"    output logic [NET_NUM_OUT-1:0] out\n")
    f.write(f");\n")

    # begin formatting functions

    neur_id_digits = int(ceil(log10(net.num_nodes() + 1)))

    def neur_id(node_id: int) -> str:
        return f"{node_id:0{neur_id_digits}d}"

    thresh_idx = net.get_node_property("Threshold").index

    def thresh(node: neuro.Node) -> int:
        return int(node.values[thresh_idx])

    thresh_incl = (
        proc_params["threshold_inclusive"]
        if ("threshold_inclusive" in proc_params)
        else True
    )
    if "min_potential" in proc_params:
        if proc_params["min_potential"] <= 0:
            min_potential = proc_params["min_potential"]
        else:
            raise ValueError("min_potential must be less than or equal to 0")
    elif ("non_negative_charge" in proc_params) and proc_params["non_negative_charge"]:
        min_potential = 0
    else:
        min_potential = -1 * proc_params["max_threshold"]

    leak_mode = proc_params["leak_mode"] if ("leak_mode" in proc_params) else "none"
    match (leak_mode):
        case "none":

            def leak(_: neuro.Node) -> int:
                return 0

        case "all":

            def leak(_: neuro.Node) -> int:
                return 1

        case "configurable":
            leak_idx = net.get_node_property("Leak").index

            def leak(node: neuro.Node) -> int:
                return int(node.values[leak_idx])

        case _:
            raise ValueError(f'Invalid leak mode: "{leak_mode}"')

    # end formatting functions

    net.make_sorted_node_vector()
    for node in net.sorted_node_vector:
        num_inp_ports = _num_inp_ports(node)
        f.write(f"    // Start Neuron {neur_id(node.id)}\n")
        f.write(f"    logic neur_{neur_id(node.id)}_fire;\n")
        f.write(
            f"    logic signed [NET_CHARGE_WIDTH-1:0]"
            f" neur_{neur_id(node.id)}_inp [0:{max(num_inp_ports,1) - 1}];\n"
        )
        if node.input_id > -1:
            # use the last indexed port for input to make synapse generation easier
            f.write(
                f"    assign neur_{node.id:0{neur_id_digits}d}"
                f"_inp[{num_inp_ports - 1}]"
                f" = inp[{node.input_id}];\n"
            )
        
        if num_inp_ports == 0:
            f.write(
                f"    assign neur_{node.id:0{neur_id_digits}d}"
                f"_inp[0]"
                f" = 0;\n"
            )
        f.write(f"\n")

        f.write(f"    risp_neuron #(\n")
        f.write(f"        .THRESHOLD({thresh(node)}),\n")
        f.write(f"        .LEAK({leak(node)}),\n")
        f.write(f"        .NUM_INP({num_inp_ports}),\n")
        f.write(f"        .CHARGE_WIDTH(NET_CHARGE_WIDTH),\n")
        f.write(f"        .POTENTIAL_MIN({int(min_potential)}),\n")
        f.write(f"        .THRESHOLD_INCLUSIVE({int(thresh_incl)})\n")
        f.write(f"    ) neur_{neur_id(node.id)} (\n")
        f.write(f"        .clk,\n")
        f.write(f"        .arstn,\n")
        f.write(f"        .en,\n")
        f.write(f"        .inp(neur_{neur_id(node.id)}_inp),\n")
        f.write(f"        .fire(neur_{neur_id(node.id)}_fire)\n")
        f.write(f"    );\n")

        if node.output_id > -1:
            f.write(f"\n")
            f.write(
                f"    assign out[{node.output_id}] = neur_{neur_id(node.id)}_fire;\n"
            )

        f.write(f"    //  End  Neuron {neur_id(node.id)}\n\n")

    weight_idx = net.get_edge_property("Weight").index

    def weight(edge: neuro.Edge) -> int:
        return int(edge.values[weight_idx])

    delay_idx = net.get_edge_property("Delay").index

    def delay(edge: neuro.Edge) -> int:
        return int(edge.values[delay_idx])

    for node in net.sorted_node_vector:
        for inp_idx in range(len(node.incoming)):
            inp = node.incoming[inp_idx]
            f.write(f"\n")
            f.write(
                f"    // Start Synapse"
                f" {neur_id(inp.pre.id)}_{neur_id(inp.post.id)}\n"
            )
            f.write(f"    risp_synapse #(\n")
            f.write(f"        .WEIGHT({weight(inp)}),\n")
            f.write(f"        .DELAY({delay(inp)}),\n")
            f.write(f"        .CHARGE_WIDTH(NET_CHARGE_WIDTH)\n")
            f.write(f"    ) syn_{neur_id(inp.pre.id)}_{neur_id(inp.post.id)} (\n")
            f.write(f"        .clk,\n")
            f.write(f"        .arstn,\n")
            f.write(f"        .en,\n")
            f.write(f"        .inp(neur_{neur_id(inp.pre.id)}_fire),\n")
            f.write(f"        .out(neur_{neur_id(inp.post.id)}_inp[{inp_idx}])\n")
            f.write(f"    );\n")
            f.write(
                f"    //  End  Synapse {neur_id(inp.pre.id)}_{neur_id(inp.post.id)}\n"
            )

    f.write(f"endmodule\n")


def write_network_sv(sv, net: neuro.Network, suffix: str = "") -> None:
    net_other = net.get_data("other")

    if not isinstance(net_other, dict):
        net_other = net_other.to_python()

    proc = net_other["proc_name"]

    sv.write(
        "// This file has been generated by the Network HDL Generator.\n"
        "// It is STRONGLY DISCOURAGED to edit this file by hand.\n\n"
    )
    # TODO: Add support for other processors.
    match (proc):
        case "risp":
            _write_risp_network_sv(sv, net, suffix)
        case _:
            raise NotImplementedError(
                f"The {proc.upper()} processor is not yet supported."
            )


def hash_network(net: neuro.Network, length: int = None) -> str:
    net_dict = net.as_json().to_python()
    # Remove fields with no bearing on arch
    # TODO: filter more fields?
    for node in net_dict["Nodes"]:
        if "name" in node:
            del node["name"]
    for dat in net_dict["Associated_Data"]:
        match (dat):
            case "proc_params":
                pass
            case "other":
                for oth in net_dict["Associated_Data"][dat].copy():
                    if oth != "proc_name":
                        del net_dict["Associated_Data"][dat][oth]
            case _:
                del dat

    # TODO: set defaults for optional fields?
    # cannot seem to do by loading network into processor

    # `dumps` sorts dictionaries by key but not lists
    # the following lists have elements where order should not change function
    net_dict["Edges"] = sorted(net_dict["Edges"], key=lambda x: (x["to"], x["from"]))
    net_dict["Nodes"] = sorted(net_dict["Nodes"], key=lambda x: x["id"])
    net_dict["Properties"]["edge_properties"] = sorted(
        net_dict["Properties"]["edge_properties"], key=lambda x: x["index"]
    )
    net_dict["Properties"]["node_properties"] = sorted(
        net_dict["Properties"]["node_properties"], key=lambda x: x["index"]
    )
    net_dict["Properties"]["network_properties"] = sorted(
        net_dict["Properties"]["network_properties"], key=lambda x: x["index"]
    )
    # Inputs, Outputs, and Network_Values seem order-sensitive
    return sha256(
        dumps(
            net_dict,
            sort_keys=True,
        ).encode()
    ).hexdigest()[:length]


def build_network_sv(net: neuro.Network, net_path: str = "") -> pl.Path:
    if net_path == "":
        fpath = fpga.networks_build_path / (hash_network(net, HASH_LEN) + ".sv")
    else:
        fpath = pl.Path(net_path)
    if not fpath.is_file():
        fpath.parent.mkdir(parents=True, exist_ok=True)
        with open(fpath, "w") as sv:
            write_network_sv(sv, net)
    return fpath


def convert_file_sv(json_filepath: str, sv_filepath: str, naming: str = "bare") -> None:
    net = neuro.Network()
    net.read_from_file(json_filepath)

    suffix = "_"
    match (naming):
        case "bare":
            pass
        case "filename":
            suffix += re.sub("[\\-_]*net(work)?[\\-_]*", "", pl.Path(sv_filepath).stem)
        case "hash":
            suffix += hash_network(net)[:HASH_LEN]
        case _:
            raise ValueError(f'Invalid naming mode: "{naming}"')
    if suffix == "_":
        suffix = ""

    with open(sv_filepath, "w") as sv:
        write_network_sv(sv, net, suffix)
