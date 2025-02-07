# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import argparse
import base64

import dash_bootstrap_components as dbc
from dash import (
    ALL,
    Dash,
    Input,
    Output,
    Patch,
    State,
    callback,
    ctx,
    dcc,
    html,
    no_update,
)
from neuro import Network
from waitress import serve

from fpga._math import (
    bools_to_signed,
    bools_to_unsigned,
    signed_to_bools,
    unsigned_to_bools,
    unsigned_width,
    width_padding_to_byte,
)
from fpga._processor import DispatchOpcode, IoType, StreamFlag, dispatch_operand_widths
from fpga.network import charge_width, proc_params_dict


def io_type(io_type_str):
    return getattr(IoType, io_type_str.upper())


def prefix_type(io_type_str: str):
    io_t = io_type(io_type_str)
    match io_t:
        case IoType.DISPATCH:
            return DispatchOpcode
        case IoType.STREAM:
            return StreamFlag
        case _:
            raise ValueError()


def is_flag(pfx_t: type):
    return "flag" in pfx_t.__name__.lower()


def prefix_width(pfx_t: type):
    return len(pfx_t) if is_flag(pfx_t) else unsigned_width(len(pfx_t) - 1)


def prefix(pfx_t, pfx_str):
    return getattr(pfx_t, pfx_str.upper())


app = Dash(
    external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=False
)

app.layout = dbc.Container(
    [
        dbc.Row(dbc.Col(html.H1("Packet Visualization"))),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Upload(
                        children=dbc.InputGroup(
                            [
                                dbc.InputGroupText("Drag and Drop or "),
                                dbc.Button("Select Network File"),
                            ]
                        ),
                        id="network_file",
                        multiple=False,
                        # accept="*.txt,*.json",
                    ),
                    width="auto",
                ),
                dbc.Col(dbc.Label("Parameters from:"), width="auto"),
                dbc.Col(
                    dbc.RadioItems(
                        id="param_select",
                        options=[
                            {"label": "File", "value": "File", "disabled": True},
                            {"label": "Manual", "value": "Manual"},
                        ],
                        value="Manual",
                        inline=True,
                    ),
                    width="auto",
                ),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("Processor Parameters"),
                        dbc.Row(
                            [
                                dbc.Col(dbc.Label("Charge Width")),
                                dbc.Col(
                                    # Cannot use fewer than 2 bits for signed int
                                    dbc.Input(
                                        id="charge_width",
                                        type="number",
                                        inputMode="numeric",
                                        value=8,
                                        min=2,
                                    )
                                ),
                            ],
                            align="center",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(dbc.Label("Interface(s)")),
                                dbc.Col(
                                    dbc.Checklist(
                                        id="interfaces",
                                        options=[
                                            {
                                                "label": "AXI Stream",
                                                "value": "AXI Stream",
                                            },
                                            {"label": "UART", "value": "UART"},
                                        ],
                                        value=["UART"],
                                        switch=True,
                                    )
                                ),
                            ],
                            align="center",
                        ),
                    ],
                    width="auto",
                ),
                dbc.Col(
                    [
                        html.H2("Network Parameters"),
                        dbc.Row(
                            [
                                dbc.Col(dbc.Label("Number of Input Neurons")),
                                dbc.Col(
                                    [
                                        dbc.Input(
                                            id="num_inp",
                                            type="number",
                                            inputMode="numeric",
                                            value=1,
                                            min=1,
                                        ),
                                    ]
                                ),
                            ],
                            align="center",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(dbc.Label("Number of Output Neurons")),
                                dbc.Col(
                                    [
                                        dbc.Input(
                                            id="num_out",
                                            type="number",
                                            inputMode="numeric",
                                            value=1,
                                            min=1,
                                        ),
                                    ]
                                ),
                            ],
                            align="center",
                        ),
                    ],
                    width="auto",
                ),
            ],
        ),
        html.H2("Source"),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Col(dbc.Label("Source Type")),
                            dbc.Col(
                                dbc.RadioItems(
                                    id="source_type",
                                    options=[
                                        io_name.capitalize()
                                        for io_name in IoType._member_names_
                                    ],
                                    value=IoType.DISPATCH.name.capitalize(),
                                ),
                                width="auto",
                            ),
                        ]
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Table(
                        id="source_table",
                        bordered=True,
                        responsive=True,
                    )
                ),
            ]
        ),
        html.H2("Sink"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Row(
                            [
                                dbc.Col(dbc.Label("Sink Type")),
                                dbc.Col(
                                    dbc.RadioItems(
                                        id="sink_type",
                                        options=[
                                            io_name.capitalize()
                                            for io_name in IoType._member_names_
                                        ],
                                        value=IoType.DISPATCH.name.capitalize(),
                                    )
                                ),
                            ]
                        ),
                    ],
                    width="auto",
                ),
                dbc.Col(
                    dbc.Table(
                        id="sink_table",
                        bordered=True,
                        responsive=True,
                    )
                ),
            ]
        ),
    ]
)


