## Example Data

The example data for testing is drawn from the [Neurofinder dataset](http://neurofinder.codeneuro.org/).

### Testing Segmentation Process
To facilitate the testing of the segmentation process, we have uploaded a mean image derived from the first 436 images using ViNe-Seg's microscope mode. 

**Note:** Generating a mean image from a relatively small number of images is not ideal for subsequent segmentation. This limitation is acknowledged, but our primary aim here is to:

- Provide a practical example for users.
- Enable testing of segmentation on a mean image.
- Offer an opportunity to experiment with trace extraction.

This sample dataset, originating from the Neurofinder's 03.00 dataset, serves as a basic demonstration of ViNe-Seg's capabilities.

## ViNe-Seg Tutorial using the example data

Here we assume you already installed and started ViNe-Seg as described in the [Instructions](https://github.com/NiRuff/ViNe-Seg/blob/main/Readme.md)

#### Loading the Mean image

Press the _Open_ button and load the mean or max projection of your experiment. In this case, the 0-436_mean.png file.

<!---![open1](https://github.com/NiRuff/GithubMedia/blob/main/tutorial1.png?raw=true)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/tutorial1.png?raw=true"  width="85%"></p>

After clicking the button, a dialogue will open from which you can load the respective file

<!---![open2](https://github.com/NiRuff/GithubMedia/blob/main/tutorial2.png?raw=true)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/tutorial2.png?raw=true"  width="85%"></p>

#### Running a ViNe-Seg model

In the _Auto-Segmentation_ menu you can download other ViNe-Seg models (_ViNe-Seg Model Manager_), choose a specific model and run the segmentation step. For now, click the _ViNe-Seg_ Button in the _Auto-Segmentation_ menu to start the segmentation process on your chosen image.

<!---![seg](https://github.com/NiRuff/GithubMedia/blob/main/tutorial3.png?raw=true)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/tutorial3.png?raw=true"  width="85%"></p>

#### Selecting a confidence value

A very powerful tool to adjust your segmentation results is using the confidence slider. Here, you can adjust, how confident your model has to be in order to accept a segmentation result. Do not hesitate to use values lower than the default of 50 if the results seem more meaningful to you. This is a value that can be properly reported for a respective model and therefore leads to reproducible results when repeating the segmentation process. 

<!---![conf](https://github.com/NiRuff/GithubMedia/blob/main/confidence.gif?raw=true)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/confidence.gif?raw=true"  width="85%"></p>

#### Manually adjusting segmentation results

In this step, you can further vary your segmentation output. Here you can delete or add ROIs and also manipulate the shape of already existing polygons. Every shape that has been user-edited will change its color to a light blue to keep track of the editing process. Further, shapes that are smaller or larger than defined in the expected borders are shown in red and dark blue, respectively. This setting can be adapted in the buttons for _Adjust Min/Max Neuron Size_.


<!---![segAdj](https://github.com/NiRuff/GithubMedia/blob/main/edit.gif?raw=true)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/edit.gif?raw=true"  width="85%"></p>

#### Extract Traces

After adjusting your segmentation and saving the results (Ctrl + S), you can initiate the _Extract Traces_-Operation in the _Trace Extraction_ Menu. After clicking the button you will be prompted for the directory in which your experiment (typically your tif(f) stack) is stored. After providing these files, you need to confirm the number of frames detected in your directory.

| Extract Traces         | Choose Directory       |
| ---------------------- | ---------------------- |
| ![traceEx](https://github.com/NiRuff/GithubMedia/blob/main/tutorial4.png?raw=true) | ![prompt](https://github.com/NiRuff/GithubMedia/blob/main/tutorial5.png?raw=true) |


This might be the most time-consuming process in the whole ViNe-Seg pipeline, so you might need to be patient for a minute here if you selected many ROIs.

After the trace extraction was successful, you will be prompted for a long median filter length for the dynamic df/f calculation. The default of 5401 frames was selected in accordance with the ABO pipeline.


<!---![dff](https://github.com/NiRuff/GithubMedia/blob/main/tutorial7.png?raw=true)--->
<p align="center"><img src="https://github.com/NiRuff/GithubMedia/blob/main/tutorial7.png?raw=true"  width="50%"></p>



