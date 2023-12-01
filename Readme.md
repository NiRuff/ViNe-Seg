# Visible Neuron Segmentation: ViNe-Seg (beta version)

<img align="right" width="420" height="420" src=https://user-images.githubusercontent.com/50486014/173547029-a4a1bfac-379f-42ef-aaec-166d814ea421.png width="30%" height="30%" /> <br>


### Embedding Deep-Learning assisted segmentation of Visible Neurons and subsequent Analysis in one Graphical User Interface
**ViNe-Seg** comes in two versions, that include:


| |ViNe-Seg|<nobr> ViNe-Seg :heavy_plus_sign: </nobr>|
|:----|:------:|:------:|
|Autosegmentation Model Manager| :heavy_check_mark: | :heavy_check_mark: |
|ViNe-Seg Autosegmentation step| :heavy_check_mark: | :heavy_check_mark: |
|Manual refinement of segmentation results| :heavy_check_mark: | :heavy_check_mark: |
|Trace Extraction| :heavy_check_mark: | :heavy_check_mark: |
|ΔF/F conversion| :heavy_check_mark: | :heavy_check_mark: |
|Microscope Mode| :heavy_check_mark: | :heavy_check_mark: |
|Free| :heavy_check_mark: | :heavy_check_mark: |
|Open-Source| :heavy_check_mark: | :heavy_check_mark: |
|CASCADE SPIKE Inference| :x: | :heavy_check_mark: |


## Installation of the basic version of ViNe-Seg
We aimed to develop ViNe-Seg as user-friendly as possible. Therefor, ViNe-Seg comes with a GUI and is easily installable using pip with the command:

### General recommendation: Create a new conda environment
```
conda create -n vineseg_env python=3.9
conda activate vineseg_env
```
## Then run:
### Windows recommendation:
```
pip install PyQt5
pip install vineseg
```

### Mac recommendation:
```
conda install pyqt
pip install vineseg
```

### Ubuntu recommendation:
```
conda install pyqt
pip install vineseg
pip uninstall opencv-python
pip install opencv-python-headless 
```

ViNe-Seg will be downloaded and installed with all necessary dependencies.

### Installation of the advanced version of ViNe-Seg, including the CASCADE SPIKE inference

