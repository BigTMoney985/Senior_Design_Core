# Senior Design reactor core
This is the OpenMC model for team 7 in OpenMC. To change iterable variables, please go into the global_vars.py file and update any pertinent variables. When you want to get all your xmls (the stuff you use to run the model) please run main.py. If you have any questions, contact tommywilliams@mst.edu or just send me a teams message and I'll try and help out.

## USAGE
To run the model, simply run ./main.py
The arguments are as follows:

--run-mode (-r): 'plot' or 'model' (Default: 'model')
This will determine the specific run mode, plot will generate a plot image and a plot with a 
material legend of the model geometry. the "model" option will generate a model.xml file with all
tallies and run settings and may run it.

--compute-choice (-c): 'local' or 'hpc' (Default: 'hpc')
This will determine if openmc.run() is called after running the model option. If 'hpc' is selected, 
the model will not be ran immediately and you will have to do either a mpiexec command or run openmc in 
the terminal. Using 'local' will call openmc.run() immediately following the generation of the model.xml file.

EXAMPLE USAGE:
```console
t-money@chudlaptop:~/Senior_Design_Core$ ./main.py --run-mode model -c local

# This will generate a model xml file and run the file immediately


t-money@chudlaptop:~/Senior_Design_Core$ ./main.py --run-mode plot

# This will run the plotter, note that the compute choice is not needed for this selection.
# HPC is the default selection, however.
```

## TODO

- [x] Add all the iterables into the global_vars.py area (such as fuel choice)
- [ ] Maybe make an input yaml?
- [x] Get the ring fully made for the fuel elements.
- [ ] Add a separate plotter.py file
- [x] Add heights to fuel and water
- [x] Add proper material definitions to the control rods
- [x] Add a function to get the material dict to get rid of the errors
- [x] Add separate water cells so we don't have weird not stuff
- [ ] Update rod withdrawal algorithm so it makes sense.
- [x] Reduce the ratio of r_in to r_out to less than 2.16
- [x] Actually make three-lobed core
- [ ] Separate control blades and be distance into two vars.
- [ ] Explain how the repo actually works
- [x] Make inner blades aluminum and not Be
- [x] Implement an argparse for plot or xml creation
- [ ] fix the env variable for chain files n shit...