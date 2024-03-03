import os
import numpy as np
from PIL import Image
import json
import sys
from ..utils import shape_to_mask
import tifffile as tfile

# Function to convert an image to a numpy array
def image2array(image_path):
    im = Image.open(image_path)
    imarray = np.array(im)
    return imarray

# Function to calculate traces for an image using masks
def tracesForImage(imagePath, masks):
    trace = np.zeros(len(masks))
    im = image2array(imagePath)
    for x in range(0, len(masks)):
        roimask = np.invert(masks[x])
        a = np.ma.array(im, mask=roimask)
        trace[x] = a.mean()

    return trace

def tracesForSlice(stackPath, slice, masks):
    trace = np.zeros(len(masks))
    im = tfile.imread(stackPath, key=slice)
    for x in range(0, len(masks)):
        roimask = np.invert(masks[x])
        a = np.ma.array(im, mask=roimask)
        trace[x] = a.mean()

    return trace

from multiprocessing import Pool, freeze_support
from itertools import repeat

if __name__ == '__main__':
    freeze_support()
    

