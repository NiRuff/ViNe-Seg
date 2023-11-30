import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Polygon

from .vine_seg import ViNeSeg


def predict(image_path, model_path, conf_threshold=0.1, plot_first=True):
    model = ViNeSeg(model_path)
    result = model.predict(image_path, conf=conf_threshold)
    if plot_first:
        first_result = result[0]
        plt.imshow(first_result.plot())

    return result


def parse_mask_to_vineseg(mask):
    # assuming only a single image has been predicted
    mask = np.array(mask.xy).squeeze()

    # Get the x and y coordinates of the contour
    x_coords, y_coords = mask[:, 0], mask[:, 1]
    # Create a list of (x, y) tuples for the polygon vertices
    polygon_vertices = [coord for coord in zip(x_coords, y_coords)]
    # Create a Shapely Polygon from the vertices
    polygon = Polygon(polygon_vertices)
    # Simplify the polygon using the Ramer-Douglas-Peucker algorithm
    simplified_polygon = polygon.simplify(tolerance=0.0)
    simplified_polygon_coords = list(simplified_polygon.exterior.coords)
    simplified_polygon_area = simplified_polygon.area

    return simplified_polygon_coords, simplified_polygon_area


def get_vineseg_list(predictions, min_size=1, max_size=1000, conf_threshold=0.1):
    result = []
    # in case there are multiple predictions at the same time
    for pred in predictions:
        scores = pred.boxes.conf
        path = pred.path
        try:
            for idx, mask in enumerate(pred.masks):
                coords, area = parse_mask_to_vineseg(mask)
                score = scores[idx]
                points = np.array(mask.xy).squeeze().tolist()
                label = "Neuron_too_small" if area < min_size else "Neuron_too_big" if area > max_size else "Neuron"
                result.append(
                    {
                        "shape_type": 'polygon',
                        "points": points,
                        "score": score.item(),
                        "label": label,
                    }
                )
        except TypeError:
            print("No ROIs found. Try another model or adapt the minimum/maximum size for expected neurons.")
    return result
