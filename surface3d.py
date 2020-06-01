'''
======================
3D surface (color map)
======================

Demonstrates plotting a 3D surface colored with the coolwarm color map.
The surface is made opaque by using antialiased=False.

Also demonstrates using the LinearLocator and custom formatting for the
z axis tick labels.
'''
import sys
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
import re
import numpy as np
import csv
from numpy import float64

dim = "3D"

filename = sys.argv[1]

if (__name__ == "__main__"):
    dtypes = np.dtype({'names':('X', 'Y', 'Z'),
                       'formats': (np.float64, np.float64, np.float64)})
    data = np.loadtxt(filename, comments='#', delimiter=',', usecols=(0,1,2), dtype = dtypes)
    # converters={float64}, dtype, unpack, ndmin, encoding, max_rows)
    x = data['X']
    y = data['Y']
    z = data['Z']

    fig = plt.figure()
    if(dim == "2D"):
        ax = fig.add_subplot(111)
        surf = ax.scatter(x,y,s=1,c=z, marker = 'o', cmap = cm.jet );
    elif (dim == "3D"):
        ax = fig.add_subplot(111, projection='3d')
        surf = ax.scatter(x,y,z,s=1,c=z, marker = 'o', cmap = cm.jet );
        ax.zaxis.set_major_locator(LinearLocator(10))
        ax.zaxis.set_major_formatter(FormatStrFormatter('%.02f'))

    # Add a color bar which maps values to colors.
    fig.colorbar(surf, shrink=0.5, aspect=5)
    plt.show()

    # scatterPlot("3D")
