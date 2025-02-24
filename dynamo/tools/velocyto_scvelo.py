# functions to run velocyto and scvelo
import numpy as np
import pandas as pd
#import velocyto as vcy
#import scvelo as scv
import scipy as scp 
import matplotlib.pyplot as plt
from .moments import *
from anndata import AnnData

# code from scSLAM-seq repository 
# vlm.ts: transition matrix?
# from velocitySlamSeq.slam_seq import simulate_mul

def vlm_to_adata(vlm, trans_mats = None, cells_ixs = None, em_key = None):
	""" Conversion function from the velocyto world to the scanpy world

	Parameters
	--------
	vlm: VelocytoLoom Object
	trans_mats: None or dict
		A dict of all relevant transition matrices
	cell_ixs: list of int
		These are the indices of the subsampled cells

	Output
	adata: AnnData object
	"""

	# create the anndata object
	adata = AnnData(
		vlm.Sx_sz.T, vlm.ca, vlm.ra,
		layers=dict(
			unspliced=vlm.U.T,
			spliced = vlm.S.T, 
			velocity = vlm.velocity.T),
		uns = dict(velocity_graph = vlm.corrcoef, louvain_colors = list(np.unique(vlm.colorandum)))
	)

	# add uns annotations
	if trans_mats is not None:
		for key, value in trans_mats.items():
			adata.uns[key] = trans_mats[key]
	if cells_ixs is not None:
		adata.uns['cell_ixs'] = cells_ixs

	# rename clusters to louvain
	try:
		ix = np.where(adata.obs.columns == 'Clusters')[0][0]
		obs_names = list(adata.obs.columns)
		obs_names[ix] = 'louvain'
		adata.obs.columns = obs_names

		# make louvain a categorical field
		adata.obs['louvain'] = pd.Categorical(adata.obs['louvain'])
	except:
		print('Could not find a filed \'Clusters\' in vlm.ca.')

	# save the pca embedding
	adata.obsm['X_pca'] = vlm.pcs[:, range(50)]

	# transfer the embedding
	if em_key is not None:
		adata.obsm['X_' + em_key] = vlm.ts
		adata.obsm['velocity_' + em_key] = vlm.delta_embedding

	# make things sparse
	adata.X = scp.sparse.csr_matrix(adata.X)
	adata.uns['velocity_graph'] =scp.sparse.csr_matrix(adata.uns['velocity_graph'])

	# make the layers sparse
	adata.layers['unspliced'] = scp.sparse.csr_matrix(adata.layers['unspliced'])
	adata.layers['spliced'] = scp.sparse.csr_matrix(adata.layers['unspliced'])
	adata.layers['velocity'] = scp.sparse.csr_matrix(adata.layers['unspliced'])

	return adata

def converter(data_in, from_type = 'adata', to_type = 'vlm', dir = '.'): 
	"""
	convert adata to loom object
	- we may save to a temp directory automatically 
	- we may write a on-the-fly converter which doesn't involve saving and reading files  
	"""
	if(from_type == 'adata'):
		if(to_type == 'vlm'):
			file = dir + '/data.loom'
			data_in.write_loom(file)
			data_out = vcy.VelocytoLoom(file)
	elif(from_type == 'vlm'):
		if(to_type == 'adata'):
			data_out = vlm_to_adata(vlm)

	data_out.ra['Gene'] = data_out.ra['var_names'] # required by plot_phase_portraits
	colors20 = np.vstack((plt.cm.tab20b(np.linspace(0., 1, 20))[::2], plt.cm.tab20c(np.linspace(0, 1, 20))[1::2]))

	def colormap_fun(x: np.ndarray) -> np.ndarray:
		return colors20[np.mod(x, 20)]

	data_out.colorandum = colormap_fun([1] * data_out.S.shape[1])

	return(data_out)

