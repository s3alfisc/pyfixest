import numpy as np
from pyfixest.feols import Feols, _drop_multicollinear_variables


class Feiv(Feols):

    """
    A class to estimate an IV model using a 2SLS estimator. Inherits from the Feols class.
    Users should not call this class directly, but rather use the feols() function.

    Users should not directly instantiate this class, but rather use the [feols()](/docs/reference/estimation.feols.qmd) function.

    Parameters
    ----------
    Y : np.ndarray
        Dependent variable, a two-dimensional np.array.
    X : np.ndarray
        Independent variables, a two-dimensional np.array.
    Z : np.ndarray
        Instruments, a two-dimensional np.array.
    weights : np.ndarray
        Weights, a one-dimensional np.array.
    coefnames_x : list
        Names of the coefficients of X.
    coefnames_z : list
        Names of the coefficients of Z.
    collin_tol : float
        Tolerance for collinearity check.

    Attributes
    ----------
    _Z : np.ndarray
        Processed instruments after handling multicollinearity.
    _coefnames_z : list
        Names of coefficients for Z after handling multicollinearity.
    _collin_vars_z : list
        Variables identified as collinear in Z.
    _collin_index_z : list
        Indices of collinear variables in Z.
    _is_iv : bool
        Indicator if instrumental variables are used.
    _support_crv3_inference : bool
        Indicator for supporting CRV3 inference.
    _support_iid_inference : bool
        Indicator for supporting IID inference.
    _tZX : np.ndarray
        Transpose of Z times X.
    _tXZ : np.ndarray
        Transpose of X times Z.
    _tZy : np.ndarray
        Transpose of Z times Y.
    _tZZinv : np.ndarray
        Inverse of transpose of Z times Z.
    _beta_hat : np.ndarray
        Estimated regression coefficients.
    _Y_hat_link : np.ndarray
        Predicted values of the regression model.
    _u_hat : np.ndarray
        Residuals of the regression model.
    _scores : np.ndarray
        Scores used in the regression.
    _hessian : np.ndarray
        Hessian matrix used in the regression.
    _bread : np.ndarray
        Bread matrix used in the regression.

    Raises
    ------
    ValueError
        If Z is not a two-dimensional array.

    """
    # Constructor and methods implementation...


    def __init__(
        self,
        Y: np.ndarray,
        X: np.ndarray,
        Z: np.ndarray,
        weights: np.ndarray,
        coefnames_x: list,
        coefnames_z: list,
        collin_tol: float,
    ) -> None:

        super().__init__(
            Y=Y, X=X, weights=weights, coefnames=coefnames_x, collin_tol=collin_tol
        )

        # import pdb; pdb.set_trace()

        # check if Z is two dimensional array
        if len(Z.shape) != 2:
            raise ValueError("Z must be a two-dimensional array")

        # handle multicollinearity in Z
        (
            self._Z,
            self._coefnames_z,
            self._collin_vars_z,
            self._collin_index_z,
        ) = _drop_multicollinear_variables(Z, coefnames_z, self._collin_tol)

        self._is_iv = True

        self._support_crv3_inference = False
        self._support_iid_inference = True

    def get_fit(self) -> None:

        _X = self._X
        _Z = self._Z
        _Y = self._Y

        self._tZX = _Z.T @ _X
        self._tXZ = _X.T @ _Z
        self._tZy = _Z.T @ _Y
        self._tZZinv = np.linalg.inv(_Z.T @ _Z)

        H = self._tXZ @ self._tZZinv
        A = H @ self._tZX
        B = H @ self._tZy

        self._beta_hat = np.linalg.solve(A, B).flatten()

        self._Y_hat_link = self._X @ self._beta_hat
        self._u_hat = self._Y.flatten() - self._Y_hat_link.flatten()

        self._scores = self._Z * self._u_hat[:, None]
        self._hessian = self._Z.transpose() @ self._Z

        D = np.linalg.inv(self._tXZ @ self._tZZinv @ self._tZX)
        self._bread = (H.T) @ D @ H
