import numpy as np
import pandas as pd
import pytest

import pyfixest as pf


@pytest.mark.parametrize("fml", ["Y~X1+f3", "Y~X1+f3|f1", "Y~X1+f3|f1+f2"])
@pytest.mark.parametrize("resampvar", ["X1", "f3"])
@pytest.mark.parametrize("reps", [111, 212])
@pytest.mark.parametrize("algo_iterations", [None, 10])
@pytest.mark.parametrize("cluster", [None, "group_id"])
def test_algos_internally(data, fml, resampvar, reps, algo_iterations, cluster):
    fit = pf.feols(fml, data=data)

    rng1 = np.random.default_rng(1234)
    rng2 = np.random.default_rng(1234)

    kwargs = {
        "resampvar": resampvar,
        "reps": reps,
        "type": "randomization-c",
        "algo_iterations": algo_iterations,
        "store_ritest_statistics": True,
        "cluster": cluster,
    }

    kwargs1 = kwargs.copy()
    kwargs2 = kwargs.copy()

    kwargs1["choose_algorithm"] = "slow"
    kwargs1["rng"] = rng1
    kwargs2["choose_algorithm"] = "fast"
    kwargs2["rng"] = rng2

    res1 = fit.ritest(**kwargs1)
    ritest_stats1 = fit._ritest_statistics.copy()

    res2 = fit.ritest(**kwargs2)
    ritest_stats2 = fit._ritest_statistics.copy()

    assert np.allclose(res1.Estimate, res2.Estimate, atol=1e-3, rtol=1e-3)
    assert np.allclose(res1["Pr(>|t|)"], res2["Pr(>|t|)"], atol=1e-3, rtol=1e-3)
    assert np.allclose(ritest_stats1, ritest_stats2, atol=1e-3, rtol=1e-3)


@pytest.fixture
def ritest_results():
    # Load the CSV file into a pandas DataFrame
    file_path = "tests/data/ritest_results.csv"
    results_df = pd.read_csv(file_path)
    results_df.set_index(["formula", "resampvar", "cluster"], inplace=True)
    return results_df


@pytest.fixture
def data():
    return pf.get_data(N=1000, seed=2999)


@pytest.mark.parametrize("fml", ["Y~X1+f3", "Y~X1+f3|f1", "Y~X1+f3|f1+f2"])
@pytest.mark.parametrize("resampvar", ["X1", "f3", "X1=-0.75", "f3>0.05"])
@pytest.mark.parametrize("cluster", [None, "group_id"])
def test_vs_r(data, fml, resampvar, cluster, ritest_results):
    fit = pf.feols(fml, data=data)
    reps = 10_000

    rng1 = np.random.default_rng(1234)

    kwargs = {
        "resampvar": resampvar,
        "reps": reps,
        "type": "randomization-c",
        "cluster": cluster,
    }

    kwargs1 = kwargs.copy()

    kwargs1["choose_algorithm"] = "fast"
    kwargs1["rng"] = rng1

    res1 = fit.ritest(**kwargs1)

    if cluster is not None:
        pval = ritest_results.xs(
            (fml, resampvar, cluster), level=("formula", "resampvar", "cluster")
        )["pval"].to_numpy()
        se = ritest_results.xs(
            (fml, resampvar, cluster), level=("formula", "resampvar", "cluster")
        )["se"].to_numpy()
        ci_lower = ritest_results.xs(
            (fml, resampvar, cluster), level=("formula", "resampvar", "cluster")
        )["ci_lower"].to_numpy()
    else:
        pval = ritest_results.xs(
            (fml, resampvar, "none"), level=("formula", "resampvar", "cluster")
        )["pval"].to_numpy()
        se = ritest_results.xs(
            (fml, resampvar, "none"), level=("formula", "resampvar", "cluster")
        )["se"].to_numpy()
        ci_lower = ritest_results.xs(
            (fml, resampvar, "none"), level=("formula", "resampvar", "cluster")
        )["ci_lower"].to_numpy()

    assert np.allclose(res1["Pr(>|t|)"], pval, rtol=1e-01, atol=0.01)
    assert np.allclose(res1["Std. Error (Pr(>|t|))"], se, rtol=1e-01, atol=0.01)
    assert np.allclose(res1["2.5% (Pr(>|t|))"], ci_lower, rtol=1e-01, atol=0.01)


def test_fepois_ritest():
    data = pf.get_data(model="Fepois")
    fit = pf.fepois("Y ~ X1*f3", data=data)
    fit.ritest(resampvar="f3", reps=2000, store_ritest_statistics=True)

    assert fit._ritest_statistics is not None
    assert np.allclose(fit.pvalue().xs("f3"), fit._ritest_pvalue, rtol=1e-01, atol=0.01)