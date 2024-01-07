import numpy as np
import pandas as pd
import warnings


from typing import Union, Optional, List
from pyfixest.feols import Feols
from pyfixest.demean import demean
from pyfixest.exceptions import (
    NonConvergenceError,
    NotImplementedError,
)


class Fepois(Feols):

    """
    Class to estimate Poisson Regressions. Inherits from Feols. The following methods are overwritten: `get_fit()`.

    Attributes
    ----------
    fe : np.ndarray
        Fixed effects as a numpy array.
    maxiter : Optional[int]
        Maximum number of iterations for the Iteratively Reweighted Least Squares (IRLS) algorithm.
    tol : Optional[float]
        Tolerance level for the convergence of the IRLS algorithm.
    _drop_singletons : bool
        Indicates whether to drop singleton fixed effects.
    _method : str
        The method used for estimation, set to "fepois".
    convergence : bool
        Indicates whether the model has converged.
    _support_crv3_inference : bool
        Support for crv3 inference.
    _support_iid_inference : bool
        Support for iid inference.
    _Y_hat_response : np.ndarray or None
        The estimated dependent variable at the response level.
    deviance : np.ndarray or None
        The deviance of the model.
    _Xbeta : np.ndarray or None
        The linear predictor X @ beta.

    Methods
    -------
    __init__(Y, X, fe, weights, coefnames, drop_singletons, collin_tol, maxiter=25, tol=1e-08)
        Initialize the Fepois class with given parameters.
    get_fit()
        Fit a Poisson Regression Model via Iteratively Reweighted Least Squares.
    predict(newdata=None, type="link")
        Return predicted values of the regression model.
    """

    def __init__(
        self,
        Y: np.ndarray,
        X: np.ndarray,
        fe: np.ndarray,
        weights: np.ndarray,
        coefnames: List[str],
        drop_singletons: bool,
        collin_tol: float,
        maxiter: Optional[int] = 25,
        tol: Optional[float] = 1e-08,
    ):

        """
        Initialize the Fepois class with given parameters.

        Parameters
        ----------
        Y : np.ndarray
            Dependent variable, a two-dimensional numpy array.
        X : np.ndarray
            Independent variables, a two-dimensional numpy array.
        fe : np.ndarray
            Fixed effects, a two-dimensional numpy array or None.
        weights : np.ndarray
            Weights, a one-dimensional numpy array or None.
        coefnames : List[str]
            Names of the coefficients in the design matrix X.
        drop_singletons : bool
            Whether to drop singleton fixed effects.
        collin_tol : float
            Tolerance level for the detection of collinearity.
        maxiter : Optional[int], default 25
            Maximum number of iterations for the IRLS algorithm.
        tol : Optional[float], default 1e-08
            Tolerance level for the convergence of the IRLS algorithm.
        """

        super().__init__(
            Y=Y, X=X, weights=weights, coefnames=coefnames, collin_tol=collin_tol
        )

        # input checks
        _fepois_input_checks(fe, drop_singletons, tol, maxiter)

        self.fe = fe
        self.maxiter = maxiter
        self.tol = tol
        self._drop_singletons = drop_singletons
        self._method = "fepois"
        self.convergence = False

        if self.fe is not None:
            self._has_fixef = True
        else:
            self._has_fixef = False

        # check if Y is a weakly positive integer
        self._Y = _to_integer(self._Y)
        # check that self._Y is a weakly positive integer
        if np.any(self._Y < 0):
            raise ValueError(
                "The dependent variable must be a weakly positive integer."
            )

        self._support_crv3_inference = True
        self._support_iid_inference = True

        self._Y_hat_response = None
        self.deviance = None
        self._Xbeta = None

    def get_fit(self) -> None:
        """
        Fit a Poisson Regression Model via Iterated Weighted Least Squares.

        Returns
        -------
        None
        """

        _Y = self._Y
        _X = self._X
        _fe = self.fe
        _N = self._N
        _drop_singletons = self._drop_singletons
        _convergence = self.convergence  # False
        _maxiter = self.maxiter
        _iwls_maxiter = 25
        _tol = self.tol

        def compute_deviance(_Y, mu):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                deviance = (
                    2 * np.sum(np.where(_Y == 0, 0, _Y * np.log(_Y / mu)) - (_Y - mu))
                ).flatten()
            return deviance

        accelerate = True
        # inner_tol = 1e-04
        stop_iterating = False
        crit = 1

        for i in range(_maxiter):
            if stop_iterating:
                _convergence = True
                break
            if i == _maxiter:
                raise NonConvergenceError(
                    f"The IRLS algorithm did not converge with {_iwls_maxiter} iterations. Try to increase the maximum number of iterations."
                )

            if i == 0:
                _mean = np.mean(_Y)
                mu = (_Y + _mean) / 2
                eta = np.log(mu)
                Z = eta + _Y / mu - 1
                last_Z = Z.copy()
                reg_Z = Z.copy()
                last = compute_deviance(_Y, mu)

            elif accelerate:
                last_Z = Z.copy()
                Z = eta + _Y / mu - 1
                reg_Z = Z - last_Z + Z_resid
                X = X_resid.copy()

            else:
                # update w and Z
                Z = eta + _Y / mu - 1  # eq (8)
                reg_Z = Z.copy()  # eq (9)

            # tighten HDFE tolerance - currently not possible with PyHDFE
            # if crit < 10 * inner_tol:
            #    inner_tol = inner_tol / 10

            # Step 1: weighted demeaning
            ZX = np.concatenate([reg_Z, _X], axis=1)

            if _fe is not None:
                # ZX_resid = algorithm.residualize(ZX, mu)
                ZX_resid, success = demean(x=ZX, flist=_fe, weights=mu.flatten())
                if success == False:
                    raise ValueError("Demeaning failed after 100_000 iterations.")
            else:
                ZX_resid = ZX

            Z_resid = ZX_resid[:, 0].reshape((_N, 1))  # z_resid
            X_resid = ZX_resid[:, 1:]  # x_resid

            # Step 2: estimate WLS
            WX = np.sqrt(mu) * X_resid
            WZ = np.sqrt(mu) * Z_resid

            XWX = WX.transpose() @ WX
            XWZ = WX.transpose() @ WZ

            delta_new = np.linalg.solve(XWX, XWZ)  # eq (10), delta_new -> reg_z
            resid = Z_resid - X_resid @ delta_new

            mu_old = mu.copy()
            # more updating
            eta = Z - resid
            mu = np.exp(eta)

            # same criterion as fixest
            # https://github.com/lrberge/fixest/blob/6b852fa277b947cea0bad8630986225ddb2d6f1b/R/ESTIMATION_FUNS.R#L2746
            deviance = compute_deviance(_Y, mu)
            crit = np.abs(deviance - last) / (0.1 + np.abs(last))
            last = deviance.copy()

            stop_iterating = crit < _tol

        self._beta_hat = delta_new.flatten()
        self._Y_hat_response = mu
        self._Y_hat_link = eta
        # (Y - self._Y_hat)
        # needed for the calculation of the vcov

        # updat for inference
        self._weights = mu_old
        # if only one dim
        if self._weights.ndim == 1:
            self._weights = self._weights.reshape((self._N, 1))

        self._u_hat = resid.flatten()

        self._Y = Z_resid
        self._X = X_resid
        self._Z = self._X
        self.deviance = deviance

        self._tZX = np.transpose(self._Z) @ self._X
        self._tZXinv = np.linalg.inv(self._tZX)
        self._Xbeta = eta

        self._scores = self._u_hat[:, None] * self._weights * X_resid
        self._hessian = XWX
        self._T = self._weights * X_resid

        if _convergence:
            self._convergence = True

    def predict(
        self, newdata: Optional[pd.DataFrame] = None, type="link"
    ) -> np.ndarray:
        """
        Return a flat numpy array with predicted values of the regression model.

        Parameters
        ----------
        newdata : Optional[pd.DataFrame], default None
            A pandas DataFrame with the new data, to be used for prediction.
            If None, uses the data used for fitting the model.
        type : str, default "link"
            The type of prediction to be computed. Either "response" or "link".

        Returns
        -------
        np.ndarray
            Predicted values of the regression model.
        """

        _Xbeta = self._Xbeta
        _has_fixef = self._has_fixef

        if _has_fixef:
            raise NotImplementedError(
                "Prediction with fixed effects is not yet implemented for Poisson regression."
            )
        if newdata is not None:
            raise NotImplementedError(
                "Prediction with function argument `newdata` is not yet implemented for Poisson regression."
            )

        if type not in ["response", "link"]:
            raise ValueError("type must be one of 'response' or 'link'.")

        y_hat = super().predict(data=newdata)
        if type == "link":
            y_hat = np.exp(y_hat)

        return y_hat