@callback(
    Output("param_select", "options"),
    Output("param_select", "value"),
    Output("charge_width", "value"),
    Output("num_inp", "value"),
    Output("num_out", "value"),
    Input("param_select", "value"),
    Input("network_file", "contents"),
    Input("charge_width", "value"),
    Input("num_inp", "value"),
    Input("num_out", "value"),
)
def update_parameters(select, contents, proc_charge_width, net_num_inp, net_num_out):
    if None in [proc_charge_width, net_num_inp, net_num_out]:
        # values between changes
        return no_update, no_update, no_update, no_update, no_update
    options = Patch()
    if ctx.triggered_id and ctx.triggered_id == "network_file" and contents:
        select = "File"

    if not contents:
        options[0]["disabled"] = True

    if (
        ctx.triggered_id
        and ctx.triggered_id in ["param_select", "network_file"]
        and select == "File"
    ):
        options[0]["disabled"] = False
        _, content_string = contents.split(",")
        text = base64.b64decode(content_string).decode("utf-8")
        net = Network()
        net.from_str(text)
        proc_params = proc_params_dict(net)
        if not proc_params["discrete"]:
            raise ValueError("Non-discrete network targeting FPGA not yet supported.")
        return options, select, charge_width(net), net.num_inputs(), net.num_outputs()
    else:
        return options, "Manual", no_update, no_update, no_update


@callback(
    Output("interfaces", "options"),
    Output("interfaces", "value"),
    Input("interfaces", "value"),
)
def update_interface_options(interfaces_value):
    # Prevent toggling off of AXI Stream if dependent interface is enabled
    interfaces_options = Patch()
    if "UART" in interfaces_value:
        interfaces_options[0]["disabled"] = True
        if "AXI Stream" not in interfaces_value:
            interfaces_value.append("AXI Stream")
    else:
        interfaces_options[0]["disabled"] = False

    # Prevent toggling on of dependent interface if AXI Stream is disabled
    if "AXI Stream" not in interfaces_value:
        interfaces_options[1]["disabled"] = True
    else:
        interfaces_options[1]["disabled"] = False

    return interfaces_options, interfaces_value


def update_prefix_table(io_label: str, io_type_str: str):
    pfx_t = prefix_type(io_type_str)
    pfx_width = prefix_width(pfx_t)

    rows = [[html.Th("Flags" if is_flag(pfx_t) else "Opcode", colSpan=pfx_width)]]
    if is_flag(pfx_t):
        rows.append([html.Td(flg_name) for flg_name in pfx_t._member_names_])
    else:
        rows.append(
            [
                html.Td(
                    dbc.Select(
                        id={"type": io_label + "_opcode"},
                        options=pfx_t._member_names_,
                    ),
                    colSpan=pfx_width,
                )
            ]
        )

    rows.append(
        [
            html.Td(
                dbc.Switch(
                    id={
                        "type": io_label
                        # we change the switch type to avoid callbacks on flag changes
                        + ("_flag" if is_flag(pfx_t) else "_opcode") + "_switch",
                        "index": idx,
                    },
                    value=False,
                    disabled=False,
                )
            )
            for idx in range(pfx_width)
        ]
    )
    return [
        html.Tbody(
            [html.Thead(row) if row == 0 else html.Tr(row) for row in rows],
            id={"type": io_label + "_table_body"},
        )
    ]


def update_opcode(
    ctx, opcode_str: str, bit_switches: list[bool], io_type_str: str
) -> tuple[str, list[bool]]:
    pfx_t = prefix_type(io_type_str)
    pfx_width = prefix_width(pfx_t)
    # set opc to opcode based on whether triggered by select or switches
    if ctx.triggered_id and "switch" not in ctx.triggered_id["type"]:
        return no_update, unsigned_to_bools(prefix(pfx_t, opcode_str).value, pfx_width)
    else:
        return pfx_t(
            bools_to_unsigned(bit_switches),
        ).name, [
            no_update
        ] * len(bit_switches)


