DBSCAN example

Here's a example with DBSCAN that should be pretty meaty.

The file `dbscan-20-4-5.txt` is a dbscan network for any grid with 20 rows.  It's of a decent
size:

- Nodes:        420
- Edges:       3260
- Inputs:        20
- Outputs:       40

In the directory `grids`, there are 100 input grids for testing that are 20x100.
They are sparse (5% full).

In the directory `inputs`, there are 100 files containing the 'AS' (apply_spikes) commands
for the grids.  There are roughly 100 spikes per file.

I have created two benchmarking inputs from these:

1. input_112.txt concatenates all 100 input files, and between each puts a RUN 112 call.
That runs each DBSCAN network in succession.

2. input_all.txt successively adds 112 to the spike time of each input file, and then at the
   end does `RUN 11200`.  So -- all of the inputs at one time, and then one big RUN call.
