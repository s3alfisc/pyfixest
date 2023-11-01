import pandas as pd
import numpy as np

from pyfixest.estimation import feols
from pyfixest.exceptions import NotImplementedError

from abc import ABC, abstractmethod
from formulaic import model_matrix
from scipy.sparse.linalg import spsolve



def event_study(data, yname, idname, tname, gname, xfml = None, estimator = "twfe", att = True, cluster = "idname"):

    """
    Estimate a treatment effect using an event study design. If estimator is "twfe", then
    the treatment effect is estimated using the two-way fixed effects estimator. If estimator
    is "did2s", then the treatment effect is estimated using Gardner's two-step DID2S estimator.
    Other estimators are work in progress, please contact the package author if you are interested
    / need other estimators (i.e. Mundlak, Sunab, Imputation DID or Projections).

    Args:
        data: The DataFrame containing all variables.
        yname: The name of the dependent variable.
        idname: The name of the id variable.
        tname: Variable name for calendar period.
        gname: unit-specific time of initial treatment.
        xfml: The formula for the covariates.
        estimator: The estimator to use. Options are "did2s" and "twfe".
        att: Whether to estimate the average treatment effect on the treated (ATT) or the
            canonical event study design with all leads and lags. Default is True.
    Returns:
        A fitted model object of class feols.
    """

    assert isinstance(data, pd.DataFrame), "data must be a pandas DataFrame"
    assert isinstance(yname, str), "yname must be a string"
    assert isinstance(idname, str), "idname must be a string"
    assert isinstance(tname, str), "tname must be a string"
    assert isinstance(gname, str), "gname must be a string"
    assert isinstance(xfml, str) or xfml is None, "xfml must be a string or None"
    assert isinstance(estimator, str), "estimator must be a string"
    assert isinstance(att, bool), "att must be a boolean"
    assert isinstance(cluster, str), "cluster must be a string"
    assert cluster == "idname", "cluster must be idname"

    if cluster == "idname":
        cluster = idname
    else:
        raise NotImplementedError("Clustering by a variable of your choice is not yet supported.")

    if estimator == "did2s":

        did2s = DID2S(data = data, yname = yname, idname=idname, tname = tname, gname = gname, xfml = xfml, att = att, cluster = cluster)
        fit, did2s._first_u, did2s._second_u = did2s.estimate()
        vcov = did2s.vcov()
        fit._vcov = vcov
        fit._vcov_type = "CRV1"
        fit._vcov_type_detail = "CRV1 (GMM)"
        fit._G = did2s._G
        fit._method = "did2s"

    elif estimator == "twfe":

        twfe = TWFE(data = data, yname = yname, idname=idname, tname = tname, gname = gname, xfml = xfml, att = att, cluster = cluster)
        fit = twfe.estimate()
        vcov = fit.vcov(vcov = {"CRV1": twfe._idname})
        fit._method = "twfe"

    else:
        raise Exception("Estimator not supported")

    # update inference with vcov matrix
    fit.get_inference()

    return fit



class DID(ABC):

    @abstractmethod
    def __init__(self, data, yname, idname, tname, gname, xfml, att, cluster):

        """
        Args:
            data: The DataFrame containing all variables.
            yname: The name of the dependent variable.
            idname: The name of the id variable.
            tname: Variable name for calendar period. Must be an integer in the format YYYYMMDDHHMMSS, i.e. it must be
                   possible to compare two dates via '>'. Date time variables are currently not accepted.
            gname: unit-specific time of initial treatment. Must be an integer in the format YYYYMMDDHHMMSS, i.e. it must be
                   possible to compare two dates via '>'. Date time variables are currently not accepted. Never treated units
                   must have a value of 0.
            xfml: The formula for the covariates.
            estimator: The estimator to use. Options are "did2s".
            att: Whether to estimate the average treatment effect on the treated (ATT) or the
                canonical event study design with all leads and lags. Default is True.
            cluster: The name of the cluster variable.
        Returns:
            None
        """

        # do some checks here

        self._data = data.copy()
        self._yname = yname
        self._idname = idname
        self._tname = tname
        self._gname = gname
        self._xfml = xfml
        self._att = att
        self._cluster = cluster

        if self._xfml is not None:
            raise NotImplementedError("Covariates are not yet supported.")
        if self._att is False:
            raise NotImplementedError("Event study design with leads and lags is not yet supported.")

        # check if idname, tname and gname are in data
        #if self._idname not in self._data.columns:
        #    raise ValueError(f"The variable {self._idname} is not in the data.")
        #if self._tname not in self._data.columns:
        #    raise ValueError(f"The variable {self._tname} is not in the data.")
        #if self._gname not in self._data.columns:
        #    raise ValueError(f"The variable {self._gname} is not in the data.")

        # check if tname and gname are of type int (either int 64, 32, 8)
        if self._data[self._tname].dtype not in ["int64", "int32", "int8"]:
            raise ValueError(f"The variable {self._tname} must be of type int64, and more specifically, in the format YYYYMMDDHHMMSS.")
        if self._data[self._gname].dtype not in ["int64", "int32", "int8"]:
            raise ValueError(f"The variable {self._gname} must be of type int64, and more specifically, in the format YYYYMMDDHHMMSS.")

        # check if there is a never treated unit
        if 0 not in self._data[self._gname].unique():
            raise ValueError(f"There must be at least one unit that is never treated.")

        # create a treatment variable
        self._data["ATT"] = (self._data[self._tname] >= self._data[self._gname]) * (self._data[self._gname] > 0)


    @abstractmethod
    def estimate(self):
        pass

    @abstractmethod
    def vcov(self):
        pass

    #@abstractmethod
    #def aggregate(self):
    #    pass


