import os
import subprocess
import random
import json
import argparse
import rustworkx as rx
import numpy as np
import pathlib as pl

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


# Generate network tool commands to create a randomly generated network and write them to a file
def gen_rand_network_tool_commands(template_net_json_path: str, num_neurons: int, num_synapses: int, seed: int, num_inputs: int, num_outputs: int, network_tool_commands_path: str, net_json_path: str) -> None:

    # Seed random number generator
    np.random.seed(seed)
    random.seed(seed)

    # Error check path to the template network JSON file
    if(not os.path.exists(template_net_json_path)):
        raise FileNotFoundError("ERROR: Could not find any network JSON file at the path " + template_net_json_path)

    # Generate a random directed graph with no self-loops
    rand_net_graph = rx.directed_gnm_random_graph(num_neurons, num_synapses, seed)

    with open(network_tool_commands_path, "w") as network_tool_commands_f:

        # Load network template into the network tool
        network_tool_commands_f.write(f'SEED {seed}\n')
        network_tool_commands_f.write(f'FJ {template_net_json_path}\n')

        # Add nodes with random IDs and random properties using AN and RNP commands
        neuron_ids = np.random.choice(num_neurons*10, num_neurons, replace=False)
        for neuron_id in neuron_ids:
            network_tool_commands_f.write(f'AN {neuron_id}\n')
            network_tool_commands_f.write(f'RNP {neuron_id}\n')
            
        # Identify randomized input nodes using AI command
        input_neuron_ids = np.random.choice(neuron_ids, num_inputs, replace=False)
        for input_neuron_id in input_neuron_ids:
            network_tool_commands_f.write(f'AI {input_neuron_id}\n')
            
        # Identify randomized output nodes using AO command
        output_neuron_ids = np.random.choice(neuron_ids, num_outputs, replace=False)
        for output_neuron_id in output_neuron_ids:
            network_tool_commands_f.write(f'AO {output_neuron_id}\n')
            
        # Connect nodes randomly while maintaining mean edge property   
        for edge in rand_net_graph.edge_list():
            from_neuron = edge[0]
            to_neuron = edge[1]

            # Randomly replace an edge with a self edge for randomly generated graph
            if(random.randint(0,num_neurons-1) == from_neuron):
                to_neuron = from_neuron

            # Connect nodes using the AE command
            network_tool_commands_f.write(f'AE {neuron_ids[from_neuron]} {neuron_ids[to_neuron]}\n')
            network_tool_commands_f.write(f'REP {neuron_ids[from_neuron]} {neuron_ids[to_neuron]}\n')
            
        network_tool_commands_f.write(f'TJ {net_json_path}\n')


def gen_network_from_network_tool_commands(network_tool_commands_path: str, framework_path: str, net_json_path: str) -> None:

    # Execute the network_tool binary if it exists
    network_tool_path = os.path.join(framework_path, "bin", "network_tool")
    if(not os.path.exists(network_tool_path)):
        raise FileNotFoundError("ERROR: Could not find the network tool at the path " + network_tool_path)

    # Run network tool commands in network tool and write freshly generated random network json to output file
    with open(net_json_path, 'w') as net_json_f:
        with open(network_tool_commands_path, 'r') as net_tool_commands_f:
            subprocess.run([network_tool_path], stdin=net_tool_commands_f, stdout=net_json_f, shell=True)


# Generate a network randomly and write it to a file
def generate_network(template_net_json_path: str, framework_path: str, num_neurons: int, num_synapses: int, seed: int, num_inputs: int, num_outputs: int, network_tool_commands_path: str, net_json_path: str) -> None:
    try:
        error_check_args(num_inputs, num_neurons, num_outputs, num_synapses)
        gen_rand_network_tool_commands(template_net_json_path, num_neurons, num_synapses, seed, num_inputs, num_outputs, network_tool_commands_path, net_json_path)
        gen_network_from_network_tool_commands(network_tool_commands_path, framework_path, net_json_path)
    except BaseException as e:
        raise BaseException("Network generation threw an exception") from e


if __name__ == '__main__':
    
    # Setup command line arguments
    parser = argparse.ArgumentParser(description="Generate a single random network with a variety of parameters.")
    parser.add_argument("--num_neurons", "-n", type=int, default=10, choices=range(1, MAX_NUM_NEURONS+1), help="Total number of neurons network should have")
    parser.add_argument("--num_synapses", "-e", type=int, default=20, choices=range(1, MAX_NUM_SYNAPSES+1), help="Total number of synapses network should have")
    parser.add_argument("--num_inputs", "-i", type=int, default=4, choices=range(1, MAX_NUM_NEURONS+1), help="Number of input neurons network should have")
    parser.add_argument("--num_outputs", "-o", type=int, default=4, choices=range(1, MAX_NUM_NEURONS+1), help="Number of output neurons network should have")
    parser.add_argument("--template_net_json_path", "-t", type=str, required=True, help="Path to template network JSON file (generated from the processor tool using the EMPTYNET command)")
    parser.add_argument("--network_tool_commands_path", "-c", type=str, required=True, help="Path to write generated network tool commands")
    parser.add_argument("--net_json_path", "-j", type=str, required=True, help="Path to write generated network JSON file")
    parser.add_argument("--framework_path", "-f", type=str, required=True, help="Path to the TENNLab framework directory")
    parser.add_argument("--seed", "-s", type=int, default=0, help="Seed for random number generation")
    args = parser.parse_args()

    generate_network(args.template_net_json_path, args.framework_path, args.num_neurons, args.num_synapses, args.seed, args.num_inputs, args.num_outputs, args.network_tool_commands_path, args.net_json_path)