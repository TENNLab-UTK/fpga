# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import base64

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, callback, dcc, html
from neuro import Network

import fpga._processor
from fpga._processor import _IoType
from fpga.network import charge_width

app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

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
                                    [
                                        # Cannot use fewer than 2 bits for signed int
                                        dbc.Input(
                                            id="charge_width",
                                            type="number",
                                            value=8,
                                            min=2,
                                        ),
                                    ]
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
                )
            ],
        ),
        dbc.Row(
            dbc.Col(
                [
                    html.H2("Source"),
                    dbc.Row(
                        [
                            dbc.Col(dbc.Label("Source Type")),
                            dbc.Col(
                                dbc.RadioItems(
                                    id="source_type",
                                    options=[io_name.capitalize() for io_name in _IoType._member_names_],
                                    value=_IoType.DISPATCH.name.capitalize(),
                                ),
                                width="auto",
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(dbc.Label("Opcode")),
                            dbc.Col(dbc.Select(id="opcode", )),
                        ]
                    ),
                ],
                width="auto",
            )
        ),
        dbc.Row(
            dbc.Col(
                [
                    html.H2("Sink"),
                    dbc.Row(
                        [
                            dbc.Col(dbc.Label("Sink Type")),
                            dbc.Col(
                                dbc.RadioItems(
                                        id="sink_type",
                                        options=[io_name.capitalize() for io_name in _IoType._member_names_],
                                        value=_IoType.DISPATCH.name.capitalize(),
                                )
                            ),
                        ]
                    ),
                ],
                width="auto",
            )
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
    Output("opcode", "options"),
    Output("opcode", "value"),
    Input("source_type", "value"),
)
def update_opcode_options(source_type_str):
    # HACK: this is probably asking for trouble
    opc_type = getattr(fpga._processor, "_" + source_type_str + "Opcode")
    return opc_type._member_names_, None


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