def _check_for_separation(Y: pd.DataFrame, fe: pd.DataFrame, check: str = "fe") -> List:
    """
    Check for separation in Poisson Regression.

    For details on separation checks, refer to the pplmhdfe documentation.
    Currently, only the "fe" check is implemented.

    Parameters
    ----------
    Y : pd.DataFrame
        Dependent variable.
    fe : pd.DataFrame
        Fixed effects.
    check : str
        Separation check to be performed.

    Returns
    -------
    list
        List of indices of observations that are removed due to separation.
    """

    if check == "fe":
        if (Y > 0).all().bool():
            pass
        else:
            Y_help = (Y > 0).astype(int).squeeze()

            separation_na = set()
            # loop over all elements of fe
            for x in fe.columns:
                ctab = pd.crosstab(Y_help, fe[x])
                null_column = ctab.xs(0)
                # sep_candidate if
                # fixed effect level has only observations with Y > 0
                sep_candidate = (np.sum(ctab > 0, axis=0).values == 1) & (
                    null_column > 0
                ).values.flatten()
                # droplist: list of levels to drop
                droplist = ctab.xs(0)[sep_candidate].index.tolist()

                # dropset: list of indices to drop
                if len(droplist) > 0:
                    fe_in_droplist = fe[x].isin(droplist)
                    dropset = set(fe[x][fe_in_droplist].index)
                    separation_na = separation_na.union(dropset)

            separation_na = list(separation_na)

            return separation_na

    else:
        raise NotImplementedError(
            f"Separation check via {check} is not implemented yet."
        )


def _fepois_input_checks(fe, drop_singletons, tol, maxiter):
    # fe must be np.array of dimension 2 or None
    if fe is not None:
        if not isinstance(fe, np.ndarray):
            raise AssertionError("fe must be a numpy array.")
        if fe.ndim != 2:
            raise AssertionError("fe must be a numpy array of dimension 2.")
    # drop singletons must be logical
    if not isinstance(drop_singletons, bool):
        raise AssertionError("drop_singletons must be logical.")
    # tol must be numeric and between 0 and 1
    if not isinstance(tol, (int, float)):
        raise AssertionError("tol must be numeric.")
    if tol <= 0 or tol >= 1:
        raise AssertionError("tol must be between 0 and 1.")
    # maxiter must be integer and greater than 0
    if not isinstance(maxiter, int):
        raise AssertionError("maxiter must be integer.")
    if maxiter <= 0:
        raise AssertionError("maxiter must be greater than 0.")


def _to_integer(x):
    if x.dtype == int:
        return x
    else:
        try:
            x = x.astype(np.int64)
            return x
        except ValueError:
            raise ValueError(
                "Conversion of the dependent variable to integer is not possible. Please do so manually."
            )
