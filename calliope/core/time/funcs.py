"""
Copyright (C) 2013-2018 Calliope contributors listed in AUTHORS.
Licensed under the Apache 2.0 License (see LICENSE file).

funcs.py
~~~~~~~~

Functions to process time series data.

"""

import logging

import pandas as pd
import xarray as xr

from calliope.core.util.tools import plugin_load
from calliope.core.util.dataset import get_loc_techs
from calliope.core.time import clustering


def normalized_copy(data):
    """
    Normalize timeseries data, using the maximum across all regions and timesteps.

    Parameters
    ----------
    data : xarray Dataset
        Dataset with all non-time dependent variables removed

    Returns
    -------
    ds : xarray Dataset
        Copy of `data`, with the absolute taken and normalized to 0-1

    """
    ds = data.copy(deep=True)  # Work off a copy

    for var in ds.data_vars:
        # Each DataArray is indexed over a different subset of loc_techs,
        # so we find it in the list of dimensions
        loc_tech_dim = [i for i in ds[var].dims if 'loc_techs' in i][0]

        # For each technology, get the loc_techs which are relevant
        loc_tech_subsets = [
            get_loc_techs(ds[loc_tech_dim].values, tech)
            for tech in set(i.split('::')[1] for i in ds[loc_tech_dim].values)
        ]
        # remove empty lists within the _techs list
        loc_tech_subsets = [i for i in loc_tech_subsets if i]

        # For each technology, divide all values by the maximum absolute value
        for loc_tech in loc_tech_subsets:
            ds[var].loc[{loc_tech_dim: loc_tech}] = abs(
                ds[var].loc[{loc_tech_dim: loc_tech}] /
                abs(ds[var].loc[{loc_tech_dim: loc_tech}]).max()
            )
    return ds


def _copy_non_t_vars(data0, data1):
    """Copies non-t-indexed variables from data0 into data1, then
    returns data1"""
    non_t_vars = [v for v in data0.data_vars
                  if 'timesteps' not in data0[v].dims]
    # Manually copy over variables not in `t`. If we don't do this,
    # these vars get polluted with a superfluous `t` dimension
    for v in non_t_vars:
        data1[v] = data0[v]
    return data1


def _combine_datasets(data0, data1):
    """Concatenates data0 and data1 along the time dimension"""
    data_new = xr.concat([data0, data1], dim='timesteps')
    # Ensure time dimension is ordered
    data_new = data_new.loc[
        {'timesteps': data_new.timesteps.to_index().sort_values()}
    ]

    return data_new


def apply_clustering(data, timesteps, clustering_func, how, normalize=True, **kwargs):
    """
    Apply the given clustering function to the given data.

    Parameters
    ----------
    data : xarray.Dataset
    timesteps : pandas.DatetimeIndex or list of timesteps or None
    clustering_func : str
        Name of clustering function.
    how : str
        How to map clusters to data. 'mean' or 'closest'.
    normalize : bool, optional
        If True (default), data is normalized before clustering is applied,
        using :func:`~calliope.core.time.funcs.normalized_copy`.
    **kwargs : optional
        Arguments passed to clustering_func.

    Returns
    -------
    data_new_scaled : xarray.Dataset

    """

    # Save all coordinates, to ensure they can be added back in after clustering
    data_coords = data.copy().coords
    del data_coords['timesteps']
    # Only apply clustering function on subset of masked timesteps
    if timesteps is None:
        data_to_cluster = data
    else:
        data_to_cluster = data.loc[{'timesteps': timesteps}]

    # remove all variables that are not indexed over time
    data_to_cluster = data_to_cluster.drop([
        i for i in data.variables
        if 'timesteps' not in data[i].dims or 'timestep_' in i
    ])

    for dim in data_to_cluster.dims:
        data_to_cluster[dim] = data[dim]

    if normalize:
        data_normalized = normalized_copy(data_to_cluster)
    else:
        data_normalized = data_to_cluster

    # Get function from `clustering_func` string
    func = plugin_load(clustering_func, builtin_module='calliope.core.time.clustering')

    result = func(data_normalized, **kwargs)
    clusters = result[0]  # Ignore other stuff returned

    data_new = clustering.map_clusters_to_data(data_to_cluster, clusters,
                                               how=how)

    if timesteps is None:
        data_new = _copy_non_t_vars(data, data_new)
    else:
        # Drop timesteps from old data
        data_new = _copy_non_t_vars(data, data_new)
        data_new = _combine_datasets(data.drop(timesteps, dim='timesteps'), data_new)
        data_new = _copy_non_t_vars(data, data_new)

    # It's now safe to add the original coordiantes back in (preserving all the
    # loc_tech sets that aren't used to index a variable in the DataArray)
    data_new.update(data_coords)

    # Scale the new/combined data so that the mean for each (x, y, variable)
    # combination matches that from the original data
    data_new_scaled = data_new.copy(deep=True)
    data_vars_in_t = [
        v for v in data_new.data_vars
        if 'timesteps' in data_new[v].dims and
        'timestep_' not in v]
    for var in data_vars_in_t:
        scale_to_match_mean = (data[var].mean(dim='timesteps') /
            data_new[var].mean(dim='timesteps')).fillna(0)
        data_new_scaled[var] = data_new[var] * scale_to_match_mean

    return data_new_scaled


