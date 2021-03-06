"""
Copyright (C) 2013-2018 Calliope contributors listed in AUTHORS.
Licensed under the Apache 2.0 License (see LICENSE file).

model.py
~~~~~~~~

Implements the core Model class.

"""

import numpy as np

from calliope.analysis import plotting, postprocess
from calliope.core import debug, io
from calliope.core.preprocess import \
    model_run_from_yaml, \
    model_run_from_dict, \
    build_model_data, \
    apply_time_clustering, \
    final_timedimension_processing
from calliope.core.util.tools import log_time
from calliope.core.util.dataset import split_loc_techs
from calliope import exceptions
from calliope.backend.run import run as run_backend


def read_netcdf(path):
    """
    Return a Model object reconstructed from model data in a NetCDF file.

    """
    model_data = io.read_netcdf(path)
    return Model(config=None, model_data=model_data)


class Model(object):
    """
    A Calliope Model.

    """
    def __init__(self, config, model_data=None, *args, **kwargs):
        """
        Returns a new Model from either the path to a YAML model
        configuration file or a dict fully specifying the model.

        Parameters
        ----------
        config : str or dict or AttrDict
            If str, must be the path to a model configuration file.
            If dict or AttrDict, must fully specify the model.
        model_data : Dataset, optional
            Create a Model instance from a fully built model_data Dataset.
            This is only used if `config` is explicitly set to None
            and is primarily used to re-create a Model instance from
            a model previously saved to a NetCDF file.

        """
        self._timings = {}
        log_time(self._timings, 'model_creation')
        if isinstance(config, str):
            model_run, debug_data = model_run_from_yaml(config, *args, **kwargs)
            self._init_from_model_run(model_run, debug_data)
        elif isinstance(config, dict):
            model_run, debug_data = model_run_from_dict(config, *args, **kwargs)
            self._init_from_model_run(model_run, debug_data)
        elif model_data is not None and config is None:
            self._init_from_model_data(model_data)
        else:
            # expected input is a string pointing to a YAML file of the run
            # configuration or a dict/AttrDict in which the run and model
            # configurations are defined
            raise ValueError(
                'Input configuration must either be a string or a dictionary.'
            )

        self.plot = plotting.ModelPlotMethods(self)

    def _init_from_model_run(self, model_run, debug_data):
        self._model_run = model_run
        self._debug_data = debug_data
        log_time(self._timings, 'model_run_creation')

        self._model_data_original = build_model_data(model_run)
        log_time(self._timings, 'model_data_original_creation')

        random_seed = self._model_run.get_key('model.random_seed', None)
        if random_seed:
            np.random.seed(seed=random_seed)

        # After setting the random seed, time clustering can take place
        time_config = model_run.model.get('time', None)
        if not time_config:
            _model_data = self._model_data_original
        else:
            _model_data = apply_time_clustering(
                self._model_data_original, model_run
            )
        self._model_data = final_timedimension_processing(_model_data)
        log_time(self._timings, 'model_data_creation', time_since_start=True)

        for var in self._model_data.data_vars:
            self._model_data[var].attrs['is_result'] = 0
        self.inputs = self._model_data.filter_by_attrs(is_result=0)

    def _init_from_model_data(self, model_data):
        self._model_run = None
        self._debug_data = None
        self._model_data = model_data
        self.inputs = self._model_data.filter_by_attrs(is_result=0)

        results = self._model_data.filter_by_attrs(is_result=1)
        if len(results.data_vars) > 0:
            self.results = results
        log_time(self._timings, 'model_data_loaded', time_since_start=True)

    def save_debug_data(self, path):
        """
        Save fully built and commented model_run to a YAML file at the
        given path, for debug purposes.

        """
        debug.save_debug_data(self._model_run, self._debug_data, path)

    def run(self, force_rerun=False, **kwargs):
        """
        Run the model. If ``force_rerun`` is True, any existing results
        will be overwritten.

        Additional kwargs are passed to the backend.

        """

        if hasattr(self, 'results') and not force_rerun:
            raise exceptions.ModelError(
                'This model object already has results. '
                'Use model.run(force_rerun=True) to force'
                'the results to be overwritten with a new run.'
            )

        if (self._model_data.attrs['run.mode'] == 'operate' and
                not self._model_data.attrs['allow_operate_mode']):
            raise exceptions.ModelError(
                'Unable to run this model in operational mode, probably because '
                'there exist non-uniform timesteps (e.g. from time masking)'
            )

        results, self._backend_model, interface = run_backend(
            self._model_data, self._timings, **kwargs
        )

        # Add additional post-processed result variables to results
        if results.attrs.get('termination_condition', None) == 'optimal':
            results = postprocess.postprocess_model_results(
                results, self._model_data, self._timings
            )

        for var in results.data_vars:
            results[var].attrs['is_result'] = 1

        self._model_data.update(results)
        self._model_data.attrs.update(results.attrs)

        if 'run_solution_returned' in self._timings.keys():
            self._model_data.attrs['solution_time'] = (
                self._timings['run_solution_returned'] -
                self._timings['run_start']).total_seconds()
            self._model_data.attrs['time_finished'] = (
                self._timings['run_solution_returned'].strftime('%Y-%m-%d %H:%M:%S')
            )

        self.results = self._model_data.filter_by_attrs(is_result=1)

        self.backend = interface(self)

    def get_formatted_array(self, var):
        """
        Return an xr.DataArray with locs, techs, and carriers as
        separate dimensions.

        Parameters
        ----------
        var : str
            Decision variable for which to return a DataArray.

        """
        if var not in self._model_data.data_vars:
            raise KeyError("Variable {} not in Model data".format(var))

        return split_loc_techs(self._model_data[var])

    def to_netcdf(self, path):
        """
        Save complete model data (inputs and, if available, results)
        to a NetCDF file at the given ``path``.

        """
        io.save_netcdf(self._model_data, path)

    def to_csv(self, path):
        """
        Save complete model data (inputs and, if available, results)
        as a set of CSV files to the given ``path``.

        """
        io.save_csv(self._model_data, path)