class TWFE(DID):

    """
    Estimate a Difference-in-Differences model using the two-way fixed effects estimator.
    """

    def __init__(self, data, yname, idname, tname, gname, xfml, att, cluster):

        """
        Args:
            data: The DataFrame containing all variables.
            yname: The name of the dependent variable.
            idname: The name of the id variable.
            tname: Variable name for calendar period. Must be an integer in the format YYYYMMDDHHMMSS, i.e. it must be
                   possible to compare two dates via '>'. Date time variables are currently not accepted.
            gname: unit-specific time of initial treatment. Must be an integer in the format YYYYMMDDHHMMSS, i.e. it must be
                     possible to compare two dates via '>'. Date time variables are currently not accepted. Never treated units
                     must have a value of 0.
            xfml: The formula for the covariates.
            att: Whether to estimate the average treatment effect on the treated (ATT) or the
                canonical event study design with all leads and lags. Default is True.
            cluster (str): The name of the cluster variable.
        Returns:
            None
        """

        super().__init__(data, yname, idname, tname, gname, xfml, att, cluster)

        self._estimator = "twfe"

        if self._xfml is not None:
            self._fml = f"{yname} ~ ATT + {xfml} | {idname} + {tname}"
        else:
            self._fml = f"{yname} ~ ATT | {idname} + {tname}"

    def estimate(self):

            _fml = self._fml
            _data = self._data

            fit = feols(fml = _fml, data = _data)
            self._fit = fit

            return fit

    def vcov(self):

        """
        Method not needed. The vcov matrix is calculated via the `Feols` object.
        """

        pass



class DID2S(DID):

    """
    Difference-in-Differences estimation using Gardner's two-step DID2S estimator (2021).

    Multiple parts of this code are direct translations of Kyle Butt's R code `did2s`, published
    under MIT license: https://github.com/kylebutts/did2s/tree/main.
    """

    def __init__(self, data, yname, idname, tname, gname, xfml, att, cluster):

        """
        Args:
            data: The DataFrame containing all variables.
            yname: The name of the dependent variable.
            idname: The name of the id variable.
            tname: Variable name for calendar period. Must be an integer in the format YYYYMMDDHHMMSS, i.e. it must be
                   possible to compare two dates via '>'. Date time variables are currently not accepted.
            gname: unit-specific time of initial treatment. Must be an integer in the format YYYYMMDDHHMMSS, i.e. it must be
                     possible to compare two dates via '>'. Date time variables are currently not accepted. Never treated units
                     must have a value of 0.
            xfml: The formula for the covariates.
            att: Whether to estimate the average treatment effect on the treated (ATT) or the
                canonical event study design with all leads and lags. Default is True.
            cluster (str): The name of the cluster variable.
        Returns:
            None
        """

        super().__init__(data, yname, idname, tname, gname, xfml, att, cluster)

        self._estimator = "did2s"

        if self._xfml is not None:
            self._fml1 = f"{yname} ~ {xfml} | {idname} + {tname}"
            self._fml2 = f"{yname} ~ 0 + ATT + {xfml}"
        else:
            self._fml1 = f"{yname} ~ 0 | {idname} + {tname}"
            self._fml2 = f"{yname} ~ 0 + ATT"


    def estimate(self):

        """
        Args:
            data (pd.DataFrame): The DataFrame containing all variables.
            yname (str): The name of the dependent variable.
            _first_stage (str): The formula for the first stage.
            _second_stage (str): The formula for the second stage.
            treatment (str): The name of the treatment variable.
        Returns:
            tba
        """

        return _did2s_estimate(data, yname, _first_stage, _second_stage, treatment) # returns triple Feols, first_u, second_u


    def vcov(self):

        return _did2s_vcov(_data = _data, _first_stage = _first_stage, _second_stage = _second_stage, _first_u = _first_u, _second_u = _second_u)



