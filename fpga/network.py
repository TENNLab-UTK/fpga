# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pathlib as pl
import re
from hashlib import sha256
from json import dumps
from math import ceil, log10
from warnings import warn

import neuro

import fpga
from fpga._math import signed_width

HASH_LEN = 10


def charge_width(net: neuro.Network) -> int:
    proc_params = proc_params_dict(net)
    weight_width = max(
        [
            signed_width(weight)
            for weight in [
                proc_params["min_weight"],
                proc_params["max_weight"],
            ]
        ]
    )

    scaling_width = signed_width(spike_value_factor(net))
    if scaling_width > weight_width:
        warn(
            f"A spike factor of {spike_value_factor(net)}"
            f" will mandate a network charge width of {scaling_width} bits"
            f" which is greater than the charge width of {weight_width} bits"
            " mandated by the weight range"
            f" [{proc_params['min_weight']}, {proc_params['max_weight']}]."
            " This will potentially waste hardware resources."
        )

    return max(weight_width, scaling_width)


def max_period(net: neuro.Network) -> int:
    assoc_data_keys = net.data_keys()

    if "other" in assoc_data_keys:
        assoc_data_other = net.get_data("other")
        if "sim_time" in assoc_data_other:
            return assoc_data_other["sim_time"] / 2
    
    return 25


def spike_value_factor(net: neuro.Network) -> float:
    proc_params = proc_params_dict(net)
    svf = float(proc_params["max_weight"])
    if "spike_value_factor" in proc_params:
        svf = proc_params["spike_value_factor"]
    if svf < 1.0:
        raise ValueError("Spike value factor must be greater than or equal to 1")
    return svf


def proc_params_dict(net: neuro.Network) -> dict:
    proc_params = net.get_data("proc_params")
    if type(proc_params) is not dict:
        proc_params = proc_params.to_python()
    return proc_params


def proc_name(net: neuro.Network) -> str:
    other_data = net.get_data("other")
    if type(other_data) is not dict:
        other_data = other_data.to_python()
    return other_data["proc_name"]


def _num_inp_ports(node: neuro.Node) -> int:
    return len(node.incoming) + (1 if (node.input_id > -1) else 0)


def _write_risp_network_sv(f, net: neuro.Network, suffix: str = "") -> None:
    proc_params = proc_params_dict(net)
    net_charge_width = charge_width(net)
    if not proc_params["discrete"]:
        # TODO: imlement conversion from non-discrete net
        if net_charge_width < 3:
            net_charge_width = 32
            # scale_factor = (2 ** (net_charge_width - 1) - 1) / abs_max_weight
        raise NotImplementedError(
            "Non-discrete network targeting FPGA not yet supported."
        )
    
    net_max_period = max_period(net)

    num_inp = net.num_inputs()
    num_out = net.num_outputs()

    fire_like_ravens = (
        "fire_like_ravens" in proc_params and proc_params["fire_like_ravens"]
    )

    f.write(f"package network{suffix}_config;\n")
    f.write(f"    localparam int NET_CHARGE_WIDTH = {net_charge_width};\n")
    f.write(f"    localparam int NET_MAX_PERIOD = {net_max_period};\n")
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

    min_potential = -1 * proc_params["max_threshold"]
    if "min_potential" in proc_params:
        min_potential = proc_params["min_potential"]
    elif ("non_negative_charge" in proc_params) and proc_params["non_negative_charge"]:
        warn(
            "non_negative_charge is a deprecated field; set min_potential to 0 instead."
        )
        min_potential = 0
    if min_potential > 0:
        raise ValueError("min_potential must be less than or equal to 0")

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

    for n in net.nodes():
        node = net.get_node(n)
        num_inp_ports = _num_inp_ports(node)
        f.write(f"    // Start Neuron {neur_id(node.id)}\n")
        f.write(f"    logic neur_{neur_id(node.id)}_fire;\n")
        f.write(
            f"    logic signed [NET_CHARGE_WIDTH-1:0]"
            f" neur_{neur_id(node.id)}_inp [0:{num_inp_ports - 1}];\n"
        )
        if node.input_id > -1:
            if (thresh(node) + int(not thresh_incl)) > spike_value_factor(net):
                warn(
                    f"Neuron {neur_id(node.id)} (input {node.input_id}) has a threshold"
                    f" of {thresh(node)} which cannot be solely triggered by an"
                    f" input scaling value of {spike_value_factor(net)}."
                )
            # use the last indexed port for input to make synapse generation easier
            f.write(
                f"    assign neur_{node.id:0{neur_id_digits}d}"
                f"_inp[{num_inp_ports - 1}]"
                f" = inp[{node.input_id}];\n"
            )
        f.write(f"\n")

        f.write(f"    risp_neuron #(\n")
        f.write(f"        .THRESHOLD({thresh(node)}),\n")
        f.write(f"        .LEAK({leak(node)}),\n")
        f.write(f"        .NUM_INP({num_inp_ports}),\n")
        f.write(f"        .CHARGE_WIDTH(NET_CHARGE_WIDTH),\n")
        f.write(f"        .POTENTIAL_MIN({int(min_potential)}),\n")
        f.write(f"        .THRESHOLD_INCLUSIVE({int(thresh_incl)}),\n")
        f.write(f"        .FIRE_LIKE_RAVENS({int(fire_like_ravens)})\n")
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

    for n in net.nodes():
        node = net.get_node(n)
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
            f.write(f"        .CHARGE_WIDTH(NET_CHARGE_WIDTH),\n")
            f.write(f"        .FIRE_LIKE_RAVENS({int(fire_like_ravens)})\n")
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

    proc = proc_name(net)

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
    net_dict = net.as_json()
    if type(net_dict) is not dict:
        net_dict = net_dict.to_python()
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


def build_network_sv(net: neuro.Network) -> pl.Path:
    fpath = fpga.networks_build_path / (hash_network(net, HASH_LEN) + ".sv")
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
