import json
from fpga._math import clog2, width_bits_to_bytes, width_nearest_byte

def proc_tool_cmds_to_inp_pkts(net_path: str, proc_tool_commands_path: str):
    
    net_json = {}
    with open(net_path, 'r') as file:
        net_json = json.load(file)

    node_id_to_inp_ind = {}
    i = 0
    for node_id in net_json["Inputs"]:
        node_id_to_inp_ind[int(node_id)] = i
        i += 1

    min_weight = net_json["Associated_Data"]["proc_params"]["min_weight"]
    max_weight = net_json["Associated_Data"]["proc_params"]["max_weight"]
    run_time_inclusive = net_json["Associated_Data"]["proc_params"]["run_time_inclusive"]

    net_charge_width_bits = clog2((max(abs(max_weight+1), abs(min_weight)))) + 1
    spk_width = len(node_id_to_inp_ind) * net_charge_width_bits
    run_width = width_nearest_byte(spk_width + 1) - 1
    inp_pkt_width_bytes = 1 << clog2(width_bits_to_bytes(1 + max(spk_width, run_width)))

    bin_pkts_strs_lists = []

    i = 0
    with open(proc_tool_commands_path, 'r') as proc_tool_f:
        for proc_tool_cmd in proc_tool_f:

            if "AS" in proc_tool_cmd:
                proc_tool_cmd_list = proc_tool_cmd.split()
                inp_ind = node_id_to_inp_ind[int(proc_tool_cmd_list[1])]
                time = int(proc_tool_cmd_list[2])
                val = int(proc_tool_cmd_list[3])

                if time > len(bin_pkts_strs_lists)-1:
                    for _ in range(len(bin_pkts_strs_lists), time+1):
                        bin_pkts_strs_lists.append(["0" for _ in range(inp_pkt_width_bytes*8)])

                start_bit = inp_pkt_width_bytes*8 - inp_ind*net_charge_width_bits - net_charge_width_bits - 1
                for j in range(net_charge_width_bits):
                    if (val>>j) & 1 == 1:
                        bin_pkts_strs_lists[time][start_bit+j] = "1"
                    

            elif "CA" in proc_tool_cmd:
                bin_pkts_strs_lists.clear()
                bin_pkt_str = "1"
                for _ in range(inp_pkt_width_bytes*8-1):
                    bin_pkt_str += "0"
                print("inp_data[" + str(i) + "] = " + str(inp_pkt_width_bytes*8) + "'b" + str(bin_pkt_str) + ";")
                i += 1

            elif "RUN" in proc_tool_cmd:
                proc_tool_cmd_list = proc_tool_cmd.split()
                run_time = int(proc_tool_cmd_list[1])
                if not run_time_inclusive:
                    run_time = run_time - 1

                if run_time > len(bin_pkts_strs_lists)-1:
                    for _ in range(len(bin_pkts_strs_lists), run_time+1):
                        bin_pkts_strs_lists.append(["0" for _ in range(inp_pkt_width_bytes*8)])

                for t in range(run_time+1):
                    bin_pkt_str_list = bin_pkts_strs_lists[t]
                    bin_pkt_str = "".join(bin_pkt_str_list)[::-1]
                    print("inp_data[" + str(i) + "] = " + str(inp_pkt_width_bytes*8) + "'b" + str(bin_pkt_str) + ";")
                    i += 1

                for j in range(len(bin_pkts_strs_lists)):
                    if j > run_time:
                        bin_pkts_strs_lists[j-run_time-1] = bin_pkts_strs_lists[j]

                del bin_pkts_strs_lists[-(run_time+1):]


if __name__ == '__main__':
    proc_tool_cmds_to_inp_pkts("/home/bryson/Documents/TENNLab/framework/fpga/fpga/scripts/testing/test_8/net.json", "/home/bryson/Documents/TENNLab/framework/fpga/fpga/scripts/testing/proc_tool_commands.txt")