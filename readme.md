Readme
================

![](figures/pyfixest-logo.png)

------------------------------------------------------------------------

## PyFixest: Fast High-Dimensional Fixed Effects Regression in Python

[![PyPI -
Version](https://img.shields.io/pypi/v/pyfixest.svg)](https://pypi.org/project/pyfixest/)
![PyPI - Python
Version](https://img.shields.io/pypi/pyversions/pyfixest.svg) ![PyPI -
Downloads](https://img.shields.io/pypi/dm/pyfixest.png)
[![image](https://codecov.io/gh/s3alfisc/pyfixest/branch/master/graph/badge.svg)](https://codecov.io/gh/s3alfisc/pyfixest)

`PyFixest` is a Python implementation of the formidable
[fixest](https://github.com/lrberge/fixest) package. The package aims to
mimic `fixest` syntax and functionality as closely as Python allows. For
a quick introduction, see the
[tutorial](https://s3alfisc.github.io/pyfixest/tutorial/) or take a look
at the regression chapter of [Arthur
Turrell’s](https://github.com/aeturrell) book on [Coding for
Economists](https://aeturrell.github.io/coding-for-economists/econmt-regression.html#imports).

`PyFixest` supports

-   OLS and IV Regression
-   Poisson Regression
-   Multiple Estimation Syntax
-   Several Robust and Cluster Robust Variance-Covariance Types
-   Wild Cluster Bootstrap Inference (via
    [wildboottest](https://github.com/s3alfisc/wildboottest))
-   Difference-in-Difference Estimators:
    -   The canonical Two-Way Fixed Effects Estimator
    -   [Gardner’s two-stage
        (“`Did2s`”)](https://jrgcmu.github.io/2sdd_current.pdf)
        estimator
    -   Basic Versions of the Local Projections estimator following
        [Dube et al (2023)](https://www.nber.org/papers/w31184)

## Installation

You can install the release version from `PyPi` by running

``` py
pip install pyfixest
```

or the development version from github by running

``` py
pip install git+https://github.com/s3alfisc/pyfixest.git
```

## News

`PyFixest` `0.13` adds support for the [local projections
Difference-in-Differences
Estimator](https://s3alfisc.github.io/pyfixest/difference-in-differences-estimation/).

## Benchmarks

All benchmarks follow the [fixest
benchmarks](https://github.com/lrberge/fixest/tree/master/_BENCHMARK).
All non-pyfixest timings are taken from the `fixest` benchmarks.

![](./benchmarks/lets-plot-images/benchmarks_ols.svg)
![](./benchmarks/lets-plot-images/benchmarks_poisson.svg)

## Quickstart

### Fixed Effects Regression via `feols()`

You can estimate a linear regression models just as you would in
`fixest` - via `feols()`:

``` python
from pyfixest.estimation import feols, fepois
from pyfixest.utils import get_data
from pyfixest.summarize import etable

data = get_data()
feols("Y ~ X1 | f1 + f2", data=data).summary()
```

### Multiple Estimation

You can estimate multiple models at once by using [multiple estimation
syntax](https://aeturrell.github.io/coding-for-economists/econmt-regression.html#multiple-regression-models):

``` python
# OLS Estimation: estimate multiple models at once
fit = feols("Y + Y2 ~X1 | csw0(f1, f2)", data = data, vcov = {'CRV1':'group_id'})
# Print the results
etable([fit.fetch_model(i) for i in range(6)])
```

### Adjust Standard Errors “on-the-fly”

Standard Errors can be adjusted after estimation, “on-the-fly”:

``` python
fit1 = fit.fetch_model(0)
fit1.vcov("hetero").summary()
```

### Poisson Regression via `fepois()`

You can estimate Poisson Regressions via the `fepois()` function:

``` python
poisson_data = get_data(model = "Fepois")
fepois("Y ~ X1 + X2 | f1 + f2", data = poisson_data).summary()
```

### IV Estimation via three-part formulas

Last, `PyFixest` also supports IV estimation via three part formula
syntax:

``` python
fit_iv = feols("Y ~ 1 | f1 | X1 ~ Z1", data = data)
fit_iv.summary()
```