If you also want to use the CASCADE SPIKE Inference (see https://github.com/HelmchenLabSoftware/Cascade) you might want to install the advanced version of ViNe-Seg instead. To do so, install conda or anaconda on your machine and run the following commands in the given order, to create a conda environment and install ViNe-Seg there:

```
conda create -n vineseg-adv python=3.7 tensorflow==2.3 keras==2.3.1 h5py numpy scipy matplotlib seaborn ruamel.yaml
conda activate vineseg-adv
pip install vineseg
```


<!---![showcase gif](https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg_Installation.gif)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg_Installation.gif"  width="85%"></p>

From now on, the advanced version of ViNe-Seg will be installed in your conda environment called *vineseg-adv*.

## Starting ViNe-Seg
You can start ViNe-Seg using the following command after installation (make sure not to work in an environment in which ViNe-Seg is not installed):
```
python -m vineseg
```

If you have to start the specific environment first, run:

```
conda activate vineseg-adv
python -m vineseg
```

Now, ViNe-Seg will check if you already have a version of the trained models installed and will download the default model version if none is currently in use on your machine.

After this step, the GUI will automatically be opened where you have the chance to download other models, choose between them, load your mean image in PNG or TIFF format and to run the autosegmentation using the ```Autosegmentation``` command shown in the menu bar in the top of the screen.
We embedded the ViNe-Seg functionality in the labelme GUI (see https://github.com/wkentaro/labelme) by adding a button for running the autosegmentation step of ViNe-Seg in the GUI, as well as a model manager, trace extraction, baseline correction, the CASCADE SPIKE Inference. We also added some other underlying funtionalities such as automatic loading of the generated JSON labeling files and the option to load them from old ViNe-Seg runs using the new ```Load Polygon``` button or the possibility to manipulate the resulting segmentation output either by controlling the minimum ocnfidence from which one you want to see the segmentation results or by manually editing, adding or deleting shapes. You can further switch between enumerated Neuron labels (Neuron1, ..., NeuronX) and area-based Neuron labels (Neuron too small, ... , Neuron too big) by clicking a button or remove all neurons bigger/smaller than you previously defined within the GUI. 

## What ViNe-Seg can be used for:

Here you can see some example videos of ViNe-Seg applied to the neurofinder dataset (https://github.com/codeneuro/neurofinder).

### The Autosegmentation:

<!---![showcase gif](https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg_Autosegmentation.gif)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg_Autosegmentation.gif "  width="85%"></p>

### Refining the Autosegmentation:
<!---![showcase gif](https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg_Refine.gif)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg_Refine.gif "  width="85%"></p>

### The Trace Extraction and CASCADE SPIKE Inference:
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/VineSeg2_.gif" width="85%"  />


### The Microscope Mode:
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg_Microscope.gif" width="85%"  />

## Train a custom vine-seg model

### Data Preparation

In this section, we'll walk you through the steps to prepare your dataset for training. This involves creating projections of your data, annotating images, and setting up the folder structure.

#### Create Mean/Max Projection of Your Data

Before you start annotating, you should create mean or max projections of your data. This will help in better visualization and annotation. You can use image processing libraries like OpenCV or ImageJ to accomplish this.

#### Annotate with LabelImg

1. Download and install [LabelImg](https://github.com/HumanSignal/labelImg).
2. Open LabelImg and load your mean/max projected images.
3. Annotate the objects in the images and save the annotations in the COCO format.

#### Create Data Folder

Create a folder for your dataset in the `data/` directory. For example, create a folder named `example`:

```bash
mkdir data/example
```

#### Create Required Folder Structure

Use the function `create_yolo_folder_struct`  (located in utils.py) to set up the required folder structure:

```python
create_yolo_folder_struct("data/example")
```

Your folder should now have the following structure:

```
data/example  
├── coco  
├── raw  
└── yolo  
```

#### Prepare Training Data

Use the `coco_seg_to_yolov8` function to prepare your training data:

```python
coco_seg_to_yolov8(
    coco_path="data/example/coco",
    yolo_path="data/example/yolo",
    splits=[0.7, 0.2, 0.1]
)
```

Here, `splits` is a list of three floats that add up to 1. The first number is the share of images used for training, the second for validation, and the third for testing.

#### Create `data.yaml`

Finally, create a `data.yaml` file inside the `data/example/yolo` folder with the following structure:

```yaml
path: /path/to/vineseg/data/example
train: yolo/train/images
val: yolo/val/images
test: yolo/test/images
nc: 1
names: ['cell']
```

This YAML file will be used during the training process to locate your dataset and set other configurations.

### Training

In this section, we'll guide you through the process of training your custom model. This involves setting up your training environment and running the training script.

#### Hardware Requirements

It's recommended to use a PC with a sufficient GPU for training. Ensure that your GPU has a vRAM of at least 8GB for optimal performance.

#### Open Jupyter Notebook

Open the Jupyter notebook named `train.ipynb` where the training code is located.

#### Choose a Model

You have two options for starting your training:

1. **Pre-trained Model**: Use a pre-trained model from Ultralytics that hasn't been trained on neurons yet. You can find a list of available models [here](https://docs.ultralytics.com/tasks/detect/#models). To load a small model, for example, use:
   
   ```python
   model = YOLO('yolov8s-seg.pt')
   ```

2. **Downloaded Model**: Use one of the downloaded models that you can access through the ViNeSeg GUI. To specify the path to one of these models, use:
   
   ```python
   model = YOLO('/path/to/vineseg/models/model.pt')
   ```

#### Start Training

To start the training process, use the `train` method:

```python
model.train(
    data='/path/to/vineseg/data/example/data.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    show_labels=True
)
```

Here, you can adjust the `epochs`, `imgsz`, `batch`, and `show_labels` parameters according to your needs.

#### Parameters for `model.train()`

- **`data: str`**: This is the path to the `data.yaml` file that contains metadata about your dataset. It specifies where your training, validation, and test data are located.
  
  Example: `data='/path/to/vineseg/data/example/data.yaml'`

- **`epochs: int = 100`**: The number of training epochs. An epoch is one complete forward and backward pass of all the training examples. The default value is 100.
  
  Example: `epochs=100`

- **`imgsz: int = 640`**: The size of the images for training. The images will be resized to this dimension (width x height). The default value is 640.
  
  Example: `imgsz=640`

- **`batch: int = 16`**: The batch size for training. This is the number of training examples utilized in one iteration. The default value is 16.
  
  Example: `batch=16`

- **`show_labels: bool = True`**: Whether or not to display the labels during training. This is useful for visualizing the training process. The default value is True.
  
  Example: `show_labels=True`

#### Locate Trained Model and Weights

After the training is complete, you can find the trained model in the following directory:

```
/path/to/vineseg/runs/train
```

The weights for the trained model will be stored in:

```
/path/to/vineseg/runs/train/weights
```

#### Make Weights Accessible in ViNeSeg

To use the trained model in ViNeSeg, you need to copy the weights from the `runs/weights` folder to the ViNeSeg model folder.

### Evaluate

After training your custom model, it's crucial to evaluate its performance to ensure it meets your project's requirements. This section will guide you through the evaluation process.

#### Validation Set

To get performance numbers for the validation set, run:

```python
model.val()
```

#### Test Set

To evaluate the model on the test set, specify the `mode` parameter as 'test':

```python
model.val(mode='test')
```

### Share Your Custom Model

We are excited to host your custom model to make it accessible to other researchers. 