def resample(data, timesteps, resolution):
    """
    Function to resample timeseries data from the input resolution (e.g. 1H), to
    the given resolution (e.g. 2H)

    Parameters
    ----------
    data : xarray.Dataset
        calliope model data, containing only timeseries data variables
    timesteps : str or list; optional
        If given, apply resampling to a subset of the timeseries data
    resolution : str
        time resolution of the output data, given in Pandas time frequency format.
        E.g. 1H = 1 hour, 1W = 1 week, 1M = 1 month, 1T = 1 minute. Multiples allowed.

    """
    data_new = data.copy(deep=True)
    if timesteps is not None:
        data_new = data_new.loc[{'timesteps': timesteps}]

    # First create a new resampled dataset of the correct size by
    # using first-resample, which should be a quick way to achieve this
    data_rs = data_new.resample(resolution, dim='timesteps', how='first')

    timestep_vars = [v for v in data_new.data_vars
                     if 'timesteps' in data_new[v].dims]

    # Resampling adds spurious `time` dimension to non-time vars, correct that
    for v in data_rs.data_vars:
        if v not in timestep_vars:
            data_rs[v] = data[v]

    for var in timestep_vars:
        if var in ['timestep_resolution', 'resource']:
            data_rs[var] = data_new[var].resample(
                resolution, dim='timesteps', how='sum'
            )
        else:
            try:
                data_rs[var] = data_new[var].resample(
                    resolution, dim='timesteps', how='mean'
                )
            except TypeError:
                # If the var has a datatype of strings, it can't be resampled
                logging.error('Dropping {} because it has a {} data type when '
                              'integer or float is expected for timeseries '
                              'resampling.'.format(var, data_rs[var].dtype))
                data_rs = data_rs.drop(var)

    # Get rid of the filled-in NaN timestamps
    data_rs = data_rs.dropna(dim='timesteps', how='all')

    # repopulate the attribute dictionary, as it will have been lost along the way
    data_rs.attrs.update(data.attrs)
    data_rs.attrs['allow_operate_mode'] = 1  # Resampling still permits operational mode

    if timesteps is not None:
        # Combine leftover parts of passed in data with new data
        data_rs = _copy_non_t_vars(data, data_rs)
        data_rs = _combine_datasets(data.drop(timesteps, dim='timesteps'), data_rs)
        data_rs = _copy_non_t_vars(data, data_rs)
        # Having timesteps with different lengths does not permit operational mode
        data_rs.attrs['allow_operate_mode'] = 0

    return data_rs


def drop(data, timesteps, padding=None):
    """
    Drop timesteps from data, with optional padding
    around into the contiguous areas encompassed by the timesteps.

    """
    if padding:
        timesteps_per_day = len(data.attrs['_daily_timesteps'])
        freq = '{}H'.format(24 / timesteps_per_day)

        # Series of 1 where timesteps 'exist' and 0 where they don't
        s = (pd.Series(1, index=timesteps)
               .reindex(pd.date_range(timesteps[0], timesteps[-1], freq=freq))
               .fillna(0))

        # Blocks of contiguous 1's in the series
        blocks = (s != s.shift()).cumsum().drop(s[s==0].index)

        # Groups of contiguous areas
        groups = blocks.groupby(blocks).apply(lambda x: (x.index[0], x.index[-1]))

        # Reduce size of each block by `padding` on both sides
        padding = pd.Timedelta(padding)
        dt_indices = [pd.date_range(g[0] + padding, g[1] - padding, freq=freq)
                      for g in groups]

        # Concatenate the DatetimeIndexes by using dummy Series
        timesteps = pd.concat([pd.Series(0, index=i) for i in dt_indices]).index

    # 'Distribute weight' of the dropped timesteps onto the remaining ones
    dropped_weight = data.timestep_weights.loc[{'timesteps': timesteps}].sum()

    data = data.drop(timesteps, dim='timesteps')

    data['timestep_weights'] = data['timestep_weights'] + (dropped_weight / len(data['timestep_weights']))

    return data