def run_velocyto(adata):
	"""
	1. convert adata to vlm data
	2. set up PCA, UMAP, etc.
	3. estimate the gamma parameter
	"""
	vlm = converter(adata)

	# U_norm: log2(U_sz + pcount)
	# vlm.U_sz: norm_factor * U
	# S_norm: log2(S_sz + pcount)
	# vlm.S_sz norm_factor * S
	# vlm.Ux: smoothed unspliced
	# vlm.Sx: smoothed spliced
	# vlm.Ux_sz: smoothed unspliced -- old code
	# vlm.Sx_sz: smoothed spliced -- old code

	vlm.normalize() # add U_norm, U_sz, S_norm, S_sz
	vlm.perform_PCA()
	vlm.knn_imputation() # Ux, Sx, Ux_sz, Sx_sz
	vlm.pcs = adata.X # pcs: cell x npcs ndarray

	# vlm.Sx = vlm.S_sz
	# vlm.Ux = vlm.U_sz
	# vlm.Sx_sz = vlm.S_sz
	# vlm.Ux_sz = vlm.U_sz

	# gamma fit
	vlm.fit_gammas() # limit_gamma = False, fit_offset = True,  use_imputed_data = False, use_size_norm = False

	# estimate velocity
	vlm.predict_U()
	vlm.calculate_velocity()

	# predict future state after dt
	vlm.calculate_shift() # assumption = 'constant_velocity'
	vlm.extrapolate_cell_at_t() # delta_t = 1.

	return vlm

def run_scvelo(adata): 
	"""
	1. set up PCA, UMAP, etc. 
	2. estimate gamma and all other parameters 
	3. return results (adata.var['velocity_gamma'])
	"""
	# scv.pp.filter_and_normalize(adata, min_counts=2, min_counts_u=1, n_top_genes=3000)
	scv.pp.moments(adata) # , n_pcs = 12, n_neighbors = 15, mode = 'distances'
	scv.tl.velocity(adata)
	scv.tl.velocity_graph(adata)

	# how to fit other parameters, beta, etc.?

	return adata

def mean_var_by_time(X, Time):
	import pandas as pd

	exp_data = pd.DataFrame(X)
	exp_data['Time'] = Time

	mean_val = exp_data.groupby(['Time']).mean()
	var_val = exp_data.groupby(['Time']).var()

	return mean_val.values, var_val.values

def run_dynamo(adata, normalize = True, init_num = 1, sample_method = 'lhs'):
	time = adata.obs['Step'].values
	uniqe_time = list(set(time))
	gene_num = adata.X.shape[1]

	# prepare data
	import numpy as np
	x_data = np.zeros((8, len(uniqe_time), gene_num)) # use unique time
	uu, ul, su, sl = adata.layers['uu'].toarray(), adata.layers['ul'].toarray(), adata.layers['su'].toarray(), adata.layers['sl'].toarray()
	uu = np.log2(uu + 1) if normalize else uu
	ul = np.log2(ul + 1) if normalize else ul
	su = np.log2(su + 1) if normalize else su
	sl = np.log2(sl + 1) if normalize else sl

	x_data[0], x_data[4] = mean_var_by_time(uu, time)
	x_data[1], x_data[5] = mean_var_by_time(ul, time)
	x_data[2], x_data[6] = mean_var_by_time(su, time)
	x_data[3], x_data[7] = mean_var_by_time(sl, time)

	# estimation all parameters
	p0_range = {'a': [0, 1], 'b': [0, 1], 'la': [0, 1], 'alpha_a': [10, 1000], \
			'alpha_i': [0, 10], 'sigma': [0, 1], 'beta': [0, 10], 'gamma': [0, 10]}

	estm = estimation(list(p0_range.values()))
	param_out = pd.DataFrame(index=adata.var.index, columns=['a', 'b', 'la', 'alpha_a', 'alpha_i', 'sigma', 'beta', 'gamma'])
	for i in range(gene_num):
		cur_x_data = x_data[:, :, i].squeeze()
		param_out.iloc[i, :], cost = estm.fit_lsq(uniqe_time, cur_x_data, p0=None, n_p0=init_num, sample_method=sample_method)

	# estimate only on the spliced and unspliced dataset

	# estimate on the labeled and unlabeled dataset

	# store the fitting result in adata.uns
	adata.uns.update({"dynamo": param_out})

	return adata


