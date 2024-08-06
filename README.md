<!--
 Copyright (c) 2024 Keegan Dent

 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

<div align="center">

# Neuromorphic FPGA

[![Status](https://img.shields.io/badge/status-active-success.svg)](https://github.com/TENNLab-UTK/fpga/graphs/code-frequency)
[![Software License](https://img.shields.io/badge/software_license-MPL--2.0-red.svg)](/LICENSE)
[![Hardware License](https://img.shields.io/badge/hardware_license-CERN--OHL--W--2.0-blue.svg)](/fpga/rtl/LICENSE)

FPGA neuromorphic elements, networks, processors, tooling, and software interfaces.
</div>

## 📝 Table of Contents

- [About](#about)
- [Getting Started](#getting_started)
- [Usage](#usage)
- [Built Using](#built_using)
- [Authors](#authors)
- [Acknowledgments](#acknowledgement)

## 🧐 About <a name = "about"></a>

This project is aimed at providing a simple and minimalist—but highly scalable—Field-Programmable Gate Array implementation of neuromorphic computing defined by Univeristy of Tennesse Knoxville (UTK) TENNLab research.

### Why?

The reasoning for this repository may seem unclear at first. TENNLab already maintains multiple neuroprocessors in HDL and more in simulation.
However, those approaches are optimized for ASIC implementation and thus incorporate the following primary drawbacks when implemented on FPGAs.

1. They cannot take advantage of the "FP" aspects of FPGAs. ASIC neuroprocessors must accomodate dynamic network sizes and topologies at **run-time**. This significantly increases the complexity and overhead of those designs.
1. ASICs have more granular logic building blocks, and designs targeting them are not optimized for FPGA logic elements (LEs). This often means that the designs have slower timing and more LE usage on FPGAs than in targeted implementations.

The ground-up FPGA implementation of neuromorphic networks and processors in this project allows for efficient utilization of hardware resources and communication bandwidth. A particular focus of this project is the "directive" versus "stream" spike processing which allows users to select the bandwidth usage paradigm that best suits their applications. This implementation does, however, have its own drawbacks compared to the ASIC design.

1. Relying on the EDA toolchain to map networks onto the FPGA means that it becomes a bottleneck for HWIL network training. As such, training is not a recommended application for this extension to the neuromorphic computing framework, compared to training in simulations or on ASIC implementations.
1. Dynamic network interchanges require either writing a new bitstream (time sacrifice) or increasing utilization to host multiple networks in fabric at once (area sacrifice). However, considering how resource-efficient the neuromorphic networks in this implementation are, this implementation may still outperform the ASIC designs when hosting multiple networks in fabric.

### License

The licenses for both hardware and software are **weakly reciprocal**, meaning users of this project need not distribute their larger works under the same license, but the full source, **incuding modifications**, of the code included in this repository must be made available according to the license terms described below.

#### Software

Usage of software in this repository is to be consistent with the included [license](/LICENSE): [MPL](https://opensource.org/license/mpl-2-0/).

#### Hardware

Usage of hardware description sources in this repository is to be consistent with the included [license](/fpga/rtl/LICENSE): [CERN-OHL-W](https://opensource.org/license/cern-ohl-w/).

## 🏁 Getting Started <a name = "getting_started"></a>

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

The TENNLab Neuromorphic Framework only works on Unix-like systems. Vivado only works on x86-64 Windows and Linux Systems. By extension, only Linux systems on x86-64 processors are supported. This project has been tested on an Ubuntu 22.04 LTS system.

#### Simulations (optional)

Install any simulators you wish to use which are [compatible with cocotb](https://docs.cocotb.org/en/stable/simulator_support.html).

**NOTE:** This project uses valid SystemVerilog that is currently incompatible with Icarus (iverilog). As a consequence, we are currently only running testbenches with Verilator. Even there, compatibility between the simulator and cocotb can be fragile, so we are currently using v5.024.

If you wish to see waveform outputs from the sims, install gtkwave.

#### EDA Toolchains

The EDA toolchains you require will depend on which devices you are targetting. For example, the Basys3 board as configured so far in this repository, requires the Vivado software by AMD/Xilinx. Open-source toolchains are available but are not the primary focus of this project. Theoretically [any EDA tool compatible with Edalize](https://edalize.readthedocs.io/en/latest/edalize.html) can be used in this project.

#### Framework (required) <a name = "framework"></a>

First, clone the UTK TENNLab Neuromorphic Framework repository and enter it.

```bash
git clone git clone git@bitbucket.org:neuromorphic-utk/framework.git
cd framework/
```

It is recommended, but perhaps not mandatory, to create the environment according to the Framework documentation.

```bash
cat markdown/python.md
bash scripts/create_env.sh
source pyframework/bin/activate
```

Finally, install the `framework` python package.

```bash
pip install -e .
```

### Installing <a name = "installing"></a>

Clone this repository into the requisite location (tentatively `./fpga`).

```bash
git clone git@github.com:TENNLab-UTK/fpga.git ./fpga
cd fpga
```

Install the FPGA tools in editable mode. You can swap `[test,dev]` for `[test]` below to add the linting and formatting tools. **(zsh may require escaping the brackets!)**

```bash
pip install -e .[test]
```

## 🔧 Running the tests <a name = "tests"></a>

### Simulations

Running the simulations should be as simple as using pytest. `SIMS` is a colon-delimited list.

```bash
SIMS=verilator WAVES=1 pytest tb/
```

You can find the waveform files and open them all with gtkwave using the following command.

```bash
find tb -iname "*.fst" -exec sh -c "gtkwave {} >/dev/null 2>&1 &" \;
```

### Hardware Communications

You should verify your host can reliably communicate with the hardware over serial UART.
There is a built-in "loopback" test that attempts communicating with standard baud rates ascending from 115,200 baud.

Below is an example of using the loopback test for a Digilent Basys3 board. Your cdev path will depend on your machine, and make sure your user is in the `dialout` group or has other permissions to access it.

```bash
uart-loop basys3 /dev/ttyUSB1
```

If the passing baud rates do not match the [hardware configuration "database"](/fpga/config/targets.json) then it will prompt you to update the rates.
*It is particularly good to do this if some of the existing rates in the configuration do not pass when you run it.*

## 🎈 Usage <a name="usage"></a>

The API for using the FPGA neuroprocessor is extremely similar to the standard Framework API. This is an [example](/example.py) using a simple two-neuron network.

```python
import neuro
import fpga

net = neuro.Network()
net.read_from_file("networks/simple.txt")

proc = fpga.Processor("basys3", "/dev/ttyUSB1", "DIDO")
proc.load_network(net)

proc.apply_spikes([neuro.Spike(0, i, 9) for i in range(3)])
proc.run(6)
print(proc.output_last_fire(0))
```

Support for additional FPGA targets can be accomplished by adding entries to the [targets config file](fpga/config/targets.json) and an accompanying folder containing relevant files, e.g. the top-level module and contraints files.

### Creating Your Own Runtime Front-End

There a scenarios where using the Python API for processor runtime is not feasible or optimal. For those users who wish to still use the FPGA framework for building the networks and processors, but write a separate front-end to suit their platforms, this package includes a web-based interactive visualization for processor packets.

To run it, simply follow the instructions in [Framework (required)](#framework) and [Installing](#installing) and run the `packet-vis` command.

## ⛏️ Built Using <a name = "built_using"></a>

- [cocotb](https://www.cocotb.org) - HDL Testbench Framework
- [Edalize](https://github.com/olofk/edalize) - Python API for EDA Toolchains
- [Plotly Dash](https://dash.plotly.com/) & [Dash Bootstrap Components](https://dash-bootstrap-components.opensource.faculty.ai/) - Used in the Packet Visualization app.

## ✍️ Authors <a name = "authors"></a>

- [@keegandent](https://github.com/keegandent) - Idea & initial work

See also the list of [contributors](https://github.com/TENNLab-UTK/fpga/graphs/contributors) who participated in this project.

## 🎉 Acknowledgements <a name = "acknowledgement"></a>

- [UTK TENNLab](https://neuromorphic.eecs.utk.edu) researchers for the top-level API and funamental neromorphic processing behavior, including but not limited to:
    - Dr. James Plank
    - Dr. Catherine Schuman
    - Dr. Garrett Rose
    - Dr. Charles Rizzo
    - Bryson Gullett
- [@alexforencich](https://github.com/alexforencich) for great examples of designs using using cocotb as well as various AXI4-Stream components modified for use in this project
- [@WillGreen](https://github.com/WillGreen) for his amazing tutorials on [projectf.io](https://projectf.io/tutorials/)
