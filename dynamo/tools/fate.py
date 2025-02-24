from .scVectorField import VectorField
import numpy as np
from scipy.integrate import odeint


def fate(VecFld, init_state, t_end=100, step_size=0.01, direction='both', average=False):
    """Predict the historical and future cell transcriptomic states over arbitrary time scales by integrating vector field
    functions from one or a set of initial cell state(s).

    Arguments
    ---------
        VecFld: `function`
            Functional form of the vector field reconstructed from sparse single cell samples. It is applicable to the entire
            transcriptomic space.
        init_state: `numpy.ndarray`
            Initial cell states for the historical or future cell state prediction with numerical integration.
        t_end: `float` (default 100)
            The length of the time period from which to predict cell state forward or backward over time. This is used
            by the odeint function.
        step_size: `float` (default 0.01)
            Step size for integrating the future or history cell state, used by the odeint function.
        direction: `string` (default: both)
            The direction to predict the cell fate. One of the `forward`, `backward`or `both` string.
        average: `bool` (default: False)
            A boolean flag to determine whether to smooth the trajectory by calculating the average cell state at each time
            step.

    Returns
    -------
    t: `numpy.ndarray`
        The time at which the cell state are predicted.
    prediction: `numpy.ndarray`
        Predicted cells states at different time points. Row order corresponds to the element order in t. If init_state
        corresponds to multiple cells, the expression dynamics over time for each cell is concatenated by rows. That is,
        the final dimension of prediction is (len(t) * n_cells, n_features). n_cells: number of cells; n_features: number
        of genes or number of low dimensional embeddings. Of note, if the average is set to be True, the average cell state
        at each time point is calculated for all cells.
    """

    V_func = lambda x, t: VectorField.vector_field_function(x=x, t=t, VecFld=VecFld)

    t1=np.arange(0, t_end, step_size)
    n_cell, n_feature, n_steps = init_state.shape[0], init_state.shape[1], len(t1)

    if direction is 'both':
        t0=-t1

        history, future = np.zeros((n_cell * n_steps, n_feature)), np.zeros((n_cell * n_steps, n_feature))
        for i in range(n_cell):
            history[(n_steps * i):(n_steps * (i + 1)), :] = odeint(V_func, init_state[i, :], t=t0)
            future[(n_steps * i):(n_steps * (i + 1)), :] = odeint(V_func, init_state[i, :], t=t1)
        t, prediction = np.hstack((t0, t1)), np.vstack((history, future))
    elif direction is 'forward':
        prediction = np.zeros((n_cell * n_steps, n_feature))

        for i in range(n_cell):
            prediction[(n_steps * i):(n_steps * (i + 1)), :] = odeint(V_func, init_state[i, :], t=t1)
        t=t1
    elif direction is "backward":
        t0=-t1
        prediction = np.zeros((n_cell * n_steps, n_feature))
        for i in range(n_cell):
            prediction[(n_steps * i):(n_steps * (i + 1)), :] = odeint(V_func, init_state[i, :], t=t0)
        t=t0
    else:
        raise Exception('both, forward, backward are the only valid direction argument string')

    if average:
        avg = np.zeros((len(t1), init_state.shape[1]))
        for i in range(len(t)):
            avg[i, :] = np.mean(prediction[range(n_cell) * n_steps + i, :], 0)
        prediction = avg

    return t, prediction

# def fate_(adata, time, direction = 'forward'):
#     from .moments import *
#     gene_exprs = adata.X
#     cell_num, gene_num = gene_exprs.shape
#
#
#     for i in range(gene_num):
#         params = {'a': adata.uns['dynamo'][i, "a"], \
#                   'b': adata.uns['dynamo'][i, "b"], \
#                   'la': adata.uns['dynamo'][i, "la"], \
#                   'alpha_a': adata.uns['dynamo'][i, "alpha_a"], \
#                   'alpha_i': adata.uns['dynamo'][i, "alpha_i"], \
#                   'sigma': adata.uns['dynamo'][i, "sigma"], \
#                   'beta': adata.uns['dynamo'][i, "beta"], \
#                   'gamma': adata.uns['dynamo'][i, "gamma"]}
#         mom = moments_simple(**params)
#         for j in range(cell_num):
#             x0 = gene_exprs[i, j]
#             mom.set_initial_condition(*x0)
#             if direction == "forward":
#                 gene_exprs[i, j] = mom.solve([0, time])
#             elif direction == "backward":
#                 gene_exprs[i, j] = mom.solve([0, - time])
#
#     adata.uns['prediction'] = gene_exprs
#     return adata
