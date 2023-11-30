import pandas as pd
import numpy as np
from functools import partial
from scipy.ndimage.filters import median_filter
from math import floor, ceil

# Partial for simplifying repeat median filter calls
medfilt = partial(median_filter, mode='constant')


def noise_std(x: np.ndarray, filter_length: int = 31) -> float:
    """Compute a robust estimation of the standard deviation of the
    noise in a signal `x`. The noise is left after subtracting
    a rolling median filter value from the signal. Outliers are removed
    in 2 stages to make the estimation robust.
    Parameters
    ----------
    x: np.ndarray
        1d array of signal (perhaps with noise)
    filter_length: int (default=31)
        Length of the median filter to compute a rolling baseline,
        which is subtracted from the signal `x`. Must be an odd number.
    Returns
    -------
    float:
        A robust estimation of the standard deviation of the noise.
        If any valurs of `x` are NaN, returns NaN.
    """
    if any(np.isnan(x)):
        return np.NaN
    noise = x - medfilt(x, filter_length)
    # first pass removing positive outlier peaks

    # (method is fragile if possibly have 0 as min)
    filtered_noise_0 = noise[noise < (1.5 * np.abs(noise.min()))]
    rstd = robust_std(filtered_noise_0)
    # second pass removing remaining pos and neg peak outliers
    filtered_noise_1 = filtered_noise_0[abs(filtered_noise_0) < (2.5 * rstd)]
    return robust_std(filtered_noise_1)


def robust_std(x: np.ndarray) -> float:
    """Compute the median absolute deviation assuming normally
    distributed data. This is a robust statistic.
    Parameters
    ----------
    x: np.ndarray
        A numeric, 1d numpy array
    Returns
    -------
    float:
        A robust estimation of standard deviation.
    Notes
    -----
    If `x` is an empty array or contains any NaNs, will return NaN.
    """
    mad = np.median(np.abs(x - np.median(x)))
    return 1.4826*mad

def compute_dff_trace(corrected_fluorescence_trace: np.ndarray,
                      long_filter_length: int,
                      short_filter_length: int
                      ):
    """
    Compute the "delta F over F" from the fluorescence trace.
    Uses configurable length median filters to compute baseline for
    baseline-subtraction and short timescale detrending.
    Returns the artifact-corrected and detrended dF/F, along with
    additional metadata for QA: the estimated standard deviation of
    the noise ("sigma_dff") and the number of frames where the
    computed baseline was less than the standard deviation of the noise.
    Parameters
    ----------
    corrected_fluorescence_trace: np.array
        1d numpy array of the neuropil-corrected fluorescence trace
    long_filter_length: int
        Length (in number of elements) of the long median filter used
        to compute a rolling baseline. Must be an odd number.
    short_filter_length: int (default=31)
        Length (in number of elements) for a short median filter used
        for short timescale detrending.
    Returns
    -------
    np.ndarray:
        The "dff" (delta_fluorescence/fluorescence) trace, 1d np.array
    float:
        The estimated standard deviation of the noise in the dff trace
    int:
        Number of frames where the baseline (long timescape median
        filter) was less than or equal to the estimated noise of the
        `corrected_fluorescence_trace`.
    """
    sigma_f = noise_std(corrected_fluorescence_trace, short_filter_length)

    # Long timescale median filter for baseline subtraction
    baseline = medfilt(corrected_fluorescence_trace, long_filter_length)
    dff = ((corrected_fluorescence_trace - baseline)
           / np.maximum(baseline, sigma_f))
    num_small_baseline_frames = np.sum(baseline <= sigma_f)

    sigma_dff = noise_std(dff, short_filter_length)

    # Short timescale detrending
    filtered_dff = medfilt(dff, short_filter_length)
    # Constrain to 2.5x the estimated noise of dff
    filtered_dff = np.minimum(filtered_dff, 2.5*sigma_dff)

    detrended_dff = dff - filtered_dff

    return detrended_dff, sigma_dff, num_small_baseline_frames


def dff_calc(file, long_filter=6):
    # long_filter must be an odd integer number --> adjustment
    if int(long_filter) % 2 == 0:
        if floor(long_filter) % 2 == 0:
            long_filter = ceil(long_filter)
        else:
            long_filter = floor(long_filter)
    else:
        long_filter = int(long_filter)

    traces=pd.read_csv(file, sep="\t", header=None).T.to_numpy()

    traces_mod = []
    for trace in traces:

        detrended_dff, sigma_dff, num_small_baseline_frames = compute_dff_trace(trace,
                                                                                long_filter_length=long_filter,
                                                                                short_filter_length=101)

        traces_mod.append(detrended_dff)
    if file.endswith(".txt"):
        pd.DataFrame(traces_mod).T.to_csv(file.replace(".txt", "_df_f.tsv"), sep="\t", header=None, index=False)

    elif file.endswith(".tsv"):
        pd.DataFrame(traces_mod).T.to_csv(file.replace(".tsv", "_df_f.tsv"), sep="\t", header=None, index=False)
    else:
        print("wrong file format")