def update_operand_table(
    io_label: str,
    bit_switches: list[bool],
    interfaces: list[str],
    net_num_io: int,
    charge_width: int,
    io_type_str: str,
    old_body,
):
    io_t = io_type(io_type_str)
    pfx_t = prefix_type(io_type_str)
    pfx_width = prefix_width(pfx_t)

    body = Patch()
    # NOTE: looping backward is required to avoid skipping indices to delete
    for i in range(len(old_body[0]["props"]["children"]) - 1, 0, -1):
        del body[0]["props"]["children"][i]
    for i in range(
        len(old_body[1]["props"]["children"]) - 1,
        pfx_width - 1 if is_flag(pfx_t) else 0,
        -1,
    ):
        del body[1]["props"]["children"][i]
    for i in range(len(old_body[2]["props"]["children"]) - 1, pfx_width - 1, -1):
        del body[2]["props"]["children"][i]

    # NOTE: source table callback restores operand defaults when source type changes
    match io_t:
        case IoType.DISPATCH:
            idx_width, operand_width = dispatch_operand_widths(
                pfx_width, net_num_io, charge_width, "AXI Stream" in interfaces
            )
            padding = (
                width_padding_to_byte(pfx_width + idx_width + charge_width)
                if "AXI Stream" in interfaces
                else 0
            )
            match pfx_t(bools_to_unsigned(bit_switches)):
                case DispatchOpcode.SNC | DispatchOpcode.CLR:
                    body[0]["props"]["children"].append(
                        html.Th("Padding", colSpan=operand_width)
                    )
                    body[1]["props"]["children"].append(html.Td(colSpan=operand_width))
                    body[2]["props"]["children"].extend(
                        [
                            html.Td(
                                dbc.Switch(
                                    id={
                                        "type": io_label + "_operand_switch",
                                        "index": i,
                                    },
                                    value=False,
                                    disabled=True,
                                )
                            )
                            for i in range(operand_width)
                        ]
                    )

                case DispatchOpcode.SPK:
                    if idx_width:
                        body[0]["props"]["children"].append(
                            html.Th("Index", colSpan=idx_width)
                        )
                        body[1]["props"]["children"].append(
                            html.Td(
                                dbc.Input(
                                    id={"type": io_label + "_operand", "index": 0},
                                    type="number",
                                    inputMode="numeric",
                                    value=0,
                                    min=0,
                                    max=net_num_io - 1,
                                ),
                                colSpan=idx_width,
                            )
                        )

                    if charge_width:
                        body[0]["props"]["children"].append(
                            html.Th("Charge", colSpan=charge_width)
                        )
                        body[1]["props"]["children"].append(
                            html.Td(
                                dbc.Input(
                                    id={
                                        "type": io_label + "_operand",
                                        "index": int(idx_width > 0),
                                    },
                                    type="number",
                                    inputMode="numeric",
                                    value=0,
                                    min=-(2 ** (charge_width - 1)),
                                    max=(2 ** (charge_width - 1)) - 1,
                                ),
                                colSpan=charge_width,
                            )
                        )

                    if padding:
                        body[0]["props"]["children"].append(
                            html.Th("Padding", colSpan=padding)
                        )
                        body[1]["props"]["children"].append(html.Td(colSpan=padding))

                    body[2]["props"]["children"].extend(
                        [
                            html.Td(
                                dbc.Switch(
                                    id={
                                        "type": io_label + "_operand_switch",
                                        "index": i,
                                    },
                                    value=False,
                                    disabled=(i >= (operand_width - padding)),
                                )
                            )
                            for i in range(operand_width)
                        ]
                    )

                case DispatchOpcode.RUN:
                    body[0]["props"]["children"].append(
                        html.Th("Number of Runs", colSpan=operand_width)
                    )
                    body[1]["props"]["children"].append(
                        html.Td(
                            dbc.Input(
                                id={"type": io_label + "_operand", "index": 0},
                                type="number",
                                inputMode="numeric",
                                value=0,
                                min=0,
                                max=2**operand_width - 1,
                            ),
                            colSpan=operand_width,
                        )
                    )
                    body[2]["props"]["children"].extend(
                        [
                            html.Td(
                                dbc.Switch(
                                    id={
                                        "type": io_label + "_operand_switch",
                                        "index": i,
                                    },
                                    value=False,
                                    disabled=False,
                                )
                            )
                            for i in range(operand_width)
                        ]
                    )

                case _:
                    raise ValueError()

        case IoType.STREAM:
            spk_width = net_num_io * max(charge_width, 1)
            padding = (
                width_padding_to_byte(pfx_width + spk_width)
                if "AXI Stream" in interfaces
                else 0
            )

            for inp in range(net_num_io):
                body[0]["props"]["children"].append(
                    html.Th(
                        f"Index {inp} " + ("Charge" if charge_width else "Fire"),
                        colSpan=max(charge_width, 1),
                    )
                )
                body[1]["props"]["children"].append(
                    html.Td(
                        dbc.Input(
                            id={"type": io_label + "_operand", "index": inp},
                            type="number",
                            inputMode="numeric",
                            value=0,
                            min=-(2 ** (charge_width - 1)),
                            max=(2 ** (charge_width - 1)) - 1,
                        ),
                        colSpan=charge_width,
                    )
                    if charge_width
                    else html.Td()
                )

            if padding:
                body[0]["props"]["children"].append(html.Th("Padding", colSpan=padding))
                body[1]["props"]["children"].append(html.Td(colSpan=padding))

            body[2]["props"]["children"].extend(
                [
                    html.Td(
                        dbc.Switch(
                            id={"type": io_label + "_operand_switch", "index": i},
                            value=False,
                            disabled=(i >= spk_width),
                        )
                    )
                    for i in range(spk_width + padding)
                ]
            )

        case _:
            raise ValueError()

    return body


