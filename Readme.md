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
```
pip install vineseg
```

ViNe-Seg will be downloaded and installed with all necessary dependencies.

### Installation of the advanced version of ViNe-Seg, including the CASCADE SPIKE inference

If you also want to use the CASCADE SPIKE Inference (see https://github.com/HelmchenLabSoftware/Cascade) you might want to install the advanced version of ViNe-Seg instead. To do so, install conda or anaconda on your machine and run the following commands in the given order, to create a conda environment and install ViNe-Seg there:

```
conda create -n vineseg-adv python=3.7 tensorflow==2.3 keras==2.3.1 h5py numpy scipy matplotlib seaborn ruamel.yaml
conda activate vineseg-adv
pip install vineseg
```

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

Now, ViNe-Seg will check if you already have a version of the trained MONAI models installed and will download the default model version if none is currently in use on your machine.

After this step, the GUI will automatically be opened where you have the chance to download other models, choose between them, load your mean image in PNG or TIFF format and to run the autosegmentation using the ```Autosegmentation``` command shown in the menu bar in the top of the screen.
We embedded the ViNe-Seg functionality in the labelme GUI (see https://github.com/wkentaro/labelme) by adding a button for running the autosegmentation step of ViNe-Seg in the GUI, as well as a model manager, trace extraction, baseline correction, the CASCADE SPIKE Inference. We also added some other underlying funtionalities such as automatic loading of the generated JSON labeling files and the option to load them from old ViNe-Seg runs using the new ```Load Polygon``` button or the possibility to manipulate the resulting JSON file by switching between enumerated Neuron labels (Neuron1, ..., NeuronX) and area-based Neuron labels (Neuron too small, ... , Neuron too big) by clicking a button. The area size from which the labels are derived can also be changed within the GUI. 

## What ViNe-Seg can be used for:

Here you can see some example videos of ViNe-Seg applied to the neurofinder dataset (https://github.com/codeneuro/neurofinder).

### The Autosegmentation:

<!---![showcase gif](https://github.com/NiRuff/GithubMedia/blob/main/VineSeg_Seg_1(1).gif)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/VineSeg_Seg_1(2).gif "  width="85%"></p>

### Refining the Autosegmentation:
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/VineSeg_Seg_2.gif" width="85%"  />

### The Trace Extraction and CASCADE SPIKE Inference:
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/VineSeg2_.gif" width="85%"  />


### The Microscope Mode:
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/ViNeSeg-3.gif" width="85%"  />

## Training your own model

Vineseg offers the possibility to integrate your own Monai model or to finetune an already existing model on your own data. The settings for the training can be specified via a config file.
The training can be started in the subfolder with python training.py --path_config_file="path to your config file".
The config file has the following options:

* path loading model: An already trained model can be used as starting point for further training. Specify here the folder where the model is located.
* paths training image folder: List of folders with the training images
* paths training masks folder: List of folders with the training masks
* paths val image folder: List of folders with the validation images
* paths val masks folder: List of folders with the validation masks 
* valiation intervall: Distance in epochs between evaluation time points during training on the validation dataset
* ROI training: Image size for training. Typically the ROI training is smaller than the original image size to get more training images.
  ROI training is only used if "SpatialCrop" is part of augementation steps.
* ROI validation: Image size for validation
* augmentation probability: probability that a augmentation steps is applied on the training images.
* preprocessing steps: List of preprocessing steps. The only option at the moment is "ScaleIntensity"
* augmentation steps: List of augmentation steps. Valid options are "SpatialCrop", "GaussianNoise"
  , "Rotate", "Flip", "Zoom", "ElasticDeformation" or "AffineTransformation" 
* postprocessing: Dictionary with key "Activation" for the activation function. Options are "Sigmoid" or "Softmax" as values.
  The other key "Threshold" specifies when the prediciton output is converted to 1.
* model type: The type of the neural network. Valid options are "U-Net big", "SegResNet" or "UNetTransformer"
* number input channel: Define how many different preprocessed duplications of one images are loaded into the network.
* channel types input: List of feature engineering techniques which should be applied. The length of the list must be equal to number input channel.
  Valid options are "identity", "clahe", "nl_means", "autolevel", "gamma low", "gamma high", "rolling ball" or "adjust sigmoid".
* number output channel: Number of output images from the neural network.
* channel types input: Further preprocessing steps, which are applied on the output from the neural network. The only valid option at the moment is ["identity"]
* optimizer: "Adam" or "AdamW"
* loss function: "Dice loss", "Focal loss", "Tversky loss", "Dice focal loss" or "Dice CE loss".
* metrics: List with metrics for evaluation. "Dice Metric" as only option at the moment.
* epochs: number of epochs
* batch size: number of training images per batch.
* learning rate: Initial learning rate. Will be decreased with factor (1 - current_epoch / max_epoch) ** 0.9 per epoch 
* weight decay: Will be applied in case optimizer "AdamW"
* path save model: folder for storing the trained neural network weights and the config file
* logging training results: Not used at the moment


## Automatic Preprocessing of images in the default model
The quality and image properties between the Calcium images differ a lot. Therefore we apply automatically
the CLAHE and NL-means algorithm before we feed the images into the neural network.
Depending of the image, the preprocessing step has a high influence to the visibility of neurons. 
Compare the original image <br>
<img src=https://gitlab.com/isyn2/idsair-neuronlabeling/uploads/6d575eb498dc61e5be3c44269d074eeb/grafik.png width="30%" height="30%" /> <br>
with the preprocessed one <br>
<img src=https://gitlab.com/isyn2/idsair-neuronlabeling/uploads/d835b683cdac48123597177792d10e6e/grafik.png width="30%" height="30%" /><br>

