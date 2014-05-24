"""
Copyright (C) 2013 Stefan Pfenninger.
Licensed under the Apache 2.0 License (see LICENSE file).

planning.py
~~~~~~~~~~~

Planning constraints.

"""

from __future__ import print_function
from __future__ import division

import coopr.pyomo as cp


def system_margin(model):
    """
    Depends on:
    """
    m = model.m
    time_res = model.data.time_res_series

    def carrier(y):
        return model.get_option(y + '.carrier')

    # Constraint rules
    def c_system_margin_rule(m, c):
        # If no margin defined for a carrier, use 0 (i.e. no margin)
        margin = model.config_model.system_margin.get_key(c, default=0)
        if margin:
            t = model.t_max_demand[c]
            return (sum(m.es_prod[c, y, x, t] for y in m.y for x in m.x)
                    * (1 + margin)
                    <= time_res.at[t]
                    * sum((m.e_cap[y, x] / model.get_eff_ref('e', y, x))
                          for y in m.y if carrier(y) == c
                          for x in m.x))
        else:
            return cp.Constraint.NoConstraint

    # Constraints
    m.c_system_margin = cp.Constraint(m.c)