def update_operand(
    ctx,
    operands: list,
    bit_switches: list[bool],
    opc_switches: list[bool],
    interfaces: list[str],
    io_type_str: str,
    net_num_io,
    charge_width,
):
    if (
        ctx.triggered_id
        and "switch" not in ctx.triggered_id["type"]
        and None in operands
    ):
        # value between changes
        return [no_update] * len(operands), [no_update] * len(bit_switches)

    inp_type = io_type(io_type_str)
    pfx_t = prefix_type(io_type_str)
    pfx_width = prefix_width(pfx_t)

    match inp_type:
        case IoType.DISPATCH:
            idx_width, operand_width = dispatch_operand_widths(
                pfx_width, net_num_io, charge_width, "AXI Stream" in interfaces
            )
            padding = (
                width_padding_to_byte(pfx_width + idx_width + charge_width)
                if "AXI Stream" in interfaces
                else 0
            )
            match pfx_t(bools_to_unsigned(opc_switches)):
                case DispatchOpcode.SNC | DispatchOpcode.CLR:
                    return [no_update] * len(operands), [no_update] * len(bit_switches)
                case DispatchOpcode.SPK:
                    if ctx.triggered_id and "switch" not in ctx.triggered_id["type"]:
                        if idx_width:
                            bit_switches[:idx_width] = unsigned_to_bools(
                                operands[0], idx_width
                            )
                        if charge_width:
                            bit_switches[idx_width : idx_width + charge_width] = (
                                signed_to_bools(
                                    operands[int(idx_width > 0)], charge_width
                                )
                            )
                        return [no_update] * len(operands), bit_switches
                    else:
                        if idx_width:
                            operands[0] = bools_to_unsigned(bit_switches[:idx_width])
                        if charge_width:
                            operands[int(idx_width > 0)] = bools_to_signed(
                                bit_switches[idx_width : idx_width + charge_width]
                            )
                        return operands, [no_update] * len(bit_switches)

                case DispatchOpcode.RUN:
                    if ctx.triggered_id and "switch" not in ctx.triggered_id["type"]:
                        return [no_update], unsigned_to_bools(
                            operands[0], operand_width
                        )
                    else:
                        return [bools_to_unsigned(bit_switches)], [
                            no_update
                        ] * operand_width

                case _:
                    raise ValueError()

        case IoType.STREAM:
            spk_width = net_num_io * max(charge_width, 1)
            padding = (
                width_padding_to_byte(pfx_width + spk_width)
                if "AXI Stream" in interfaces
                else 0
            )

            if ctx.triggered_id and "switch" not in ctx.triggered_id["type"]:
                if charge_width:
                    for inp in range(net_num_io):
                        bit_switches[inp * charge_width : (inp + 1) * charge_width] = (
                            signed_to_bools(operands[inp], charge_width)
                        )
                return [no_update] * len(operands), bit_switches
            else:
                operands = []
                if charge_width:
                    [
                        operands.append(
                            bools_to_signed(
                                bit_switches[
                                    inp * charge_width : (inp + 1) * charge_width
                                ]
                            )
                        )
                        for inp in range(net_num_io)
                    ]
                return operands, [no_update] * (spk_width + padding)

        case _:
            raise ValueError()


@callback(
    Output("source_table", "children"),
    Input("source_type", "value"),
)
def update_source_prefix_table(source_type_str):
    return update_prefix_table("source", source_type_str)