def run_dynamo_simple_fit(adata, log = True):
    ncells, gene_num = adata.X.shape 
    
    # estimation all parameters
    param_out = pd.DataFrame(index=adata.var.index, columns=['alpha', 'gamma'])
    
    u, s = adata.layers['unspliced'], adata.layers['spliced']
    velocity_u, velocity_s = u, s
    for i in range(gene_num):
        cur_u, cur_s = u[:, i], s[:, i]
        gamma = fit_gamma(cur_u.toarray().squeeze(), cur_s.toarray().squeeze())
        alpha = np.mean(cur_s)
        
        velocity_u[:, i] = cur_u - cur_s * gamma 
        velocity_s[:, i] = cur_s/(1 - np.exp(-1)) - cur_u
        param_out.iloc[i, :] = [alpha, gamma]
    
    adata.layers["velocity_u"] = velocity_u
    adata.layers["velocity_s"] = velocity_s
    adata.uns.update({"dynamo_simple_fit": param_out})
    
    return adata 


def run_dynamo_labeling(adata, log = True, group = False):
    ncells, gene_num = adata.X.shape 
    
    # estimation all parameters
    T = adata.obs['Time']
    
    groups = [''] if group == False else np.unique(adata.obs[group])
    
    param_out = pd.DataFrame(index=adata.var.index, columns=[i + '_' + j for j in groups for i in ['alpha', 'gamma', 'u0', 'l0']])
    L, U = adata.layers['L'], adata.layers['U']
    velocity_u, velocity_s = L, U

    for i in range(gene_num):
        all_parm = []
        for cur_grp in groups.tolist(): 
            cur_L, cur_U = (L[:, i], U[:, i]) if cur_grp == '' else (L[adata.obs[group] == cur_grp, i], U[adata.obs[group] == cur_grp, i])
            if log: 
                cur_U, cur_L = np.log(cur_U.toarray().squeeze() + 1), np.log(cur_L.toarray().squeeze() + 1)
            else: 
                cur_U, cur_L = cur_U.toarray().squeeze(), cur_L.toarray().squeeze()

            gamma, l0 = fit_gamma_labeling(T, cur_L, mode=None)
            alpha, u0 = fit_alpha_labeling(T, cur_U, gamma, mode=None)
            tmp = [alpha, gamma, u0, l0]
            all_parm.extend(tmp)

            velocity_u[:, i] = (cur_L - cur_U * gamma)[:, None]
            velocity_s[:, i] = (cur_U/(1 - np.exp(-1)) - cur_L)[:, None]
            adata.layers[cur_grp + "velocity_u"] = velocity_u
            adata.layers[cur_grp + "velocity_s"] = velocity_s

        param_out.iloc[i, :] = all_parm
    
    adata.uns.update({"dynamo_labeling": param_out})
    
    return adata 


