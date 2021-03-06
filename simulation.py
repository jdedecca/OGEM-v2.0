## Copyright 2017 João Gorenstein Dedecca

## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 3 of the
## License, or (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = """
Joao Gorenstein Dedecca
"""

__copyright__ = """
Copyright 2017 João Gorenstein Dedecca, GNU GPL 3
"""

import os, sys, logging, shutil,gc,psutil, time, csv
from OGEM import Period_Run, Network_Setup, Load_Parameters, Load_Data, Save_Parameters
import pandas as pd
import numpy as np
import pypsa
from pyutilib.services import TempfileManager
import tempfile, multiprocessing

class Logger(object):
    """" The Logger class allows for parallel output to the console and a log.dat file.
        Thanks to Triptych in http://stackoverflow.com/questions/616645/how-do-i-duplicate-sys-stdout-to-a-log-file-in-python
    """

    def __init__(self,simulation_name):
        self.terminal = sys.__stdout__
        self.log = open(os.path.join(os.getcwd(),"network",simulation_name,"log.dat"), "a",1)
        if os.path.isdir(r'/home/joaogd/OGEM/network'):
            #/home/joaogd/OGEM/network
            path = os.path.join(r"/home/joaogd/OGEM/network",simulation_name)
            if not os.path.exists(path):
                os.mkdir(path)
            self.log2 = open(os.path.join(path,"log.dat"), "a",1)

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        if hasattr(self, 'log2'):
            self.log2.write(message)

    def flush(self):
        pass

def main(run_name,path = None):
    """ Executes a single run of the exploratory model """

    # Format output.
    pd.set_option("max_rows", 50)
    pd.set_option("max_columns", 70)
    pd.set_option('display.width', 200)
    pd.options.display.float_format = '{:.2e}'.format

    logging.getLogger().setLevel(logging.WARNING) # Increase the logging thresholder for PyPSA

    parameters = Load_Parameters(run_name) # Load parameters since simulation name and other are already needed
    parameters['run_name'] = run_name

    # Increment path number to find a non-existing folder
    path = os.path.join(os.getcwd(), r"network",parameters['simulation_name'])

    while os.path.exists(path):
        parameters['simulation_name'] = parameters['simulation_name'][:-1] + str(int(parameters['simulation_name'][-1]) + 1)
        path = os.path.join(os.getcwd(), r"network", parameters['simulation_name'])

    print("Running {}".format(parameters["simulation_name"]))

    TempfileManager.tempdir = path  # Indicates temp directory, e.g. for solver files
    if multiprocessing.cpu_count() == 32:
        print('EenI HPC, setting temp path')
        tempfile.tempdir = path
    os.mkdir(path)

    # Back-up code version
    np.save(os.path.join(os.getcwd(), r"network", parameters['simulation_name'], 'parameters.npy'), parameters)
    for script in ['OGEM.py','simulation.py']:
        shutil.copy(script,path)

    for folder in ['pypsa']:
        shutil.copytree(folder,os.path.join(path,'pypsa'))

    # Create period results folders
    for period in range(parameters['periods']):
        period_path = os.path.join(os.getcwd(), r"network", parameters['simulation_name'],"p"+str(period))
        os.mkdir(period_path)

    if sys.gettrace() is None: # Only duplicate stream to log file if not in debugging mode.
        sys.stdout = Logger(parameters['simulation_name'])

    input_panel = Load_Data(run_name) # Loads setup data

    # The pathway dataframes contains the transmission and offshore wind expansion capacity for all periods
    expansion_pathway = pd.DataFrame()
    generator_pathway = pd.DataFrame()

    # Network setup
    branches_dataframe, network = Network_Setup(0, input_panel)

    # Main loop for expansion simulation.
    def Single_Period():
        parameters["period"] = period
        selected_expansions,selected_generators = Period_Run(period, network, branches_dataframe, input_panel)
        return selected_expansions.loc[:,["s_nom_opt"]].rename(columns = {"s_nom_opt":"period"+str(period)}),selected_generators.loc[:,["p_nom_opt"]].rename(columns = {"p_nom_opt":"period"+str(period)})

    for period in range(parameters["periods"]):
        selected_expansions, selected_generators = Single_Period()
        expansion_pathway = expansion_pathway.join(selected_expansions,how='outer').fillna(0)
        generator_pathway = generator_pathway.join(selected_generators,how = 'outer').fillna(0)

    print('Runs finished')
    writer = pd.ExcelWriter(os.path.join(os.getcwd(), r"network", parameters['simulation_name'],"expansion_pathway.xlsx"))
    expansion_pathway.to_excel(writer,sheet_name = 'expansion_pathway')
    generator_pathway.to_excel(writer,sheet_name = 'generator_pathway')
    writer.save()

    parameters.pop('branch_parameters')
    np.save(os.path.join(path,'parameters.npy'),parameters)
    with open(os.path.join(path,'parameters.csv'), 'w') as f:
        w = csv.DictWriter(f, parameters.keys())
        w.writeheader()
        w.writerow(parameters)

    if sys.gettrace() == None:
        sys.stdout.log.close() #Close log.dat file if not in debugging mode.

if __name__=='__main__':
    main()