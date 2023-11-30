from ultralytics import YOLO


class ViNeSeg:
    def __init__(
        self,
        weights_path: str,
    ):
        self.model = YOLO(weights_path)

    # https://docs.ultralytics.com/modes/train/
    def train(
        self,
        data: str,
        epochs: int = 100,
        imgsz: int = 640,
        batch: int = 16,
        show_labels: bool = True,
    ):
        self.model.train(
            data=data,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            show_labels=show_labels,
        )

    # https://docs.ultralytics.com/modes/predict/
    def predict(
        self,
        source: str,
        conf: float = 0.25,
        save: bool = False,
        show: bool = False,
        show_labels: bool = False,
        show_conf: bool = False,
    ):
        result = self.model.predict(
            source=source,
            conf=conf,
            save=save,
            show=show,
            show_labels=show_labels,
            show_conf=show_conf,
        )
        return result
