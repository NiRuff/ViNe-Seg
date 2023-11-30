import os
import numpy as np
from PIL import Image
import json
import sys
#sys.path.insert(1, 'C:/Users/Saleh Altahini/Miniconda3/envs/vineseg/Lib/site-packages/vineseg/utils')
#from shapeutil import shape_to_mask
from ..utils import shape_to_mask




def image2array(image_path):
    im = Image.open(image_path)
    imarray = np.array(im)
    return imarray

def tracesForImage(imagePath, masks):
    trace = np.zeros(len(masks))
    im = image2array(imagePath)
    for x in range(0, len(masks)):
        roimask = np.invert(masks[x])
        a = np.ma.array(im, mask=roimask)
        trace[x] = a.mean()

    return trace




from multiprocessing import Pool, freeze_support
from itertools import repeat

if __name__ == '__main__':
    freeze_support()
    """
    path = "C:/Users/Saleh Altahini/Documents/Vineseg Test Data/MC_191023_TL1_15-59-11"
    images_type = "tif"
    imagesArray = [os.path.join(path, f) for f in os.listdir(path) if
                       os.path.isfile(os.path.join(path, f)) and f.endswith("." + images_type)]
    filename="C:/Users/Saleh Altahini/Documents/Vineseg Test Data/predictions/AVG_MC.json"
    with open(filename) as f:
        data = json.load(f)

    masks = []

    for i in range(0, len(data['shapes'])):
        roimask = shape_to_mask((data['imageHeight'], data['imageWidth']), data['shapes'][i]['points'], shape_type=None,
                                line_width=1, point_size=1)
        masks.append(roimask)

    with Pool() as pool:
        M = pool.starmap(tracesForImage, zip(imagesArray, repeat(masks)))
    """