def compare_res(adata, velocyto_res, svelo_res, dynamo_res, a_val, b_val, la_val, alpha_a_val, alpha_i_val, sigma_val, beta_val, gamma_val):
	"""
	function to compare results from velocyto and scvelo with our new method
	0. retrieve gamm or gamma with other parameters from velocyto result or scvelo
	1. plot the correlation between parameters estimated with different methods
	2. calculate the correltion between those parameters
	"""
	# self._offset, self._offset2, self._beta, self._gamma, self._r2, self._velocity_genes

	velocyto_gammas = velocyto_res.gammas
	scvelo_gammas = svelo_res.var['velocity_gamma']

	# scatter plot the true gammas with our result
	plt.subplots(figsize = (15, 5))
	plt.plot()
	plt.subplot(131)
	plt.plot(gamma_val, velocyto_gammas, 'o')
	plt.xlabel(r'True $\gamma$')
	plt.ylabel(r'$\gamma$ (velocyto)')
	plt.subplot(132)
	plt.plot(gamma_val, scvelo_gammas, 'o')
	plt.xlabel(r'True $\gamma$')
	plt.ylabel(r'$\gamma$ (scvelo)')
	plt.subplot(133)
	plt.plot(gamma_val, dynamo_res.uns['dynamo']["gamma"], 'o')
	plt.xlabel(r'True $\gamma$')
	plt.ylabel(r'$\gamma$ (dynamo)')

    # what if we only have a small number of parameters? 
	plt.subplots(figsize = (15, 5))
	plt.plot()
	plt.subplot(131)
	plt.plot(alpha_a_val, svelo_res.var['fit_alpha'], 'o')
	plt.xlabel(r'True alpha')
	plt.ylabel(r'$\alpha$ (scvelo)')
	plt.subplot(132)
	plt.plot(beta_val, svelo_res.var['fit_beta'], 'o')
	plt.xlabel(r'True $\beta$')
	plt.ylabel(r'$\beta$ (scvelo)')
	plt.subplot(133)
	plt.plot(gamma_val, svelo_res.var['fit_gamma'], 'o')
	plt.xlabel(r'True $\gamma$')
	plt.ylabel(r'$\gamma$ (scvelo)')

    #     param_out = pd.DataFrame(index=adata.var.index, columns=['a', 'b', 'la', 'alpha_a', 'alpha_i', 'sigma', 'beta', 'gamma'])
    # what if we only have a small number of parameters? 
	plt.subplots(figsize = (15, 15))
	plt.subplot(331)
	plt.plot(a_val, adata.uns['dynamo']["a"], 'o')
	plt.xlabel(r'True $a$')
	plt.ylabel(r'$a$ (dynamo)')
	plt.subplot(332)
	plt.plot(b_val, adata.uns['dynamo']["b"], 'o')
	plt.xlabel(r'True $b$')
	plt.ylabel(r'$b$ (dynamo)')
	plt.subplot(333)
	plt.plot(la_val, adata.uns['dynamo']["la"], 'o')
	plt.xlabel(r'True $l_a$')
	plt.ylabel(r'$l_a$ (dynamo)')
	plt.subplot(334)
	plt.plot(alpha_a_val, adata.uns['dynamo']["alpha_a"], 'o')
	plt.xlabel(r'True $\alpha_a$')
	plt.ylabel(r'$\alpha_a$ (dynamo)')
	plt.subplot(335)
	plt.plot(alpha_i_val, adata.uns['dynamo']["alpha_i"], 'o')
	plt.xlabel(r'True $\alpha_i$')
	plt.ylabel(r'$\alpha_i$ (dynamo)')
	plt.subplot(336)
	plt.plot(sigma_val, adata.uns['dynamo']["sigma"], 'o')
	plt.xlabel(r'True $\sigma$')
	plt.ylabel(r'$\sigma$ (dynamo)')
	plt.subplot(337)
	plt.plot(beta_val, adata.uns['dynamo']["beta"], 'o')
	plt.xlabel(r'True $\beta$')
	plt.ylabel(r'$\beta$ (dynamo)')
	plt.subplot(338)
	plt.plot(gamma_val, adata.uns['dynamo']["gamma"], 'o')
	plt.xlabel(r'True $\gamma$')
	plt.ylabel(r'$\gamma$ (dynamo)')

	velocyto_coef = {"gamma": np.corrcoef(gamma_val, velocyto_gammas)[1, 0]}
	scvelo_coef = {"alpha": np.corrcoef(alpha_a_val, svelo_res.var['fit_alpha'])[1, 0], 
                   "beta": np.corrcoef(beta_val, svelo_res.var['fit_beta'])[1, 0], 
                   "gamma": np.corrcoef(gamma_val, svelo_res.var['fit_gamma'])[1, 0], }
    
	dynamo_coef = {'a': np.corrcoef(a_val, list(dynamo_res.uns['dynamo']["a"]))[1, 0], 
	               'b': np.corrcoef(b_val, list(dynamo_res.uns['dynamo']["b"]))[1, 0], 
	               'la': np.corrcoef(la_val, list(dynamo_res.uns['dynamo']["la"]))[1, 0],
	               'alpha_a': np.corrcoef(alpha_a_val, list(dynamo_res.uns['dynamo']["alpha_a"]))[1, 0],
	               'alpha_i': np.corrcoef(alpha_i_val, list(dynamo_res.uns['dynamo']["alpha_i"]))[1, 0],
	               'sigma': np.corrcoef(sigma_val, list(dynamo_res.uns['dynamo']["sigma"]))[1, 0],
	               'beta': np.corrcoef(beta_val, list(dynamo_res.uns['dynamo']["beta"]))[1, 0],
	               'gamma': np.corrcoef(gamma_val, list(dynamo_res.uns['dynamo']["gamma"]))[1, 0],

	              }
    
	return {'velocyto': pd.DataFrame.from_dict(velocyto_coef, orient = 'index').T, \
	'scvelo': pd.DataFrame.from_dict(scvelo_coef, orient = 'index').T, \
	'dynamo': pd.DataFrame.from_dict(dynamo_coef, orient = 'index').T}
