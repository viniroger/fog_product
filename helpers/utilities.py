#!/usr/bin/env python3.9.5
# -*- Coding: UTF-8 -*-

import os                                  # Operating system interfaces
from datetime import datetime              # Basic Dates and time types
import boto3                               # AWS SDK for Python
from botocore import UNSIGNED              # boto3 config
from botocore.config import Config         # boto3 config
from osgeo import osr                      # Python bindings for GDAL
from osgeo import gdal                     # Python bindings for GDAL
from netCDF4 import Dataset                # Read / Write NetCDF4 files
import numpy as np                         # Scientific computing with Python
import pandas as pd                        # Read and manipulate CSV file
import matplotlib.pyplot as plt            # Plotting library
import cartopy, cartopy.crs as ccrs        # Plot maps
import cartopy.io.shapereader as shpreader # Import shapefiles

class Utilities():

    @staticmethod
    def download_CMI(yyyymmddhhmn, band, path_dest):
        '''
        Download CMI/GOES-16 files from AWS
        '''
        # Check/create directory
        os.makedirs(path_dest, exist_ok=True)
        # Get datetime info
        year = datetime.strptime(yyyymmddhhmn, '%Y%m%d%H%M').strftime('%Y')
        day_of_year = datetime.strptime(yyyymmddhhmn, '%Y%m%d%H%M').strftime('%j')
        hour = datetime.strptime(yyyymmddhhmn, '%Y%m%d%H%M').strftime('%H')
        min = datetime.strptime(yyyymmddhhmn, '%Y%m%d%H%M').strftime('%M')

        # AMAZON repository information
        # https://noaa-goes16.s3.amazonaws.com/index.html
        bucket_name = 'noaa-goes16'
        product_name = 'ABI-L2-CMIPF'
        # Initializes the S3 client
        s3_client = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        # File structure
        prefix = (
            f'{product_name}/{year}/{day_of_year}/{hour}/OR_{product_name}'
            f'-M6C{int(band):02.0f}_G16_s{year}{day_of_year}{hour}{min}'
        )
        # Seach for the file on the server
        s3_result = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix,
         Delimiter = '/')

        # Check if there are files available
        if 'Contents' not in s3_result:
            # There are no files
            print(f'No files found for the date: {yyyymmddhhmn}, Band-{band}')
            return -1
        else:
            # There are files
            for obj in s3_result['Contents']:
                key = obj['Key']
                # Print the file name
                file_name = key.split('/')[-1].split('.')[0]

                # Download the file
                path_file = f'{path_dest}/{file_name}.nc'
                if os.path.exists(path_file):
                    print(f'File {path_file} exists')
                else:
                    print(f'Downloading file {path_file}')
                    s3_client.download_file(bucket_name, key, path_file)
        return f'{file_name}'

    @staticmethod
    def get_ds(input, file_name, var, k):
        '''
        Read NC file and get/apply scale and offset
        '''
        # Open the file
        img = gdal.Open(f'NETCDF:{input}/{file_name}.nc:' + var)
        # Read the header metadata
        metadata = img.GetMetadata()
        scale = float(metadata.get(var + '#scale_factor'))
        offset = float(metadata.get(var + '#add_offset'))
        undef = float(metadata.get(var + '#_FillValue'))
        dtime = metadata.get('NC_GLOBAL#time_coverage_start')
        # Load the data
        ds = img.ReadAsArray(0, 0, img.RasterXSize, img.RasterYSize).astype(float)
        # Apply the scale and offset
        ds = (ds * scale + offset) + k
        return dtime, img, undef, ds

    @staticmethod
    def proj_ret(img, undef, ds, extent, file_name):
        '''
        Reproject ds/netCDF image to retangular projection limited by extent
        '''
        # Read the original file projection and configure the output projection
        source_prj = osr.SpatialReference()
        source_prj.ImportFromProj4(img.GetProjectionRef())
        target_prj = osr.SpatialReference()
        target_prj.ImportFromProj4("+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs")
        # Reproject the data
        GeoT = img.GetGeoTransform()
        driver = gdal.GetDriverByName('MEM')
        raw = driver.Create('raw', ds.shape[0], ds.shape[1], 1, gdal.GDT_Float32)
        raw.SetGeoTransform(GeoT)
        raw.GetRasterBand(1).WriteArray(ds)
        # Define the parameters of the output file
        options = gdal.WarpOptions(format = 'netCDF',
                  srcSRS = source_prj,
                  dstSRS = target_prj,
                  outputBounds = (extent[0], extent[3], extent[2], extent[1]),
                  outputBoundsSRS = target_prj,
                  outputType = gdal.GDT_Float32,
                  srcNodata = undef,
                  dstNodata = 'nan',
                  xRes = 0.02,
                  yRes = 0.02,
                  resampleAlg = gdal.GRA_NearestNeighbour)
        # Write the reprojected file on disk
        gdal.Warp(f'{file_name}_ret.nc', raw, options=options)

    @staticmethod
    def plot_map(dtime, file_name, extent, properties):

        # Open the reprojected GOES-R image
        file = Dataset(f'{file_name}_ret.nc')
        # Get the pixel values
        data = file.variables['Band1'][:]

        # Choose the plot size (width x height, in inches)
        plt.figure(figsize=(10,10))
        # Use the Geostationary projection in cartopy
        ax = plt.axes(projection=ccrs.PlateCarree())
        # Define the image extent
        img_extent = [extent[0], extent[2], extent[1], extent[3]]
        # Plot the image
        img = ax.imshow(data, origin='upper', extent=img_extent,\
         vmin=properties['vmin'], vmax=properties['vmax'],\
         cmap=properties['colormap'])

        # Add a shapefile
        shapefile = list(shpreader.Reader('helpers/BR_UF_2019.shp').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='white',\
         facecolor='none', linewidth=0.3)

        # Add coastlines, borders and gridlines
        ax.coastlines(resolution='10m', color='white', linewidth=0.8)
        ax.add_feature(cartopy.feature.BORDERS, edgecolor='white', linewidth=0.5)
        gl = ax.gridlines(crs=ccrs.PlateCarree(), color='gray', alpha=1.0,\
         linestyle='--', linewidth=0.25, xlocs=np.arange(-180, 180, 5),\
          ylocs=np.arange(-90, 90, 5), draw_labels=True)
        gl.top_labels = False
        gl.right_labels = False

        # Plot some places
        file_places = 'helpers/places.csv'
        df = pd.read_csv(file_places)
        for index, row in df.iterrows():
            plt.text(row['lon'],row['lat'],row['id'], color='blue')

        # Add a colorbar
        plt.colorbar(img, label=properties['label'], \
         orientation='horizontal', pad=0.05, fraction=0.05)
        # Extract date
        date = (datetime.strptime(dtime, '%Y-%m-%dT%H:%M:%S.%fZ'))
        # Add a title
        plt.title('GOES-16 ' + properties['band'] + ' ' + date.strftime('%Y-%m-%d %H:%M') +\
         ' UTC', fontweight='bold', fontsize=10, loc='left')
        plt.title('Reg.: ' + str(extent) , fontsize=10, loc='right')

        # Save the image
        plt.savefig(f'{file_name}.png', bbox_inches='tight', pad_inches=0,\
         dpi=300)
        # Show the image
        #plt.show()
