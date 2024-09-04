import sys
import os
import argparse
import random
import subprocess
import json
import numpy as np


SUPPORTED_PROCESSORS = ["risp"]
MAX_SIM_TIME = 5000
MAX_NUM_SIM_TIMES = 1000
PROB_INPUT_AS_TIMESTEP = 0.1


# Randomly generate inputs to SNN in form of processor tool commands, write processor tool commands out to a file, simulate SNN with processor toool command inputs, and write out processor tool command outputs to a file
def gen_inputs(net_json_path: str, framework_path: str, output_proc_tool_cmds_path: str, num_sim_times: int, sim_time: int, proc_tool_output_times_path: str) -> None:

    # Error check path to the network JSON file
    net_path = net_json_path
    if(not os.path.exists(net_path)):
        raise FileNotFoundError("ERROR: Could not find any network JSON file at the path " + net_path)

    # Get network JSON from the network JSON file
    with open(net_path, 'r') as file:
        net_json = json.load(file)

    # Ensure network has a non-empty array of neurons
    if("Nodes" not in net_json):
        raise AttributeError("ERROR: Could not find Nodes in the given network")
    if(not isinstance(net_json["Nodes"], list) or len(net_json["Nodes"]) == 0):
        raise ValueError("ERROR: Nodes must be a non-empty array of nodes in the given network")
    
    # Ensure network has non-empty array of input neuron IDs
    if("Inputs" not in net_json):
        raise AttributeError("ERROR: Could not find Inputs in the given network")
    if(not isinstance(net_json["Inputs"], list) or len(net_json["Inputs"]) == 0):
        raise ValueError("ERROR: Inputs must be a non-empty array of node IDs in the given network")

    # Ensure the network is targetting a valid specific processor
    if("Associated_Data" not in net_json):
        raise AttributeError("ERROR: Given network is missing Associated_Data")
    if("other" not in net_json["Associated_Data"]):
        raise AttributeError("ERROR: Given network is missing the other field in its Associated_Data")
    if("proc_name" not in net_json["Associated_Data"]["other"]):
        raise AttributeError("ERROR: Given network is missing the proc_name field in its Associated_Data, other")
    if(net_json["Associated_Data"]["other"]["proc_name"] not in SUPPORTED_PROCESSORS):
        raise ValueError("ERROR: Given network's processor, " + str(net_json["Associated_Data"]["other"]["proc_name"]) + " is not supported")
    proc_name = net_json["Associated_Data"]["other"]["proc_name"]

    # Build set of all neuron IDs
    neuron_ids = set()
    for node in net_json["Nodes"]:

        # Ensure every node has an integer ID
        if("id" not in node):
            raise AttributeError("ERROR: Node in given network does not have an ID")
        if(not isinstance(node["id"], int)):
            raise ValueError("ERROR: Node ID=" + str(node["id"] + " is not an integer in the given network"))
        
        neuron_ids.add(node["id"])

    # Build list of all input neuron IDs
    input_neuron_ids = []
    for neuron_id in net_json["Inputs"]:

        # Ensure input neuron ID corresponds to a neuron in the Nodes array
        if(neuron_id not in neuron_ids):
            raise ValueError("ERROR: Neuron with input ID " + str(neuron_id) + " is in the Inputs array but not in the Nodes array in the given network")

        input_neuron_ids.append(neuron_id)

    # Execute the appropriate processor tool binary if it exists
    proc_tool_path = os.path.join(framework_path,"cpp-apps","bin","processor_tool_"+proc_name)
    if(not os.path.exists(proc_tool_path)):
        raise FileNotFoundError("ERROR: Could not find a processor tool at the path " + proc_tool_path)
    proctool = subprocess.Popen([proc_tool_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # Generate random processor tool commands and write them to the output file and to the processor tool stdin 
    with open(output_proc_tool_cmds_path, 'w') as proc_tool_cmds_file:

        # In processor tool, make processor and load SNN
        ml_cmd_str = f"ML {net_path}\n"
        proc_tool_cmds_file.write(ml_cmd_str)
        proctool.stdin.write(ml_cmd_str.encode())
        proctool.stdin.flush()

        for sim_time_ind in range(num_sim_times):

            # Randomly generate set of apply spike commands for each timestep
            for timestep in range(sim_time):

                # Sample from binomial distribution to determine how many input neurons will receive input spikes this timestep
                num_as_cmds = np.random.binomial(len(input_neuron_ids), PROB_INPUT_AS_TIMESTEP)

                # Randomly choose which input neurons will receive input spikes this timestep
                as_neuron_ids = np.random.choice(input_neuron_ids, num_as_cmds, replace=False)

                # Generate AS commands for every input neuron that gets an input spike this timestep
                for as_neuron_id in as_neuron_ids:
                    as_cmd_str = f"AS {as_neuron_id} {timestep} 1\n"
                    proc_tool_cmds_file.write(as_cmd_str)
                    proctool.stdin.write(as_cmd_str.encode())
                    proctool.stdin.flush()

            # Run processor for sim_time timesteps
            run_cmd_str = f"RUN {sim_time}\n"
            proc_tool_cmds_file.write(run_cmd_str)
            proctool.stdin.write(run_cmd_str.encode())
            proctool.stdin.flush()

            # Get output neuron fire times for the sim_time
            ot_cmd_str = "OT\n"
            proc_tool_cmds_file.write(ot_cmd_str)
            proctool.stdin.write(ot_cmd_str.encode())
            proctool.stdin.flush()

            # Reset network activity between sim_times (independent steps)
            if(sim_time_ind < num_sim_times-1):
                ca_cmd_str = "CA\n"
                proc_tool_cmds_file.write(ca_cmd_str)
                proctool.stdin.write(ca_cmd_str.encode())
                proctool.stdin.flush()

    # Send data writen to stdin to processor tool process
    proctool_stdout, _ = proctool.communicate()

    # Write output of processor tool to output file
    with open(proc_tool_output_times_path, 'wb') as proc_tool_output_times_file:
        proc_tool_output_times_file.write(proctool_stdout)

    # Stop processor tool process
    proctool.terminate()


if __name__ == '__main__':
    
    # Setup command line arguments
    parser = argparse.ArgumentParser(description="Generate random processor tool commands (inputs) for a given SNN and get output from framework simulating the SNN with these inputs.")
    parser.add_argument("--net_json_path", "-n", type=str, required=True, help="Network JSON file path")
    parser.add_argument("--output_proc_tool_cmds_path", "-p", type=str, required=True, help="Path to write generated processor tool commands")
    parser.add_argument("--proc_tool_output_times_path", "-sr", type=str, required=True, help="Path to write processor tool output fire times after running SNN with generated processor tool commands")
    parser.add_argument("--framework_path", "-f", type=str, required=True, help="Path to the TENNLab framework directory")
    parser.add_argument("--sim_time", "-st", type=int, default=100, choices=range(1, MAX_SIM_TIME+1), help="Number of timesteps to run processor between every output fire times output")
    parser.add_argument("--num_sim_times", "-nst", type=int, default=10, choices=range(1, MAX_NUM_SIM_TIMES+1), help="Number of sim_times to run the network")
    parser.add_argument("--seed", "-s", type=int, default=0, help="Seed for random number generation")
    args = parser.parse_args()

    # Seed random number generator
    np.random.seed(args.seed)
    random.seed(args.seed)

    gen_inputs(args.net_json_path, args.framework_path, args.output_proc_tool_cmds_path, args.num_sim_times, args.sim_time, args.proc_tool_output_times_path)