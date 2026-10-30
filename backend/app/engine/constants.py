"""Tabulated constants used by the engine, with their sources.

Every value here is copied from a published table; nothing is fitted or approximated.
If a design needs a constant outside these tables the engine rejects the design instead
of extrapolating.
"""

# AIAG SPC Manual, 2nd ed. (2005), Appendix E "Table of Constants and Formulas for Control
# Charts", printed pp. 181-182: subgroup size -> constant.
D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}
A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}
# D3 is "-" (no lower limit) for n <= 6.
D3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223}
D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777}
# Individuals chart (moving range of 2): E2 and the n=2 range constants.
E2 = 2.660

# AIAG MSA 4th ed. (2010), Chapter III Section B, Average and Range method (GRR report
# form). K1 = 1/d2* for the number of trials (g = parts x appraisers > 15), K2 = 1/d2* for
# the number of appraisers (g = 1), K3 = 1/d2* for the number of parts (g = 1).
K1 = {2: 0.8862, 3: 0.5908}
K2 = {2: 0.7071, 3: 0.5231}
K3 = {2: 0.7071, 3: 0.5231, 4: 0.4467, 5: 0.4030, 6: 0.3742, 7: 0.3534, 8: 0.3375, 9: 0.3249, 10: 0.3146}

# AIAG MSA 4th ed.: number of distinct categories, ndc = 1.41 * (PV / GRR), truncated.
NDC_FACTOR = 1.41
