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


## Vine-Seg Custom Model Training

In this section, we'll guide you through the process of training your custom model. This involves setting up your training environment and running the training script.

## Installation

1. Clone the git
   
   ```bash
   git clone https://github.com/s-weissbach/vine-seg_segmentation.git
   ```

2. Create a conda enviorment
   
   ```bash
   conda create -n vineseg_segmentation python=3.9 pip
   conda activate -n vineseg_segmentation
   ```

3. Install the dependencies

   ```bash
   # install dependencies from requirements.txt
   pip install -r requirements.txt
   
   ```

## Data preperation

> [!IMPORTANT] 
> The data preparation notebook is specifically designed to handle the output files generated by Vine-Seg.

To prepare your dataset for training with VineSeg, follow these steps using the provided Jupyter notebook (`data_preperation.ipynb`): 

1. Create Dataset Folder Create a folder within the `data` directory and name it after your dataset. 

2. Create required subfolders (`coco`, `raw`, and `yolo`) in your dataset folder 
   
   
   

3. Copy your images along with the VineSeg generated annotation files in the `raw` folder.
   
   ```bash
   # the resulting folder structure should look like this
   
   data
   ├── coco
   ├── raw
   │   ├── image1.png
   │   ├── image1.json
   │   ├── (...)
   │   └── imageN.json
   └── yolo
   ```

4. In the Jupyter notebook, set the necessary COCO variables:
   
   ```python
   dataset = "example"
   description = "this is a toy example dataset"
   url = "in-house data"
   version = "0.1"
   year = 2024
   contributor = "somebody"
   date_created = "01-01-2024"
   annotation_id_start = 0
   image_fileendings = [".png"]
   ```

5. Run `generate_coco_dict` Function
   
   - You can generate several coco json files and combine into one YOLO data set for training
   
   ```python
   input_folder = f"data/{dataset}/raw"
   coco_output_path = f"data/{dataset}/coco" 
   
   generate_coco_dict(input_path,
                      output_path,
                      description,
                      url,
                      version,
                      year,
                      contributor,
                      date_created,
                      annotation_id_start,
                      image_fileendings,)
   
   ```

6. Use the `coco_seg_to_yolov8` function to convert the generated COCO JSON file(s) to YOLO format.
   
   - adapt the split (train, validation, test) to your need
   
   ```python
   coco_seg_to_yolov8("data/<dataset>/coco", "data/<dataset>/yolo", splits=[0.8, 0.05, 0.15])
   ```

## Training

> [!WARNING]
> We highly recommend to only train on a capable GPU. Training will be very slow and ineffective otherwise.

To train your custom VineSeg model, follow these steps using the provided Jupyter notebook (`training.ipynb`):

1. Chose a model for your training:
   
   - A fresh model, not trained on any calcium imaging data
     
     - ```python
       # model size s
       model = YOLO('yolov8s-seg.pt')
       ```
     
     - Note, there are YOLO models in different sizes. The larger the model, the more computational resources and training data is required. You can load these by sustituting the `s` after the 8 bei (`xs`, `m`, `l`, or `xl`). Refer to [YOLO](https://github.com/ultralytics/ultralytics/tree/main) for more information.
   
   - A pre-trained model from Vine-Seg, all stored in the folder `models`. 
     
     - 
       
       ```python
       # pre-trained model on AllenBrain data
       model = YOLO('models/vine_seg-allen.pt')
       ```

2. Train the model
   ```python
   # pre-trained model on AllenBrain data
   model.train(data='data/<dataset>/yolo/data.yaml', epochs=50, imgsz=640, batch=4)
   ```
   - `data`:  The path to the `<dataset>` within the `YOLO` folder.
   - `epochs`: Defines the number of complete passes through the entire training dataset during the training process. In this case, the model will undergo 50 epochs.
   - `imgsz`: Sets the input image size for the training. The images will be resized to a square shape with dimensions `imgsz x imgsz` pixels. Here, the value is set to 640, indicating an image size of 640x640 pixels.
   - `batch`: Specifies the batch size, which is the number of training samples utilized in one iteration. In this case, the batch size is set to 4. Adjusting the batch size can impact training speed and memory requirements.

                

        
