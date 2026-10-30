"""Reference datasets for engine validation.

AIAG_* datasets are the worked examples of the AIAG MSA Reference Manual, 4th ed.
(2010), Chapter III. They were transcribed for this test suite; the transcription is
checked by reproducing every intermediate value the manual publishes (appraiser
averages and ranges, R-bar, X-diff, Rp, ANOVA sums of squares). Expected values carry
the manual's rounding, so comparisons use a tolerance consistent with it.
"""

# GRR example: 3 appraisers (A, B, C) x 3 trials x 10 parts. GRR_AIAG[appraiser][trial] -> 10 parts.
GRR_AIAG = {
    "A": [[0.29, -0.56, 1.34, 0.47, -0.80, 0.02, 0.59, -0.31, 2.26, -1.36],
          [0.41, -0.68, 1.17, 0.50, -0.92, -0.11, 0.75, -0.20, 1.99, -1.25],
          [0.64, -0.58, 1.27, 0.64, -0.84, -0.21, 0.66, -0.17, 2.01, -1.31]],
    "B": [[0.08, -0.47, 1.19, 0.01, -0.56, -0.20, 0.47, -0.63, 1.80, -1.68],
          [0.25, -1.22, 0.94, 1.03, -1.20, 0.22, 0.55, 0.08, 2.12, -1.62],
          [0.07, -0.68, 1.34, 0.20, -1.28, 0.06, 0.83, -0.34, 2.19, -1.50]],
    "C": [[0.04, -1.38, 0.88, 0.14, -1.46, -0.29, 0.02, -0.46, 1.77, -1.49],
          [-0.11, -1.13, 1.09, 0.20, -1.07, -0.67, 0.01, -0.56, 1.45, -1.77],
          [-0.15, -0.96, 0.67, 0.11, -1.45, -0.49, 0.21, -0.49, 1.87, -2.16]],
}
# Published Average & Range results (GRR report form).
GRR_AIAG_AR = {"r_bar": 0.3417, "x_diff": 0.4446, "rp": 3.511, "ev": 0.20188, "av": 0.22963, "grr": 0.30575,
               "pv": 1.10456, "tv": 1.14610, "pct_ev": 17.62, "pct_av": 20.04, "pct_grr": 26.68, "pct_pv": 96.38,
               "ndc": 5}
GRR_AIAG_AVERAGES = {"A": 0.1903, "B": 0.0683, "C": -0.2543}
GRR_AIAG_RANGES = {"A": 0.184, "B": 0.513, "C": 0.328}
# Published ANOVA table (sums of squares and degrees of freedom).
GRR_AIAG_ANOVA_SS = {"Appraiser": (2, 3.1673), "Parts": (9, 88.3619), "Appraiser x Part": (18, 0.3590),
                     "Equipment": (60, 2.7589), "Total": (89, 94.6471)}

# Bias example: reference 6.00, 15 readings.
BIAS_AIAG = {"reference": 6.00,
             "values": [5.8, 5.7, 5.9, 5.9, 6.0, 6.1, 6.0, 6.1, 6.4, 6.3, 6.0, 6.1, 6.2, 5.6, 6.0],
             "expected": {"bias": 0.0067, "s": 0.2120, "sigma_b": 0.05474, "ci_low": -0.1107, "ci_high": 0.1241}}

# Linearity example: 5 reference parts x 12 trials.
LINEARITY_AIAG = {
    "parts": {2.0: [2.70, 2.50, 2.40, 2.50, 2.70, 2.30, 2.50, 2.50, 2.40, 2.40, 2.60, 2.40],
              4.0: [5.10, 3.90, 4.20, 5.00, 3.80, 3.90, 3.90, 3.90, 3.90, 4.00, 4.10, 3.80],
              6.0: [5.80, 5.70, 5.90, 5.90, 6.00, 6.10, 6.00, 6.10, 6.40, 6.30, 6.00, 6.10],
              8.0: [7.60, 7.70, 7.80, 7.70, 7.80, 7.80, 7.80, 7.70, 7.80, 7.50, 7.60, 7.70],
              10.0: [9.10, 9.30, 9.50, 9.30, 9.40, 9.50, 9.50, 9.50, 9.60, 9.20, 9.30, 9.40]},
    "expected": {"bias_averages": [0.491667, 0.125, 0.025, -0.291667, -0.616667], "slope": -0.131667,
                 "intercept": 0.736667, "r_squared": 0.71},
}

# Fleiss, J. L. (1971) worked example as reproduced in the literature: 10 subjects,
# 14 raters, 5 categories (counts per category). Published kappa = 0.210.
FLEISS_EXAMPLE = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
                  [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]


def grr_observations(data=GRR_AIAG):
    return [{"operator": op, "part": str(p + 1), "trial": t + 1, "value": v}
            for op, trials in data.items() for t, row in enumerate(trials) for p, v in enumerate(row)]


def linearity_observations():
    return [{"part": f"P{i + 1}", "reference": ref, "trial": t + 1, "value": v}
            for i, (ref, vals) in enumerate(LINEARITY_AIAG["parts"].items()) for t, v in enumerate(vals)]
