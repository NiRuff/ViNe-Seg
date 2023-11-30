# standard python packages
import os, warnings
import glob
import numpy as np
import scipy.io as sio
import matplotlib.pyplot as plt
import pandas as pd

# cascade2p packages, imported from the downloaded Github repository
from .cascade2p import cascade # local folder
from .cascade2p.utils import plot_dFF_traces, plot_noise_level_distribution, plot_noise_matched_ground_truth
from .cascade2p.utils_discrete_spikes import infer_discrete_spikes

import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QLabel, QWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, \
    QTableView, QHBoxLayout, QProgressBar, QAbstractItemView, QPushButton
import os
import json
import urllib.request
import shutil

# @markdown ΔF/F traces must be saved as \*.npy-files (for Python) or \*.mat-files (for Matlab/Python) as a single large matrix named **`dF_traces`** (neurons x time). ΔF/F values of the input should be numeric, not in percent (e.g. 0.5 instead of 50%). For different input formats, the code in this box can be modified (it\'s not difficult).

def load_neurons_x_time(file_path):
    """Custom method to load data as 2d array with shape (neurons, nr_timepoints)"""

    if file_path.endswith('.mat'):
        traces = sio.loadmat(file_path)['dF_traces']

    elif file_path.endswith('.npy'):
        traces = np.load(file_path, allow_pickle=True)
        # if saved data was a dictionary packed into a numpy array (MATLAB style): unpack
        if traces.shape == ():
            traces = traces.item()['dF_traces']

    else:
        raise Exception('This function only supports .mat or .npy files.')

    print('Traces standard deviation:', np.nanmean(np.nanstd(traces, axis=1)))
    if np.nanmedian(np.nanstd(traces, axis=1)) > 2:
        print('Fluctuations in dF/F are very large, probably dF/F is given in percent. Traces are divided by 100.')
        return traces / 100
    else:
        return traces

def run_CASCADE(dff_path, model_name, pb):


    pb.setValue(1)

    traces = pd.read_csv(dff_path, sep="\t", header=None).T.to_numpy()

    if np.nanmedian(np.nanstd(traces, axis=1)) > 2:
        print('Fluctuations in dF/F are very large, probably dF/F is given in percent. Traces are divided by 100.')
        traces = traces / 100

    warnings.filterwarnings('ignore')

    total_array_size = traces.itemsize * traces.size * 64 / 1e9

    # If the expected array size is too large for the Colab Notebook, split up for processing
    if total_array_size < 10:
        spike_prob = cascade.predict(model_name, traces)
        pb.setValue(10)

    # Will only be used for large input arrays (long recordings or many neurons)
    else:

        print("Split analysis into chunks in order to fit into memory.")

        # pre-allocate array for results
        spike_prob = np.zeros((traces.shape))
        # nb of neurons and nb of chuncks
        nb_neurons = traces.shape[0]
        nb_chunks = np.int(np.ceil(total_array_size / 10))

        chunks = np.array_split(range(nb_neurons), nb_chunks)
        # infer spike rates independently for each chunk
        for part_array in range(nb_chunks):
            pb.setValue(pb.Value+1)
            spike_prob[chunks[part_array], :] = cascade.predict(model_name, traces[chunks[part_array], :])

    discrete_approximation, spike_time_estimates = infer_discrete_spikes(spike_prob, model_name)

    folder = os.path.dirname(dff_path)
    save_path = os.path.join(folder, 'discrete_spikes_' + os.path.basename(dff_path))
    pd.DataFrame(spike_time_estimates).to_csv(save_path)

    save_path = os.path.join(folder, 'spike_probs_' + os.path.basename(dff_path))
    pd.DataFrame(spike_prob).to_csv(save_path)
