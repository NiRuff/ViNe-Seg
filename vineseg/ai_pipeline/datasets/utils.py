import json
import os
from shutil import copyfile

import numpy as np


def transform_segmentations(segmentations, width, height):
    res = []
    # label to prepend
    # TODO: make this dynamic for cleaner code
    label = 0

    for segmentation in segmentations:
        res.append([label] + [val / width if idx % 2 == 0 else val / height for idx, val in enumerate(segmentation)])

    return res


def split_indices(length, splits):
    splits_adjusted = [int(length * split) for split in splits]

    # Generate a list of random integers between 0 and the length of the list (exclusive)
    indices = np.arange(length)

    # Shuffle the indices to distribute them randomly
    np.random.shuffle(indices)

    # Calculate the starting and ending indices for each split
    split_points = np.cumsum(splits_adjusted)[:-1]
    split_lists = np.split(indices, split_points)

    return split_lists


def coco_seg_to_yolov8(coco_path, output_path, splits):
    assert (
        len(splits) == 3
    ), "Please provide three values for splits. If you don't need a validation or test set, just provide 0 as a value. Example: [1, 0, 0]"

    coco_dict_name = [file for file in os.listdir(coco_path) if ".json" in file][0]
    full_file_path = os.path.join(coco_path, coco_dict_name)

    with open(full_file_path, "r") as file:
        coco_dict = json.load(file)

    num_images = len(coco_dict["images"])

    train, val, test = split_indices(num_images, splits)

    # loop over images
    for idx, image in enumerate(coco_dict["images"]):
        id, width, height, file_name = image["id"], image["width"], image["height"], image["file_name"]
        # get annotations
        annotations = filter(lambda x: x["image_id"] == id, coco_dict["annotations"])
        # check why this is an array  of arrays
        # extract segmentation from annotation
        segmentations = [annotation["segmentation"][0] for annotation in annotations]

        # transform from pixel to percent
        segmentations_percent = transform_segmentations(segmentations, width, height)

        # get path for file depending on split
        slug = "train" if idx in train else "val" if idx in val else "test"
        final_path = os.path.join(output_path, slug)

        # write to disk
        file_path_label = os.path.join(final_path, "labels", f"{id}.txt")
        with open(file_path_label, "w") as file:
            for segmentation in segmentations_percent:
                file.write(" ".join([str(val) for val in segmentation]))
                file.write("\n")

        # copy image over to yolo folder
        file_path_image_src = os.path.join(coco_path, file_name)
        file_path_image_dest = os.path.join(final_path, "images", file_name)
        copyfile(file_path_image_src, file_path_image_dest)
