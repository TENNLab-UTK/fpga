def dma_inp_buffer_packetize(dma_buffer_path: str):
    with open(dma_buffer_path, 'r') as f:
        for line in f:
            pkt_list = []
            num_chars_in_pkt = 0
            for c in reversed(line.strip().replace("buffer being sent via dma: 0x", "")):
                pkt_list.insert(0, c)
                num_chars_in_pkt = (num_chars_in_pkt + 1) % 16
                if num_chars_in_pkt == 0:
                    print("".join(pkt_list))
                    pkt_list.clear()

def dma_out_buffer_packetize(dma_buffer_path: str):
    with open(dma_buffer_path, 'r') as f:
        for line in f:
            pkt_list = []
            num_chars_in_pkt = 0
            for c in reversed(line.strip().replace("buffer being received via dma: 0x", "")):
                pkt_list.insert(0, c)
                num_chars_in_pkt = (num_chars_in_pkt + 1) % 2
                if num_chars_in_pkt == 0:
                    pkt = "".join(pkt_list)
                    if (int(pkt, 16) >> 7) & 1 == 1:
                        print(pkt)
                    pkt_list.clear()

if __name__ == '__main__':
    # dma_inp_buffer_packetize("tmp_buffer_incorrect_original.txt")
    dma_out_buffer_packetize("tmp_buffer_incorrect_original.txt")