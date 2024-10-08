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

import fpga._processor
from fpga._math import (
    bools_to_signed,
    bools_to_unsigned,
    signed_to_bools,
    unsigned_to_bools,
    unsigned_width,
    width_padding_to_byte,
)
from fpga._processor import (
    DispatchOpcode,
    IoType,
    dispatch_operand_widths,
    opcode_width,
)
from fpga.network import charge_width, proc_params_dict


def io_type(io_type_str):
    return getattr(IoType, io_type_str.upper())


def opcode_type(source_type_str):
    return getattr(fpga._processor, source_type_str + "Opcode")


def opcode(opc_type, opcode_str):
    return getattr(opc_type, opcode_str.upper())


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


@callback(
    Output("source_table", "children"),
    Input("source_type", "value"),
)
def update_opcode_table(source_type_str):
    opc_type = opcode_type(source_type_str)
    opc_width = opcode_width(opc_type)

    rows = [
        [html.Th("Opcode", colSpan=opc_width)],
        [
            html.Td(
                dbc.Select(
                    id={"type": "opcode"},
                    options=opc_type._member_names_,
                ),
                colSpan=opc_width,
            )
        ],
    ]

    rows.append(
        [
            html.Td(
                dbc.Switch(
                    id={"type": "opcode_switch", "index": idx},
                    value=False,
                    disabled=False,
                )
            )
            for idx in range(opc_width)
        ]
    )
    return [
        html.Tbody(
            [html.Thead(row) if row == 0 else html.Tr(row) for row in rows],
            id={"type": "source_table_body"},
        )
    ]


@callback(
    Output({"type": "opcode"}, "value"),
    Output({"type": "opcode_switch", "index": ALL}, "value"),
    Input({"type": "opcode"}, "value"),
    Input({"type": "opcode_switch", "index": ALL}, "value"),
    State("source_type", "value"),
)
def update_opcode(opcode_str, bit_switches, source_type_str):
    opc_type = opcode_type(source_type_str)
    opc_width = opcode_width(opc_type)
    # set opc to opcode based on whether triggered by select or switches
    if ctx.triggered_id and ctx.triggered_id["type"] == "opcode":
        return no_update, unsigned_to_bools(
            opcode(opc_type, opcode_str).value, opc_width
        )
    else:
        return opc_type(
            bools_to_unsigned(bit_switches),
        ).name, [
            no_update
        ] * len(bit_switches)