def _did2s_estimate(_data: pd.DataFrame, yname : str, _first_stage: str, _second_stage: str, treatment: str):

        """
        Args:
            data (pd.DataFrame): The DataFrame containing all variables.
            yname (str): The name of the dependent variable.
            _first_stage (str): The formula for the first stage.
            _second_stage (str): The formula for the second stage.
            treatment (str): The name of the treatment variable.
        Returns:
            A fitted model object of class feols and the first and second stage residuals.
        """
        _first_stage = _first_stage.replace(" ", "")
        _second_stage = _second_stage.replace(" ", "")
        assert _first_stage[0] == "~", "First stage must start with ~"
        assert _second_stage[0] == "~", "Second stage must start with ~"

        _first_stage_full = f"{yname} {_fml1}"
        _second_stage_full = f"{yname}_hat {_fml2}"

        if treatment is not None:
            _not_yet_treated_data = data[data[treatment] == False]
        else:
            _not_yet_treated_data = data[data["ATT"] == False]

        # estimate first stage
        fit1 = feols(fml = _first_stage_full, data = _not_yet_treated_data)

        # obtain estimated fixed effects
        fit1.fixef()

        # demean data
        Y_hat = fit1.predict(newdata = _data)
        _first_u = _data[f"{_yname}"].to_numpy().flatten() - Y_hat
        _data[f"{_yname}_hat"] = self._first_u

        fit2 = feols(_second_stage_full, data = _data)
        _second_u = fit2.resid()

        return fit2, _first_u, _second_u


def _did2s_vcov(_data: pd.DataFrame, _first_stage: str, _second_stage: str, _first_u: np.ndarray, _second_u: np.ndarray, _cluster : str):

    """
    Compute a variance covariance matrix for Gardner's 2-stage Difference-in-Differences Estimator.
    Args:
        data (pd.DataFrame):

    """

    cluster_col =  _data[_cluster]
    _, clustid = pd.factorize(cluster_col)

    _G = clustid.nunique()                                      # actually not used here, neither in did2s

    X1 = model_matrix(_first_stage, _data, output = "sparse")   # here: from potential two part formula to one - part formula
    X2 = model_matrix(_second_stage, _data, output = "sparse")

    X10 = X1.copy().tocsr()
    treated_rows = np.where(_data["ATT"], 0, 1)
    X10 = X10.multiply(treated_rows[:, None])

    X10X10 = X10.T.dot(X10)
    X2X1 = X2.T.dot(X1)
    X2X2 = X2.T.dot(X2)

    V = spsolve(X10X10, X2X1.T).T

    k = X2.shape[1]
    vcov = np.zeros((k, k))

    X10 = X10.tocsr()
    X2 = X2.tocsr()

    for (_,g,) in enumerate(clustid):

        X10g = X10[cluster_col == g, :]
        X2g = X2[cluster_col == g, :]
        first_u_g = _first_u[cluster_col == g]
        second_u_g = _second_u[cluster_col == g]

        W_g = X2g.T.dot(second_u_g) - V @ X10g.T.dot(first_u_g)

        score = spsolve(X2X2, W_g)
        cov_g = score.dot(score.T)

        vcov += cov_g

    return vcov


def did2s(data: pd.DataFrame, yname : str, _first_stage: str, _second_stage: str, treatment: str, cluster: str):

    fit, first_u, second_u = _did2s_estimate(data, yname, first_stage, second_stage, treatment)
    vcov = _did2s_vcov(data, first_stage, second_stage, first_u, second_u, cluster)
    fit._vcov = vcov

    return fit










