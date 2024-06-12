import numpy as np
import pytest

import pyfixest as pf
from pyfixest.utils.utils import get_data, ssc


@pytest.fixture
def data():
    return get_data(N=1_000, seed=9)


# note - tests currently fail because of ssc adjustments
@pytest.mark.parametrize("fml", ["Y~X1", "Y~X1|f1", "Y~X1|f1+f2"])
def test_hc_equivalence(data, fml):
    # note: cannot turn of ssc for wildboottest HC
    fixest = pf.feols(fml=fml, data=data)
    tstat = fixest.tstat().xs("X1")
    boot_tstat = fixest.wildboottest(param="X1", reps=999)["t value"]

    # cannot test for for equality because of ssc adjustments
    np.testing.assert_allclose(tstat, boot_tstat, rtol=0.01, atol=0.01)


@pytest.mark.parametrize("fml", ["Y~X1", "Y~X1|f1", "Y~X1|f1+f2"])
def test_crv1_equivalence(data, fml):
    fixest = pf.feols(
        fml, data=data, vcov={"CRV1": "group_id"}, ssc=ssc(adj=False, cluster_adj=False)
    )
    tstat = fixest.tstat().xs("X1")
    boot_tstat = fixest.wildboottest(
        param="X1", reps=999, adj=False, cluster_adj=False
    )["t value"]

    np.testing.assert_allclose(tstat, boot_tstat)