@callback(
    Output({"type": "source_opcode"}, "value"),
    Output({"type": "source_opcode_switch", "index": ALL}, "value"),
    Input({"type": "source_opcode"}, "value"),
    Input({"type": "source_opcode_switch", "index": ALL}, "value"),
    State("source_type", "value"),
)
def update_source_opcode(opcode_str, bit_switches, source_type_str):
    return update_opcode(ctx, opcode_str, bit_switches, source_type_str)


@callback(
    Output({"type": "source_table_body"}, "children"),
    Input({"type": "source_opcode_switch", "index": ALL}, "value"),
    Input("interfaces", "value"),
    Input("num_inp", "value"),
    Input("charge_width", "value"),
    State("source_type", "value"),
    # need the old body to get lengths of rows, etc.
    State({"type": "source_table_body"}, "children"),
)
def update_source_operand_table(
    bit_switches, interfaces, net_num_inp, proc_charge_width, source_type_str, old_body
):
    return update_operand_table(
        "source",
        bit_switches,
        interfaces,
        net_num_inp,
        proc_charge_width,
        source_type_str,
        old_body,
    )


@callback(
    Output({"type": "source_operand", "index": ALL}, "value"),
    Output({"type": "source_operand_switch", "index": ALL}, "value"),
    Input({"type": "source_operand", "index": ALL}, "value"),
    Input({"type": "source_operand_switch", "index": ALL}, "value"),
    State({"type": "source_opcode_switch", "index": ALL}, "value"),
    State("interfaces", "value"),
    State("source_type", "value"),
    State("num_inp", "value"),
    State("charge_width", "value"),
)
def update_source_operand(
    operands,
    bit_switches,
    opc_switches,
    interfaces,
    source_type_str,
    net_num_inp,
    proc_charge_width,
):
    return update_operand(
        ctx,
        operands,
        bit_switches,
        opc_switches,
        interfaces,
        source_type_str,
        net_num_inp,
        proc_charge_width,
    )


@callback(
    Output("sink_table", "children"),
    Input("sink_type", "value"),
)
def update_sink_prefix_table(sink_type_str):
    return update_prefix_table("sink", sink_type_str)


@callback(
    Output({"type": "sink_opcode"}, "value"),
    Output({"type": "sink_opcode_switch", "index": ALL}, "value"),
    Input({"type": "sink_opcode"}, "value"),
    Input({"type": "sink_opcode_switch", "index": ALL}, "value"),
    State("sink_type", "value"),
)
def update_sink_opcode(opcode_str, bit_switches, sink_type_str):
    return update_opcode(ctx, opcode_str, bit_switches, sink_type_str)


@callback(
    Output({"type": "sink_table_body"}, "children"),
    Input({"type": "sink_opcode_switch", "index": ALL}, "value"),
    Input("interfaces", "value"),
    Input("num_out", "value"),
    State("sink_type", "value"),
    # need the old body to get lengths of rows, etc.
    State({"type": "sink_table_body"}, "children"),
)
def update_sink_operand_table(
    bit_switches, interfaces, net_num_out, sink_type_str, old_body
):
    return update_operand_table(
        "sink",
        bit_switches,
        interfaces,
        net_num_out,
        0,
        sink_type_str,
        old_body,
    )


@callback(
    Output({"type": "sink_operand", "index": ALL}, "value"),
    Output({"type": "sink_operand_switch", "index": ALL}, "value"),
    Input({"type": "sink_operand", "index": ALL}, "value"),
    Input({"type": "sink_operand_switch", "index": ALL}, "value"),
    State({"type": "sink_opcode_switch", "index": ALL}, "value"),
    State("interfaces", "value"),
    State("sink_type", "value"),
    State("num_out", "value"),
)
def update_sink_operand(
    operands,
    bit_switches,
    opc_switches,
    interfaces,
    sink_type_str,
    net_num_out,
):
    return update_operand(
        ctx,
        operands,
        bit_switches,
        opc_switches,
        interfaces,
        sink_type_str,
        net_num_out,
        0,
    )


def main():
    parser = argparse.ArgumentParser(
        prog="packet-vis", description="Packet Visualization Utility"
    )
    parser.add_argument(
        "-p",
        dest="port",
        type=int,
        default=8050,
        help="Port number for visualization web server (defaults to 8050)",
    )
    args = parser.parse_args()

    print(f"Packet Visualization running on http://0.0.0.0:{args.port}/")
    serve(app.server, port=args.port)


if __name__ == "__main__":
    main()
