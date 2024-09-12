import os
import subprocess
import random
import json
import argparse
import rustworkx as rx
import numpy as np


MAX_NUM_NEURONS = 1000
MAX_NUM_SYNAPSES = 1000


# Error check network generation arguments
def error_check_args(num_inputs: int, num_neurons: int, num_outputs: int, num_synapses: int) -> None:
    if(num_inputs > num_neurons):
        raise ValueError("ERROR: Number of input neurons cannot exceed total number of neurons")
    
    if(num_outputs > num_neurons):
        raise ValueError("ERROR: Number of output neurons cannot exceed total number of neurons")

    # if(num_inputs + num_outputs > num_neurons):
    #     raise ValueError("ERROR: Number of input + output neurons cannot exceed total number of neurons")
    
    if(num_synapses > num_neurons * (num_neurons - 1)):
        raise ValueError("ERROR: Too many synapses for random network generation (max number is num_neurons(num_neurons-1))")


# Generate a network randomly and write it to a file after arguments have already been error checked
def make_network(template_net_json_path: str, framework_path: str, num_neurons: int, num_synapses: int, seed: int, num_inputs: int, num_outputs: int, output_net_json_path: str) -> None:

    # Seed random number generator
    np.random.seed(seed)
    random.seed(seed)

    # Error check path to the template network JSON file
    template_net_path = template_net_json_path
    if(not os.path.exists(template_net_path)):
        raise FileNotFoundError("ERROR: Could not find any network JSON file at the path " + template_net_path)

    # Get network JSON from the template network JSON file
    with open(template_net_path, 'r') as file:
        net_json = json.load(file)

    # Clear the desired properties
    net_json["Nodes"] = []
    net_json["Edges"] = []
    net_json["Inputs"] = []
    net_json["Outputs"] = []

    # Convert the cleared JSON network to a string and write it back to a temporary file
    net_json_str = json.dumps(net_json, indent=2)
    with open("tmp_net.json", 'w') as file:
        file.write(net_json_str)

    # Execute the network_tool binary if it exists
    network_tool_path = os.path.join(framework_path, "bin", "network_tool")
    if(not os.path.exists(network_tool_path)):
        raise FileNotFoundError("ERROR: Could not find the network tool at the path " + network_tool_path)
    networktool = subprocess.Popen([network_tool_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # Load network template into the network tool
    networktool.stdin.write(f'SEED {seed}\n'.encode())
    networktool.stdin.write(f'FJ tmp_net.json\n'.encode())
    networktool.stdin.flush()

    # Generate a random directed graph with no self-loops
    rand_net_graph = rx.directed_gnm_random_graph(num_neurons, num_synapses, seed)

    # Add nodes with random IDs and random properties using AN and RNP commands
    neuron_ids = np.random.choice(num_neurons*10, num_neurons, replace=False)
    for neuron_id in neuron_ids:
        networktool.stdin.write(f'AN {neuron_id}\n'.encode())
        networktool.stdin.write(f'RNP {neuron_id}\n'.encode())
        networktool.stdin.flush()

    # Identify randomized input nodes using AI command
    input_neuron_ids = np.random.choice(neuron_ids, num_inputs, replace=False)
    for input_neuron_id in input_neuron_ids:
        networktool.stdin.write(f'AI {input_neuron_id}\n'.encode())
        networktool.stdin.flush()

    # Identify randomized output nodes using AO command
    output_neuron_ids = np.random.choice(neuron_ids, num_outputs, replace=False)
    for output_neuron_id in output_neuron_ids:
        networktool.stdin.write(f'AO {output_neuron_id}\n'.encode())
        networktool.stdin.flush()

    # Connect nodes randomly while maintaining mean edge property   
    for edge in rand_net_graph.edge_list():
        from_neuron = edge[0]
        to_neuron = edge[1]

        # Randomly replace an edge with a self edge for randomly generated graph
        if(random.randint(0,num_neurons-1) == from_neuron):
            to_neuron = from_neuron

        # Connect nodes using the AE command
        networktool.stdin.write(f'AE {neuron_ids[from_neuron]} {neuron_ids[to_neuron]}\n'.encode())
        networktool.stdin.write(f'REP {neuron_ids[from_neuron]} {neuron_ids[to_neuron]}\n'.encode())
        networktool.stdin.flush()

    networktool.stdin.write(f'TJ {output_net_json_path}\n'.encode())
    networktool.stdin.flush()

    # Send data writen to stdin to network tool process
    networktool.communicate()

    # Stop network tool process
    networktool.terminate()

    # Remove temporary file created for network JSON template
    os.remove("tmp_net.json")


# Generate a network randomly and write it to a file
def generate_network(template_net_json_path: str, framework_path: str, num_neurons: int, num_synapses: int, seed: int, num_inputs: int, num_outputs: int, output_net_json_path: str) -> None:
    try:
        error_check_args(num_inputs, num_neurons, num_outputs, num_synapses)
        make_network(template_net_json_path, framework_path, num_neurons, num_synapses, seed, num_inputs, num_outputs, output_net_json_path)
    except BaseException as e:

        # Remove temporary network JSON file if it was created earlier
        try:
            os.remove("tmp_net.json")
        except OSError:
            pass

        raise BaseException("Network generation threw an exception") from e


if __name__ == '__main__':
    
    # Setup command line arguments
    parser = argparse.ArgumentParser(description="Generate a single random network with a variety of parameters.")
    parser.add_argument("--num_neurons", "-n", type=int, default=10, choices=range(1, MAX_NUM_NEURONS+1), help="Total number of neurons network should have")
    parser.add_argument("--num_synapses", "-e", type=int, default=20, choices=range(1, MAX_NUM_SYNAPSES+1), help="Total number of synapses network should have")
    parser.add_argument("--num_inputs", "-i", type=int, default=4, choices=range(1, MAX_NUM_NEURONS+1), help="Number of input neurons network should have")
    parser.add_argument("--num_outputs", "-o", type=int, default=4, choices=range(1, MAX_NUM_NEURONS+1), help="Number of output neurons network should have")
    parser.add_argument("--template_net_json_path", "-t", type=str, required=True, help="Path to template network JSON file (generated from the processor tool using the EMPTYNET command)")
    parser.add_argument("--output_net_json_path", "-j", type=str, required=True, help="Path to write generated network JSON file")
    parser.add_argument("--framework_path", "-f", type=str, required=True, help="Path to the TENNLab framework directory")
    parser.add_argument("--seed", "-s", type=int, default=0, help="Seed for random number generation")
    args = parser.parse_args()

    generate_network(args.template_net_json_path, args.framework_path, args.num_neurons, args.num_synapses, args.seed, args.num_inputs, args.num_outputs, args.output_net_json_path)