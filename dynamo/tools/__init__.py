"""Mapping Vector Field of Single Cells
"""

# inclusive expression dynamics model related 
# from .dynamo import sol_u, sol_s, fit_gamma_labeling, fit_alpha_labeling, fit_gamma_splicing, fit_gamma
# from .dynamo_fitting import sol_u, sol_s, sol_p, sol_ode, sol_num, fit_gamma_labeling, fit_beta_lsq, fit_alpha_labeling, fit_alpha_synthesis, fit_gamma_splicing, fit_gamma
from .gillespie import directMethod, prop_slam, simulate_Gillespie, prop_2bifurgenes, stoich_2bifurgenes, simulate_2bifurgenes, temporal_average, temporal_cov, temporal_interp, convert_nosplice, simulate_multigene, trajectories
from .moments import Estimation

from .simulation import Simulator

from .velocity import sol_u, sol_s, sol_p, fit_linreg, fit_beta_lsq, fit_gamma_lsq, fit_alpha_synthesis, fit_alpha_degradation, velocity, estimation
from .cell_velocities import cell_velocities, markov_combination, makeTransitionMatrix, diffusion

# run other velocity tools: 
from .velocyto_scvelo import vlm_to_adata, converter, run_velocyto, run_scvelo, mean_var_by_time, run_dynamo, run_dynamo_simple_fit, run_dynamo_labeling, compare_res

# vector field related
from .scVectorField import SparseVFC, con_K, get_P, VectorField #, evaluate, con_K_div_cur_free, vector_field_function, vector_field_function_auto, auto_con_K

# potential related
from .scPotential import gen_fixed_points, gen_gradient, IntGrad, DiffusionMatrix, action, Potential, ODE, autoODE #, vector_field_function
from .Bhattacharya import path_integral, alignment
from .Wang import Wang_action, Wang_LAP, transition_rate, MFPT
from .Ao import Ao_pot_map

# cell fate related
from .fate import fate

# dimension reduction related
from .dimension_reduction import extract_indices_dist_from_graph, umap_conn_indices_dist_embedding, reduceDimension

