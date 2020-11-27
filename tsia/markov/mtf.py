import matplotlib.pyplot as plt
import numpy as np
from numba import njit, prange
from pyts.preprocessing.discretizer import KBinsDiscretizer

# Useful constants definition
MTF_N_BINS = 8
MTF_STRATEGY = 'quantile'
COLORMAP = 'jet'

def compute_mtf_statistics(mtf):
    """
    Extract statistics from the Markov transition fields passed as an argument.
    This function extract the mean and and standard deviation of the main
    diagonal of the transition field.
    
    PARAMS
    ======
        mtf: numpy.ndarray
            Numpy array containing a Markov transition field.
            
    RETURNS
    =======
        statistics (dict)
            Dictionnary containing the mean and standard deviation of the
            self-transition probabilities of the Markov transition fields
            (contained in the main diagonal)
    """
    avg_self_transition_prob = np.diag(mtf).mean()
    std_self_transition_prob = np.diag(mtf).std()

    statistics = {
        'Average self-transition prob': avg_self_transition_prob,
        'Std self-transition prob': std_self_transition_prob
    }
    
    return statistics
    
def discretize(timeseries, n_bins=MTF_N_BINS, strategy=MTF_STRATEGY):
    """
    Discretize a given time series into a certain number of bins.
    
    PARAMS
    ======
        timeseries: numpy.ndarray
            The time series data to discretize
        n_bins: int (default = 8)
            Number of bins to discretize the data into. Also known as the size
            of the alphabet.
        strategy: 'uniform', 'quantile' or 'normal' (default = 'quantile')
            Strategy used to define the widths of the bins:
            - 'uniform': All bins in each sample have identical widths
            - 'quantile': All bins in each sample have the same number of points
            - 'normal': Bin edges are quantiles from a standard normal 
                        distribution
            
    RETURNS
    =======
        X_binned: numpy.ndarray
            The binned signal
        bin_edges: list
            A list with all the bin edges
    """
    # Build a discretizer and discretize the signal passed as argument:
    discretizer = KBinsDiscretizer(n_bins=n_bins, strategy=strategy)
    X = timeseries.values.reshape(1, -1)
    X_binned = discretizer.fit_transform(X)[0]
    
    # Extract the bin edges computed during the discretization process:
    bin_edges = discretizer._compute_bins(X, 1, n_bins, strategy)
    bin_edges = np.hstack((timeseries.values.min(), 
                           bin_edges[0], 
                           timeseries.values.max()))
    
    return X_binned, bin_edges

@njit()
def markov_transition_matrix(X_binned):
    """
    Build a Markov transition matrix from a binned signal passed as an argument.
    
    PARAMS
    ======
        X_binned: numpy.ndarray
            An array with the bin number associated to each value of an 
            original time series.
        mtf_type: 'frequency' or 'probabilities'. Default = 'frequency'
            If the desired type is probabilities, the function will return the
            transition probabilities from a time step to the next. Otherwise,
            the methods will return the frequencies (transition counts from
            one column to the next).
    
    RETURNS
    =======
        X_mtm: numpy.ndarray
            The Markov transition matrix
    """
    # 0-initialize the Markov transition matrix:
    n_bins = np.max(X_binned) + 1
    X_mtm = np.zeros((n_bins, n_bins))
    
    # We loop through each timestamp:
    n_timestamps = X_binned.shape[0]
    for j in prange(n_timestamps - 1):
        # For each timestamp 'j', we count the transition from the bin 
        # associated to the current timestamp to the bin associated to 
        # the next timestamp 'j+1':
        X_mtm[X_binned[j], X_binned[j + 1]] += 1

    return X_mtm
    
def markov_transition_probabilities(X_mtm):
    """
    Compute transition probabilities from a Markov transition field.
    
    PARAMS
    ======
        X_mtm: numpy.ndarray
            A Markov transition matrix
            
    RETURNS
    =======
        X_mtm: numpy.ndarray
            An updated Markov transition matrix where each value has been
            replaced by the transition probability of the current timestep
            to the next one.
    """
    sum_mtm = X_mtm.sum(axis=1)
    np.place(sum_mtm, sum_mtm == 0, 1)
    X_mtm /= sum_mtm[:, None]
    
    return X_mtm
    
def get_mtf_map(timeseries, 
                mtf, 
                step_size=0, 
                colormap=COLORMAP, 
                reversed_cmap=False):
    """
    This function extracts the color of one of the MTF diagonals and map them
    back to the original time series. The colors are associated to probability
    intensity for the Markov transitions.
    
    PARAMS
    ======
        timeseries: numpy.ndarray
            The time series data to map the MTF data to
        mtf: numpy.ndarray
            The MTF associated to this timeseries
        step_size: integer. Default = 0
            The n-th diagonal to consider when extracting the probability
            intensities from the MTF.
        colormap: string. Default = 'jet'
            Name of the matplotlib colormap to use
        reversed_cmap: boolean. Default = False
            Indicate if the colormap must be reversed
            
    RETURNS
    =======
        mtf_map: list of dict
            A list of dictionaries for each slice of data with a color and the 
            associated time series subset.
    """
    image_size = mtf.shape[0]
    mtf_min = np.min(mtf)
    mtf_max = np.max(mtf)
    mtf_range = mtf_max - mtf_min
    mtf_colors = (np.diag(mtf, k=step_size) - mtf_min) / mtf_range
    
    # Define the color map:
    if reversed_cmap == True:
        colormap = plt.cm.get_cmap(colormap).reversed()
    else:
        colormap = plt.cm.get_cmap(colormap)
    
    mtf_map = []
    sequences_width = timeseries.shape[0] / image_size
    for i in range(image_size):
        c = colormap(mtf_colors[i])
        start = int(i * sequences_width)
        end = int((i+1) * sequences_width - 1)
        data = timeseries.iloc[start:end, :]
        
        current_map = dict()
        current_map.update({
            'color': c,
            'slice': data
        })
        mtf_map.append(current_map)
        
    return mtf_map