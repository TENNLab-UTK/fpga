# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import base64

from dash import Dash, Input, Output, State, callback, dcc, html
from neuro import Network

import fpga._processor
from fpga._processor import _IoType
from fpga.network import charge_width

app = Dash()

app.layout = [
    html.H1("Packet Visualization"),
    html.Div(
        [
            "Network File",
            dcc.Upload(
                children=html.Div(
                    [
                        "Drag and Drop or ",
                        html.A("Select File"),
                    ]
                ),
                id="network_file",
                multiple=False,
                # accept="*.txt,*.json",
            ),
        ]
    ),
    html.Div(
        [
            "Parameters from:",
            dcc.RadioItems(
                id="param_select",
                options=[
                    {"label": "File", "value": "File", "disabled": True},
                    {"label": "Manual", "value": "Manual"},
                ],
                value="Manual",
            ),
        ]
    ),
    html.H2("Processor Parameters"),
    html.Div(
        [
            "Charge Width",
            # Cannot use fewer than 2 bits to represent a signed value
            dcc.Input(id="charge_width", type="number", value=8, min=2),
        ]
    ),
    html.H2("Network Parameters"),
    html.Div(
        [
            "Number of Input Neurons",
            dcc.Input(id="num_inp", type="number", value=1, min=1),
        ]
    ),
    html.Div(
        [
            "Number of Output Neurons",
            dcc.Input(id="num_out", type="number", value=1),
        ]
    ),
    html.Hr(),
    html.H2("Source"),
    html.Div(
        [
            "Source Type",
            dcc.Dropdown(
                id="source_type",
                options=[io_name.capitalize() for io_name in _IoType._member_names_],
                value=_IoType.DISPATCH.name.capitalize(),
                clearable=False,
            ),
        ]
    ),
    html.Div(
        [
            "Opcode",
            dcc.Dropdown(id="opcode"),
        ]
    ),
    html.Hr(),
    html.H2(children="Sink"),
    html.Div(
        [
            "Sink Type",
            dcc.Dropdown(
                id="sink_type",
                options=[io_name.capitalize() for io_name in _IoType._member_names_],
                value=_IoType.DISPATCH.name.capitalize(),
                clearable=False,
            ),
        ]
    ),
]


@callback(
    Output("charge_width", "value"),
    Output("num_inp", "value"),
    Output("num_out", "value"),
    Output("charge_width", "readOnly"),
    Output("num_inp", "readOnly"),
    Output("num_out", "readOnly"),
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
    Input("source_type", "value"),
)
def update_opcode_options(source_type_str):
    # HACK: this is probably asking for trouble
    opc_type = getattr(fpga._processor, "_" + source_type_str + "Opcode")
    return opc_type._member_names_


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