@callback(
    Output({"type": "source_table_body"}, "children"),
    Input({"type": "opcode"}, "value"),
    Input("interfaces", "value"),
    Input("num_inp", "value"),
    Input("charge_width", "value"),
    State("source_type", "value"),
    # need the old body to get lengths of rows, etc.
    State({"type": "source_table_body"}, "children"),
)
def update_operand_table(
    opcode_str, interfaces, net_num_inp, proc_charge_width, source_type_str, old_body
):
    inp_type = io_type(source_type_str)
    opc_type = opcode_type(source_type_str)
    opc_width = opcode_width(opc_type)

    body = Patch()
    # NOTE: looping backward is required to avoid skipping indices to delete
    for i in range(len(old_body[0]["props"]["children"]) - 1, 0, -1):
        del body[0]["props"]["children"][i]
    for i in range(len(old_body[1]["props"]["children"]) - 1, 0, -1):
        del body[1]["props"]["children"][i]
    for i in range(len(old_body[2]["props"]["children"]) - 1, opc_width - 1, -1):
        del body[2]["props"]["children"][i]

    # NOTE: source table callback restores operand defaults when source type changes
    match inp_type:
        case IoType.DISPATCH:
            idx_width, operand_width = dispatch_operand_widths(
                net_num_inp, proc_charge_width, "AXI Stream" in interfaces
            )
            padding = (
                width_padding_to_byte(opc_width + idx_width + proc_charge_width)
                if "AXI Stream" in interfaces
                else 0
            )
            match opcode(opc_type, opcode_str):
                case DispatchOpcode.NOP | DispatchOpcode.CLR:
                    body[0]["props"]["children"].append(
                        html.Th("Padding", colSpan=operand_width)
                    )
                    body[1]["props"]["children"].append(html.Td(colSpan=operand_width))
                    body[2]["props"]["children"].extend(
                        [
                            html.Td(
                                dbc.Switch(
                                    id={"type": "operand_switch", "index": i},
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
                            html.Th("Input", colSpan=idx_width)
                        )
                        body[1]["props"]["children"].append(
                            html.Td(
                                dbc.Input(
                                    id={"type": "operand", "index": 0},
                                    type="number",
                                    inputMode="numeric",
                                    value=0,
                                    min=0,
                                    max=net_num_inp - 1,
                                ),
                                colSpan=idx_width,
                            )
                        )

                    body[0]["props"]["children"].append(
                        html.Th("Charge", colSpan=proc_charge_width)
                    )
                    body[1]["props"]["children"].append(
                        html.Td(
                            dbc.Input(
                                id={"type": "operand", "index": int(idx_width > 0)},
                                type="number",
                                inputMode="numeric",
                                value=0,
                                min=-(2 ** (proc_charge_width - 1)),
                                max=(2 ** (proc_charge_width - 1)) - 1,
                            ),
                            colSpan=proc_charge_width,
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
                                    id={"type": "operand_switch", "index": i},
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
                                id={"type": "operand", "index": 0},
                                type="number",
                                inputMode="numeric",
                                value=1,
                                min=1,
                                max=2**operand_width - 1,
                            ),
                            colSpan=operand_width,
                        )
                    )
                    body[2]["props"]["children"].extend(
                        [
                            html.Td(
                                dbc.Switch(
                                    id={"type": "operand_switch", "index": i},
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
            spk_width = net_num_inp * proc_charge_width
            padding = (
                width_padding_to_byte(opc_width + spk_width)
                if "AXI Stream" in interfaces
                else 0
            )

            for inp in range(net_num_inp):
                body[0]["props"]["children"].append(
                    html.Th(f"Input {inp} Charge", colSpan=proc_charge_width)
                )
                body[1]["props"]["children"].append(
                    html.Td(
                        dbc.Input(
                            id={"type": "operand", "index": inp},
                            type="number",
                            inputMode="numeric",
                            value=0,
                            min=-(2 ** (proc_charge_width - 1)),
                            max=(2 ** (proc_charge_width - 1)) - 1,
                        ),
                        colSpan=proc_charge_width,
                    )
                )

            if padding:
                body[0]["props"]["children"].append(html.Th("Padding", colSpan=padding))
                body[1]["props"]["children"].append(html.Td(colSpan=padding))

            body[2]["props"]["children"].extend(
                [
                    html.Td(
                        dbc.Switch(
                            id={"type": "operand_switch", "index": i},
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


@callback(
    Output({"type": "operand", "index": ALL}, "value"),
    Output({"type": "operand_switch", "index": ALL}, "value"),
    Input({"type": "operand", "index": ALL}, "value"),
    Input({"type": "operand_switch", "index": ALL}, "value"),
    State({"type": "opcode"}, "value"),
    State("interfaces", "value"),
    State("source_type", "value"),
    State("num_inp", "value"),
    State("charge_width", "value"),
)
def update_operand(
    operands,
    bit_switches,
    opcode_str,
    interfaces,
    source_type_str,
    net_num_inp,
    proc_charge_width,
):
    if ctx.triggered_id and ctx.triggered_id["type"] == "operand" and None in operands:
        # value between changes
        return [no_update] * len(operands), [no_update] * len(bit_switches)

    inp_type = io_type(source_type_str)
    opc_type = opcode_type(source_type_str)
    opc_width = opcode_width(opc_type)

    match inp_type:
        case IoType.DISPATCH:
            idx_width, operand_width = dispatch_operand_widths(
                net_num_inp, proc_charge_width, "AXI Stream" in interfaces
            )
            padding = (
                width_padding_to_byte(opc_width + idx_width + proc_charge_width)
                if "AXI Stream" in interfaces
                else 0
            )
            match opcode(opc_type, opcode_str):
                case DispatchOpcode.NOP | DispatchOpcode.CLR:
                    return [no_update] * len(operands), [no_update] * len(bit_switches)
                case DispatchOpcode.SPK:
                    if ctx.triggered_id and ctx.triggered_id["type"] == "operand":
                        if idx_width:
                            bit_switches[:idx_width] = unsigned_to_bools(
                                operands[0], idx_width
                            )
                        bit_switches[idx_width : idx_width + proc_charge_width] = (
                            signed_to_bools(
                                operands[int(idx_width > 0)], proc_charge_width
                            )
                        )
                        return [no_update] * len(operands), bit_switches
                    else:
                        if idx_width:
                            operands[0] = bools_to_unsigned(bit_switches[:idx_width])
                        operands[int(idx_width > 0)] = bools_to_signed(
                            bit_switches[idx_width : idx_width + proc_charge_width]
                        )
                        return operands, [no_update] * len(bit_switches)

                case DispatchOpcode.RUN:
                    if ctx.triggered_id and ctx.triggered_id["type"] == "operand":
                        return [no_update], unsigned_to_bools(
                            operands[0], operand_width
                        )
                    else:
                        return [max(bools_to_unsigned(bit_switches), 1)], [
                            no_update
                        ] * operand_width

                case _:
                    raise ValueError()

        case IoType.STREAM:
            spk_width = net_num_inp * proc_charge_width
            padding = (
                width_padding_to_byte(opc_width + spk_width)
                if "AXI Stream" in interfaces
                else 0
            )

            if ctx.triggered_id and ctx.triggered_id["type"] == "operand":
                for inp in range(net_num_inp):
                    bit_switches[
                        inp * proc_charge_width : (inp + 1) * proc_charge_width
                    ] = signed_to_bools(operands[inp], proc_charge_width)
                return [no_update] * len(operands), bit_switches
            else:
                operands = []
                [
                    operands.append(
                        bools_to_signed(
                            bit_switches[
                                inp * proc_charge_width : (inp + 1) * proc_charge_width
                            ]
                        )
                    )
                    for inp in range(net_num_inp)
                ]
                return operands, [no_update] * (spk_width + padding)

        case _:
            raise ValueError()


@callback(
    Output("sink_table", "children"),
    Input("interfaces", "value"),
    Input("sink_type", "value"),
    Input("num_out", "value"),
)
def update_sink_table(interfaces, sink_type_str, net_num_out):
    if net_num_out is None:
        # value between changes
        return no_update

    out_type = io_type(sink_type_str)

    rows = [[], []]

    match out_type:
        case IoType.DISPATCH:
            idx_width = unsigned_width(net_num_out)
            padding = (
                width_padding_to_byte(idx_width) if "AXI Stream" in interfaces else 0
            )
            rows[0].append(
                html.Th(f"Number of Fires, Output Index Fired", colSpan=idx_width)
            )
            [
                rows[1].append(
                    html.Td(
                        dbc.Switch(
                            id={"type": "out_switch", "index": out},
                            value=False,
                            disabled=False,
                        )
                    )
                )
                for out in range(idx_width)
            ]
            rows.extend(
                [
                    [
                        html.Td(
                            dbc.Input(
                                id={"type": "out_idx"},
                                type="number",
                                inputMode="numeric",
                                value=0,
                                min=0,
                                max=net_num_out,
                            ),
                            colSpan=idx_width,
                        )
                    ]
                    + [html.Td() for _ in range(padding)]
                ]
            )

        case IoType.STREAM:
            padding = (
                width_padding_to_byte(net_num_out) if "AXI Stream" in interfaces else 0
            )

            [
                rows[0].append(html.Th(f"Output {out} Fire"))
                for out in range(net_num_out)
            ]
            [
                rows[1].append(
                    html.Td(
                        dbc.Switch(
                            id={"type": "fire_switch", "index": out},
                            value=False,
                            disabled=False,
                        )
                    )
                )
                for out in range(net_num_out)
            ]

        case _:
            raise ValueError()

    if padding:
        rows[0].append(html.Th("Padding", colSpan=padding))
        [
            rows[1].append(
                html.Td(
                    dbc.Switch(
                        id={"type": "fire_switch", "index": out},
                        value=False,
                        disabled=True,
                    )
                )
            )
            for out in range(padding)
        ]

    return [
        html.Tbody(
            [html.Thead(row) if row == 0 else html.Tr(row) for row in rows],
            id={"type": "sink_table_body"},
        )
    ]


@callback(
    Output({"type": "out_idx"}, "value"),
    Output({"type": "out_switch", "index": ALL}, "value"),
    Input({"type": "out_idx"}, "value"),
    Input({"type": "out_switch", "index": ALL}, "value"),
)
def update_output(out_idx, bit_switches):
    if ctx.triggered_id and ctx.triggered_id["type"] == "out_idx":
        if out_idx is None:
            # value between changes
            return no_update, [no_update] * len(bit_switches)
        return no_update, unsigned_to_bools(out_idx, len(bit_switches))
    else:
        return bools_to_unsigned(bit_switches), [no_update] * len(bit_switches)


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
