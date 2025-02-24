#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 30 11:21:25 2019

@author: xqiu
"""


# from .velo_slam_eqns import *
import numpy as np
from .gillespie import *
import pandas as pd
import scipy.sparse
from anndata import AnnData

# deterministic as well as noise 
def Simulator(a = None, b = None, la = None, aa = None, ai = None, si = None, be = None, ga = None, C0=np.zeros((5, 1)), t_span=[0, 50], n_traj=1, t_eval = None, dt = 1, method = 'Gillespie', verbose=False):
    """
    a: rate of active promoter switches to inactive one
    b: rate of inactive promoter switches to active one
    la: lambda_: 4sU labeling rate
    aa: transcription rate with active promoter
    ai: transcription rate with inactive promoter
    si: sigma, degradation rate
    be: beta, splicing rate
    ga: gamma: the fraction of labeled u turns to unlabeled s
    t_span: list of between and end time of simulation
    n_traj: number of simulation trajectory to use
    t_eval: the time points at which data is simulated
    dt: delta t used in simulation
    method: method to simulate the expression dynamics
    verbose: whether to report running information
    """

    gene_num, species_num = C0.shape[0:2]
    if method == 'Gillespie':
        if t_eval is None:
            steps = (t_span[1] - t_span[0]) // dt # // int; %% remainder
            t_eval = np.linspace(t_span[0], t_span[1], steps)
        trajs_C = simulate_multigene(a, b, la, aa, ai, si, be, ga, C0, t_span, n_traj, t_eval, report=verbose)    # unfinished, no need to interpolate now.
        uu, ul, su, sl = [np.transpose(trajs_C[:, :, i + 1, :].reshape((gene_num, -1))) for i in range(4)]

        u = uu + ul 
        s = su + sl 
        E = u + s
    
        layers = {'uu': scipy.sparse.csc_matrix(uu), 'ul': scipy.sparse.csc_matrix(ul), \
                                           'su': scipy.sparse.csc_matrix(su.astype(int)), \
                                           'sl': scipy.sparse.csc_matrix(sl.astype(int)), \
                                           'spliced': scipy.sparse.csc_matrix((s).astype(int)), \
                                           'unspliced': scipy.sparse.csc_matrix((u).astype(int)),
                                           'ambiguous': scipy.sparse.csc_matrix((E).astype(int))} # ambiguous is required for velocyto

    elif method == 'simulate_2bifurgenes': 
        gene_num = 2
        _, trajs_C = simulate_2bifurgenes(a1 = 20, b1 = 20, a2 = 20, b2 = 20, K = 20, n = 3, be1 = 1, ga1 = 1, be2 = 1, ga2 = 1, C0 = np.zeros(4), t_span = t_span, n_traj = n_traj, report=verbose)    # unfinished, no need to interpolate now.
        u = trajs_C[0][[0, 2], :].T
        s = trajs_C[0][[1, 3], :].T
        E = u + s
        
        layers = {'spliced': scipy.sparse.csc_matrix((s).astype(int)), \
                   'unspliced': scipy.sparse.csc_matrix((u).astype(int)),
                   'ambiguous': scipy.sparse.csc_matrix((E).astype(int))} # ambiguous is required for velocyto

        steps = u.shape[0]
        
    # anadata: observation x variable (cells x genes)

    if(verbose):
        print('we have %s cell and %s genes.' % (E.shape[0], E.shape[1]))

    var = pd.DataFrame({'gene_short_name': ['gene_%d'%(i) for i in range(gene_num)]}) # use the real name in simulation? 
    var.set_index('gene_short_name', inplace = True)

    # provide more annotation for cells next:
    cell_ids = ['traj_%d_step_%d'%(i, j) for i in range(n_traj) for j in range(steps)] # first n_traj and then steps
    obs = pd.DataFrame({'Cell_name': cell_ids,
                        'Trajectory': [i for i in range(n_traj) for j in range(steps)],
                        'Step': [j for i in range(n_traj) for j in range(steps)]})
    obs.set_index('Cell_name', inplace = True)

    adata = AnnData(E, obs, var, layers = layers, obsm = {"X_pca": E})

    # remove cells that has no expression
    adata = adata[adata.X.sum(1) > 0, :]
    return adata




