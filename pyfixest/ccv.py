from pyfixest.estimation import feols
from scipy.stats import t
from tqdm import tqdm

import pandas as pd
import numpy as np

def ccv(data, depvar, treatment, cluster, xfml = None, seed = None, pk = 1, qk = 1, splits = 4):
    """
    Compute the CCV cluster robust variance estimator following Abadie, Athey, Imbens, Wooldridge (2022).
    The code is based on a Python implementation of the authours published under CC0 1.0 Deed and available at
    https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/27VMOT. This function has also
    benefitted from Daniel Pailanir and Damian Clarke's implementation in Stata available at
    https://github.com/Daniel-Pailanir/TSCB-CCV and published under GPL3 License.

    Parameters
    ----------
    data : pd.DataFrame
        Dataframe with the data
    depvar : str
        Name of the dependent variable
    treatment : str
        Name of the treatment variable
    xfml: str
        Additional formula string for covariate adjustment. Default is None.
    cluster : str
        Name of the cluster variable
    pk : float
        tba
    qk: float
        tba
    seed: random seed
        Random seed to control the behavior or sample splits. Sample are splitted so that E(Z) = 0.5.
    splits: int
        Number of splits to compute the variance estimator. Default is 4.
    Returns
    -------
    fit_full : feols
        Object with the fitted model and the cluster robust variance estimator
    """

    assert isinstance(data, pd.DataFrame)
    assert isinstance(depvar, str)
    assert isinstance(treatment, str)
    assert isinstance(cluster, str)
    assert isinstance(xfml, str) or xfml is None
    assert isinstance(pk, (int, float))
    assert isinstance(qk, (int, float))
    assert isinstance(seed, int) or seed is None
    assert isinstance(splits, int)

    rng = np.random.default_rng(seed)
    fml =  f"{depvar} ~ {treatment}" if xfml is None else f"{depvar} ~ {treatment} + {xfml}"

    fit_full = feols(fml, data, vcov = {"CRV1": cluster})
    if fit_full._has_fixef:
        raise ValueError("The model has fixed effects, which is not supported by the CCV estimator.")

    tau_full = fit_full.coef().xs(treatment)

    # get Y, W, X, cluster from fit_full (handles NaNs, etc.)
    # overwrite data to get rid of NaNs
    data = fit_full._data
    Y = fit_full._Y.flatten()
    W = data[treatment].values
    assert np.all(np.isin(W, [0, 1])), "Treatment variable must be binary with values 0 and 1"
    X = fit_full._X
    cluster_vec = data[cluster].values
    unique_clusters = np.unique(cluster_vec)

    N = fit_full._N
    G = len(unique_clusters)

    vcov_splits = np.empty(splits)
    for s in tqdm(range(splits)):

        Z = rng.choice([False, True], size=N)
        # compute alpha, tau using Z == 0
        fit_split1 = feols(fml, data[~Z])
        coefs_split = fit_split1._beta_hat
        tau = fit_split1.coef().xs(treatment)

        # estimate treatment effect for each cluster
        # for both the full sample and the subsample
        pk_term = 0.0
        tau_ms = np.zeros(G)
        N = 0
        for i, m in enumerate(unique_clusters):

            ind_m = cluster_vec == m
            Nm = np.sum(ind_m)
            N += Nm
            ind_m_and_split = ind_m & ~Z

            treatment_nested_in_cluster = (data.loc[ind_m, treatment].nunique() == 1)
            treatment_nested_in_cluster_split = (data.loc[ind_m_and_split, treatment].nunique() == 1)

            if treatment_nested_in_cluster:
                aux_tau_full = tau_full
            else:
                fit_m_full = feols(fml, data[ind_m])
                aux_tau_full = fit_m_full.coef().xs(treatment)

            # treatment effect in cluster for subsample
            if treatment_nested_in_cluster_split:
                aux_tau = tau
            else:
                fit_m = feols(fml, data[ind_m_and_split])
                aux_tau = fit_m.coef().xs(treatment)
            tau_ms[i] = aux_tau

            # compute the pk term in Z0
            aux_pk = Nm*((aux_tau_full-tau)**2)
            pk_term += aux_pk

        pk_term *= (1-pk) / N
        uhat = Y - X @ coefs_split
        #import pdb; pdb.set_trace()
        #Wbar = np.mean(W[Z])
        Wbar = np.sum(W * (1 - Z)) / (np.sum((1 - W) * (1 - Z)) + np.sum(W * (1 - Z)))
        Zavg = np.mean(Z)
        Zavg_squared = Zavg**2
        n_adj = N * (Wbar**2) * ((1-Wbar)**2)

        vcov_ccv = 0.0
        for i, m in enumerate(unique_clusters):
            ind_m = cluster_vec==m

            res_term = (W[ind_m & Z] - Wbar)*uhat[ind_m & Z]
            tau_term = (tau_ms[i] - tau)*Wbar*(1-Wbar)
            diff = res_term - tau_term

            #sq_mean = np.mean(diff) ** 2
            #mean_sq = np.mean(diff ** 2)
            sq_sum = np.sum(diff)**2
            sum_sq = np.sum(diff**2)
            #vcov_ccv += sq_mean + (1-Zavg) * mean_sq
            vcov_ccv += ((1 / Zavg_squared) * sq_sum - ((1-Zavg)/Zavg_squared) * sum_sq ) #+ n_adj * pk_term

        vcov_ccv = vcov_ccv / n_adj + G * pk_term

        vcov_splits[s] = vcov_ccv

    vcov_ccv = np.mean(vcov_splits)


    crv1_idx = fit_full._coefnames.index(treatment)
    vcov_crv1 = fit_full._vcov[crv1_idx, crv1_idx]
    qk = 1
    vcov_ccv = qk * vcov_ccv  + (1 - qk) * vcov_crv1

    se = np.sqrt(vcov_ccv)
    tstat = tau_full / se
    df = G - 1
    pvalue = 2 * (1 - t.cdf(np.abs(tstat), df))
    alpha = 0.95
    z = np.abs(t.ppf((1 - alpha) / 2, df))
    z_se = z * se
    conf_int = np.array([tau_full - z_se, tau_full + z_se])

    res_ccv = pd.Series({
        "Estimate": tau_full,
        "Std. Error": se,
        "t value": tstat,
        "Pr(>|t|)": pvalue,
        "2.5 %": conf_int[0],
        "97.5 %": conf_int[1]
    })
    res_ccv.name = "CCV"

    res_crv1 = fit_full.tidy().xs(treatment)
    res_crv1.name = "CRV1"

    return pd.concat([res_ccv, res_crv1], axis=1).T

