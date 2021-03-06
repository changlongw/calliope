=================
Analysing a model
=================

Calliope inputs and results are made to be very easily handled. Whatever platform you prefer to use for data processing, our NetCDF or CSV output makes it easy. If you prefer to not worry about writing your own scripts, then we have that covered too! :class:`~calliope.Model.plot` is built on plotly's interactive toolbox, to bring your data to life.

Within the xarray Datasets of ``model.inputs`` and ``model.results``, variables are indexed over concatenated sets. For instance, if a technology ``boiler`` only exists in location ``X1`` and not in locations ``X2`` or ``X3``, then we will specify parameters for just the `loc::tech` ``X1::boiler``. This can be extended to parameters which also consider ``carriers``, such that we would have a ``loc::tech::carrier`` ``X1::boiler::heat`` (avoiding empty parameter values for ``power``, as the boiler never considers that enery carrier). If a user knows the name of this concatenated set and indeces, they can index by those (e.g. ``resource_area`` is indexed over the set ``loc_techs_area``, within which are all `loc::techs` which receive their resource over an area). Otherwise, ``model.get_formatted_array('name of variable')`` can be used to produce an xarray DataArray, indexed over seperated indeces: any of `techs`, `locs`, `carriers`, `costs`, `timesteps`. This for analysis per technology, location, etc.

.. note:: On saving to CSV, all variables are formatted to separate concatenated sets.

-------------------
Visualising results
-------------------

In an interactive Python session, there are four primary visualisation functions: ``capacity``, ``timeseries``, ``transmission``, and ``summary``. ``summary`` can also be accessed from the command line interface, to gain access to result visualisation without the need to interact with Python.

Refer to the :ref:`API documentation for the analysis module<api_analysis>` for an overview of available analysis functionality.

Refer to the :doc:`tutorials <tutorials>` for some basic analysis techniques.

Plotting time series
--------------------

.. raw:: html
   :file: images/plot_timeseries.html

In Python, we get this function by calling ``model.plot.timeseries()``. It includes all relevant timeseries information, from both inputs and results. We can force it to only have particular results in the dropdown menu:

.. code-block:: python

    # Only inputs or only results
    model.plot.timeseries(array='inputs')
    model.plot.timeseries(array='results')

    # Only consumed resource
    model.plot.timeseries(array='resource_con')

    # Only consumed resource and `power` carrier flow
    model.plot.timeseries(array=['power', `resource_con`])

The data used to build the plots can also be subset and ordered by using the ``subset`` argument. This uses `xarray's 'loc' indexing functionality <http://xarray.pydata.org/en/stable/indexing.html>`_ to access subsets of data:

.. code-block:: python

    # Only show region1 data (rather than the default, which is a sum of all locations)
    model.plot.timeseries(subset={'locs': ['region1']})

    # Only show a subset of technologies
    model.plot.timeseries(subset={'techs': ['ccgt', 'csp']})

    # Assuming our model has three techs, 'ccgt', 'csp', and 'battery',
    # specifying `subset` lets us order them in the stacked barchart
    model.plot.timeseries(subset={'techs': ['ccgt', 'battery', 'csp']})

.. seealso:: :ref:`API documentation for the analysis module<api_analysis>`

Plotting capacities
-------------------

.. raw:: html
   :file: images/plot_capacity.html

Functionality is similar to timeseries, this time called by ``model.plot.capacity()``. Here we show capacity limits set at input and chosen capacities at output. Choosing dropdowns and subsetting works in the same way as for timeseries plots

Plotting transmission
---------------------

.. raw:: html
   :file: images/plot_transmission_token.html

by calling ``model.plot.transmission()`` you will see installed links, their capacities (on hover), and the locations of the nodes. This functionality only works if you have physically pinpointed your locations using the ``coordinates`` key for your location.

The above plot uses `Mapbox <https://www.mapbox.com/>`_ to overlay our transmission plot on Openstreetmap. By creating an account at Mapbox and acquiring a Mapbox access token, you can also create similar visualisations by giving the token to the plotting function: ``model.plot.transmission(mapbox_access_token='your token here')``.

Without the token, the plot will fall back on simple country-level outlines. In this urban scale example, the background is thus just grey (zoom out to see the UK!):

.. raw:: html
   :file: images/plot_transmission.html

.. note:: If the coordinates were in `x` and `y`, not `lat` and `lon`, the transmission trace would be given on a cartesian plot.

Summary plots
-------------
If you want all the data in one place, you can run ``model.plot.summary(out_file='path/to/file.html')``, which will build a HTML file of all the interactive plots (maintaining the interactivity) and save it to ``out_file``. By clocking on this HTML file, a browser tab will pop up with the plots. This funcionality is made avaiable in the command line interface by using the command ``--save_plots=filename.html`` when running the model.

.. seealso:: :ref:`running_cli`

Saving publication-quality SVG figures
--------------------------------------

On calling any of the three primary plotting functions, you can also set ``save_svg=True`` for a high quality vector graphic to be saved. This file can be prepared for publication in programs like `Inkscape <https://inkscape.org/en/>`_.

.. note::

    For similar results in the command line interface, you'll currently need to save your model to netcdf (``--save_netcdf={filename.nc}``) then load it into a Calliope Model object in Python. Once there, you can use the above functions to get your SVGs.

-----------------
Reading solutions
-----------------

Calliope provides functionality to read a previously-saved model from a single NetCDF file:

.. code-block:: python

   solved_model = calliope.read_netcdf('my_saved_model.nc')

In the above example, the model's input data will be available under ``solved_model.inputs``, while the results (if the model had previously been solved) are available under ``solved_model.results``.

Both of these are `xarray.Datasets <http://xarray.pydata.org/en/stable/data-structures.html#dataset>`_ and can be further processed with Python.

.. seealso:: The `xarray documentation <http://xarray.pydata.org/en/stable/>`_ should be consulted for further information on dealing with Datasets. Calliope's NetCDF files follow the `CF conventions <http://cfconventions.org/>`_ and can easily be processed with any other tool that can deal with NetCDF.
