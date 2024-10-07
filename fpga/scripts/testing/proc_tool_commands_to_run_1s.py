

def proc_tools_commands_to_run_1s(proc_tool_commands_path: str):
    time_node_ids = []
    with open(proc_tool_commands_path, 'r') as f:
        for line in f:
            if "AS" in line:
                proc_tool_cmd_list = line.split()
                node_id = int(proc_tool_cmd_list[1])
                time = int(proc_tool_cmd_list[2])
                val = int(proc_tool_cmd_list[3])

                if time > len(time_node_ids)-1:
                    for _ in range(len(time_node_ids), time+1):
                        time_node_ids.append([])

                time_node_ids[time].append((node_id, val))

            elif "CA" in line:
                time_node_ids.clear()
                print("CA")

            elif "RUN" in line:
                proc_tool_cmd_list = line.split()
                run_time = int(proc_tool_cmd_list[1]) - 1

                if run_time > len(time_node_ids)-1:
                    for _ in range(len(time_node_ids), run_time+1):
                        time_node_ids.append([])

                for t in range(run_time+1):
                    for node_id, val in time_node_ids[t]:
                        print("AS " + str(node_id) + " 0 " + str(val))
                    print("RUN 1")
                    print("OT")

                for j in range(len(time_node_ids)):
                    if j > run_time:
                        time_node_ids[j-run_time-1] = time_node_ids[j]

                del time_node_ids[-(run_time+1):]

if __name__ == '__main__':
    proc_tools_commands_to_run_1s("/home/bryson/Documents/TENNLab/framework/fpga/fpga/scripts/testing/proc_tool_commands.txt")