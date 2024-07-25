# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
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

import fpga._processor
from fpga._math import bool_list_to_uint, uint_to_bool_list, width_padding_to_byte
from fpga._processor import (
    DispatchOpcode,
    IoType,
    dispatch_operand_widths,
    opcode_width,
)
from fpga.network import charge_width


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
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("Source"),
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
                    ],
                    width="auto",
                ),
                dbc.Col(
                    dbc.Table(
                        id="source_table",
                    )
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("Sink"),
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
                    )
                ),
            ]
        ),
    ]
)


@callback(
    Output("charge_width", "value"),
    Output("num_inp", "value"),
    Output("num_out", "value"),
    Output("charge_width", "readonly"),
    Output("num_inp", "readonly"),
    Output("num_out", "readonly"),
    Input("param_select", "value"),
    State("network_file", "contents"),
    State("charge_width", "value"),
    State("num_inp", "value"),
    State("num_out", "value"),
)
def update_parameters(select, contents, net_charge_width, num_inp, num_out):
    if select == "File":
        _, content_string = contents.split(",")
        text = base64.b64decode(content_string).decode("utf-8")
        net = Network()
        net.from_str(text)
        proc_params = net.get_data("proc_params").to_python()
        if not proc_params["discrete"]:
            raise ValueError("Non-discrete network targeting FPGA not yet supported.")
        return charge_width(net), net.num_inputs(), net.num_outputs(), True, True, True
    else:
        return net_charge_width, num_inp, num_out, False, False, False


@callback(
    Output("param_select", "options"),
    Output("param_select", "value"),
    Input("network_file", "contents"),
    State("param_select", "options"),
)
def enable_param_select(contents, options):
    if contents is not None:
        options[0]["disabled"] = False
        return options, "File"
    else:
        options[0]["disabled"] = True
        return options, "Manual"


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
    Input("interfaces", "value"),
    Input("source_type", "value"),
    Input("num_inp", "value"),
    Input("charge_width", "value"),
)
def update_source_table(interfaces, source_type_str, net_num_inp, proc_charge_width):
    inp_type = io_type(source_type_str)
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

    _, operand_width = dispatch_operand_widths(
        net_num_inp, proc_charge_width, "AXI Stream" in interfaces
    )

    rows[0].append(html.Th("Operand", colSpan=operand_width))
    rows[1].append(html.Td(colSpan=operand_width))

    rows.append(
        [
            html.Td(dbc.Switch(id={"type": "bit_switch", "index": idx}, value=False))
            for idx in range(opc_width + operand_width)
        ]
    )
    return [
        html.Tbody([html.Tr(row) for row in rows], id={"type": "source_table_body"})
    ]


@callback(
    Output({"type": "opcode"}, "value"),
    Output({"type": "bit_switch", "index": ALL}, "value"),
    Input({"type": "opcode"}, "value"),
    Input({"type": "bit_switch", "index": ALL}, "value"),
    State("source_type", "value"),
)
def update_opcode(opcode_str, bit_switches, source_type_str):
    opc_type = opcode_type(source_type_str)
    opc_width = opcode_width(opc_type)
    # set opc to opcode based on whether triggered by select or switches
    if ctx.triggered_id and ctx.triggered_id["type"] == "opcode":
        opc = opcode(opc_type, opcode_str)
    elif ctx.triggered_id is None or ctx.triggered_id["index"] < opc_width:
        opc = opc_type(
            bool_list_to_uint(bit_switches[:opc_width]),
        )
    # case where triggered by non-opcode switches; return with no changes
    else:
        return no_update, [no_update] * len(bit_switches)

    bit_switches = uint_to_bool_list(opc.value, opc_width) + (
        [False] * len(bit_switches[opc_width:])
    )
    return opc.name, bit_switches


@callback(
    Output({"type": "source_table_body"}, "children"),
    Input({"type": "opcode"}, "value"),
    State("interfaces", "value"),
    State("source_type", "value"),
    State("num_inp", "value"),
    State("charge_width", "value"),
    # need the old body to get lengths of rows, etc.
    State({"type": "source_table_body"}, "children"),
)
def update_operand_table(
    opcode_str, interfaces, source_type_str, net_num_inp, proc_charge_width, old_body
):
    inp_type = io_type(source_type_str)
    opc_type = opcode_type(source_type_str)
    opc_width = opcode_width(opc_type)

    body = Patch()

    # NOTE: source table callback restores operand defaults when source type changes
    match inp_type:
        case IoType.DISPATCH:
            idx_width, operand_width = dispatch_operand_widths(
                net_num_inp, proc_charge_width, "AXI Stream" in interfaces
            )
            padding = width_padding_to_byte(opc_width + idx_width + proc_charge_width)
            # NOTE: looping backward is required to avoid skipping indices to delete
            for i in range(len(old_body[0]["props"]["children"]) - 1, 0, -1):
                del body[0]["props"]["children"][i]
            for i in range(len(old_body[1]["props"]["children"]) - 1, 0, -1):
                del body[1]["props"]["children"][i]

            match opcode(opc_type, opcode_str):
                case DispatchOpcode.NOP | DispatchOpcode.CLR:
                    body[0]["props"]["children"].append(
                        html.Th("Operand", colSpan=operand_width)
                    )
                    body[1]["props"]["children"].append(html.Td(colSpan=operand_width))

                case DispatchOpcode.SPK:
                    if idx_width > 0:
                        body[0]["props"]["children"].append(
                            html.Th("Input Index", colSpan=idx_width)
                        )
                        body[1]["props"]["children"].append(
                            html.Td(
                                dbc.Input(
                                    id={"type": "inp_idx"},
                                    type="number",
                                    value=1,
                                    min=0,
                                    max=net_num_inp - 1,
                                ),
                                colSpan=idx_width,
                            )
                        )

                    body[0]["props"]["children"].append(
                        html.Th("Input Value", colSpan=proc_charge_width)
                    )
                    body[1]["props"]["children"].append(
                        html.Td(
                            dbc.Input(
                                id={"type": "inp_val"},
                                type="number",
                                value=1,
                                min=-(2 ** (proc_charge_width - 1)),
                                max=(2 ** (proc_charge_width - 1)) - 1,
                            ),
                            colSpan=proc_charge_width,
                        )
                    )

                    body[0]["props"]["children"].append(
                        html.Th("Padding", colSpan=padding)
                    )
                    body[1]["props"]["children"].append(html.Td(colSpan=padding))

                case DispatchOpcode.RUN:
                    body[0]["props"]["children"].append(
                        html.Th("Number of Runs", colSpan=operand_width)
                    )
                    body[1]["props"]["children"].append(
                        html.Td(
                            dbc.Input(
                                id={"type": "num_runs"},
                                type="number",
                                value=1,
                                min=1,
                                max=2**operand_width - 1,
                            ),
                            colSpan=operand_width,
                        )
                    )
                case _:
                    raise ValueError()
        case IoType.STREAM:
            pass
        case _:
            raise ValueError()

    return body


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
