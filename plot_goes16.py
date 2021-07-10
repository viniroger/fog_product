#!/usr/bin/env python3.9.5
# -*- Coding: UTF-8 -*-

import os
from helpers.utilities import Utilities

# INPUT VARIABLES - Extent and Datetime
extent = [-60.0, -35.0, -45.0, -25.0] # Min lon, Max lon, Min lat, Max lat
yyyymmddhhmn = '202107071000'
band = '7'

# Check/create input and output directories
input = 'input'; os.makedirs(input, exist_ok=True)
output = 'output'; os.makedirs(output, exist_ok=True)

# Download the file
file_name = Utilities.download_CMI(yyyymmddhhmn, band, input)
# Read file
var = 'CMI' # variable
k = - 273.15 # convert Kelvin to Celsius
dtime, img, undef, ds = Utilities.get_ds(input, file_name, var, k)

# Reprojection of BTD image and write to a NC file
file_name = f"{output}/{file_name}"
Utilities.proj_ret(img, undef, ds, extent, file_name)

# Define properties to plot map
properties = {
    'colormap': 'gray_r',
    'label': 'Brightness temperature (°C)',
    'band': band,
    'vmin': None,
    'vmax': None
}
Utilities.plot_map(dtime, file_name, extent, properties)
