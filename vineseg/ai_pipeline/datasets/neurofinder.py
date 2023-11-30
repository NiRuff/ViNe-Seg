import json
import os

import cv2
import numpy as np
from shapely.geometry import Polygon
from skimage import measure


def scale_pixel_values(image_array):
    min_val = np.min(image_array)
    max_val = np.max(image_array)
    # Normalize the pixel values to the range [0, 1]
    normalized_array = (image_array - min_val) / (max_val - min_val)
    # Scale the normalized pixel values to the range [0, 255]
    scaled_array = (normalized_array * 255).astype(np.uint8)
    return scaled_array


def tiff_to_png(input_path: str, output_path: str):
    for folder in os.listdir(input_path):
        if not folder.startswith("neurofinder."):
            continue
        img = []
        img_folder_path = os.path.join(input_path, folder, "images")
        for file in os.listdir(img_folder_path):
            if not file.endswith(".tiff"):
                continue
            img_path = os.path.join(img_folder_path, file)
            img.append(cv2.imread(img_path))

        # combine array to one png
        img = np.array(img)
        img = np.mean(img, axis=3)
        img = np.max(img, axis=0)
        scaled_img = scale_pixel_values(img)

        # write png to disk
        img_out_path = os.path.join(output_path, f"{folder}.png")
        cv2.imwrite(img_out_path, scaled_img)


def generate_mask(shape, mask_coords):
    mask = np.zeros(shape)
    for x, y in mask_coords:
        mask[x, y] = 1
    return mask


def extract_coordinates_from_mask(mask: np.ndarray) -> list:
    # Assume that `roi_matrix` is the binary matrix representing the ROI
    # Find the contours of the binary matrix
    contours = measure.find_contours(mask, 0.5)
    # Assume that there is only one contour for the ROI
    roi_contour = contours[0]
    # Get the x and y coordinates of the contour
    x_coords = roi_contour[:, 1]
    y_coords = roi_contour[:, 0]

    # Create a list of (x, y) tuples for the polygon vertices
    polygon_vertices = [(x, y) for x, y in zip(x_coords, y_coords)]
    # Create a Shapely Polygon from the vertices
    polygon = Polygon(polygon_vertices)

    # Simplify the polygon using the Ramer-Douglas-Peucker algorithm
    tolerance = 0.0
    simplified_polygon = polygon.simplify(tolerance)
    area = simplified_polygon.area
    # Get the coordinates of the simplified polygon
    simplified_polygon_coords = list(simplified_polygon.exterior.coords)

    return simplified_polygon_coords, area


def generate_coco_dict(input_path: str, output_path: str, img_shape: tuple):
    coco_dict = {
        "info": {
            "description": "Neurofinder - Max Projection + Masks",
            "url": "https:/neurofinder.codeneuro.org/",
            "version": "1.0",
            "year": 2023,
            "contributor": "Neurofinder",
            "date_created": "2023-03-24",
        },
        "images": [],
        "annotations": [],
        "categories": [{"id": 1, "name": "cell", "supercategory": "soma"}],
    }

    anno_id = 100_000

    for folder in os.listdir(input_path):
        if not folder.startswith("neurofinder."):
            continue

        coco_image_entry = {
            "id": folder,
            "width": 512,
            "height": 512,
            "file_name": f"{folder}.png",
        }

        # read annotations
        json_path = os.path.join(input_path, folder, "regions/regions.json")
        with open(json_path, "r") as j:
            regions = json.load(j)

        annos = []
        for region in regions:
            soma, area = extract_coordinates_from_mask(generate_mask(img_shape, region["coordinates"]))
            coco_coord = []
            tmp_x = []
            tmp_y = []
            for x, y in soma:
                coco_coord.append(x)
                coco_coord.append(y)
                tmp_x.append(x)
                tmp_y.append(y)
            # Find the minimum and maximum x coordinates
            min_x, max_x = min(tmp_x), max(tmp_x)
            # Find the minimum and maximum y coordinates
            min_y, max_y = min(tmp_y), max(tmp_y)
            # Construct the bounding box (x, y, width, height)
            bounding_box = [min_x, min_y, max_x - min_x, max_y - min_y]
            anno_entry = {
                "id": anno_id,
                "image_id": folder,
                "category_id": 1,
                "segmentation": [list(coco_coord)],
                "area": area,
                "bbox": bounding_box,
                "iscrowded": 0,
            }
            annos.append(anno_entry)
            anno_id += 1
        coco_dict["images"].append(coco_image_entry)
        coco_dict["annotations"] += annos
    with open(os.path.join(output_path, "neurofinder_coco.json"), "w") as j:
        json.dump(coco_dict, j)
