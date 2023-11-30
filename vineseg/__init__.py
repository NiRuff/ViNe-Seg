# flake8: noqa

import logging
import sys
from pathlib import Path
import json
import zipfile

from qtpy import QT_VERSION

__appname__ = "ViNe-Seg"

# Semantic Versioning 2.0.0: https://semver.org/
# 1. MAJOR version when you make incompatible API changes;
# 2. MINOR version when you add functionality in a backwards-compatible manner;
# 3. PATCH version when you make backwards-compatible bug fixes.
__version__ = "0.0.48"

QT4 = QT_VERSION[0] == "4"
QT5 = QT_VERSION[0] == "5"
del QT_VERSION


PY2 = sys.version[0] == "2"
PY3 = sys.version[0] == "3"
del sys

from .label_file import LabelFile
from . import testing
from . import utils

### Model version check
# circumvent ssl error
import os, ssl
if (not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None)):
    ssl._create_default_https_context = ssl._create_unverified_context

# for having unique ctype so that windows won't group with random programs in the taskbar
import ctypes
myappid = __appname__ + __version__ # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
# circumvent duplicate dll error
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

import urllib.request
default_url = "http://vineseg.isyn-mainz.de/"
has_a_model = False

try:
    from tensorflow.version import VERSION

    cascade_enabled = True
except ImportError:
    cascade_enabled = False


# check if local manifest file exists
script_dir = os.path.dirname(__file__)
manifest_path = os.path.join(script_dir, "experiments/MANIFEST.json")
manifest_path_cascade = os.path.join(script_dir, "CASCADE_models/MANIFEST.json")
if os.path.isfile(manifest_path):
    # manifest exists
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    if len(manifest["installed"]) > 0:
        has_a_model = True
        # print which models are installed
        #print("Currently installed ViNe-Seg models:")
        #for model in manifest["installed"]:
        #    print(model["name"])
    else:
        has_a_model = False
else:
    # if no local manifest found, assume no models has been downloaded
    has_a_model = False

# if no models found, download the default model
if not has_a_model:
    print("No ViNe-Seg Models are currently installed! Downloading the default model...")
    # get online manifest
    with urllib.request.urlopen(default_url + "MANIFEST.json") as url:
        online_manifest = json.loads(url.read().decode())

    # get the path of default model
    default_model_path = online_manifest["default"]["location"]
    default_model_url = default_url + "models/" + default_model_path
    print(default_model_path, default_model_url)

    # start if/else here
    # new models
    if default_model_path.startswith("vine_seg"):

        # check paths for download exists
        if not os.path.exists(
                os.path.join(os.path.sep, script_dir, "experiments")):
            os.makedirs(os.path.join(os.path.sep, script_dir, "experiments"))

        print("Retrieving file 1 of 1.")
        urllib.request.urlretrieve(default_model_url,
                                   os.path.join(script_dir, "experiments", default_model_path))


    # old models
    else:
        # check paths for download exists
        if not os.path.exists(
                os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights")):
            os.makedirs(os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights"))
        if not os.path.exists(
                os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights_swa")):
            os.makedirs(os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights_swa"))

        # download model
        print("Retrieving file 1 of 3.")
        urllib.request.urlretrieve(default_model_url + '/trained_weights/trained_weights.pth',
                                   os.path.join(script_dir, "experiments", default_model_path,
                                                "trained_weights/trained_weights.pth"))
        print("Retrieving file 2 of 3.")
        urllib.request.urlretrieve(default_model_url + '/trained_weights_swa/trained_weights.pth',
                                   os.path.join(script_dir, "experiments", default_model_path,
                                                "trained_weights_swa/trained_weights.pth"))
        print("Retrieving file 3 of 3.")
        urllib.request.urlretrieve(default_model_url + '/Experiment_parameter.json',
                                   os.path.join(script_dir, "experiments", default_model_path,
                                                "Experiment_parameter.json"))

    # # check paths for download exists
    # if not os.path.exists(os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights")):
    #     os.makedirs(os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights"))
    # if not os.path.exists(
    #         os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights_swa")):
    #     os.makedirs(os.path.join(os.path.sep, script_dir, "experiments", default_model_path, "trained_weights_swa"))
    #
    # # download model
    # print("Please wait.")
    # print("Retrieving file 1 of 3.")
    # urllib.request.urlretrieve(default_model_url + '/trained_weights/trained_weights.pth',
    #                            os.path.join(script_dir, "experiments", default_model_path,
    #                                         "trained_weights/trained_weights.pth"))
    # print("Retrieving file 2 of 3.")
    # urllib.request.urlretrieve(default_model_url + '/trained_weights_swa/trained_weights.pth',
    #                            os.path.join(script_dir, "experiments", default_model_path,
    #                                         "trained_weights_swa/trained_weights.pth"))
    # print("Retrieving file 3 of 3.")
    # urllib.request.urlretrieve(default_model_url + '/Experiment_parameter.json',
    #                            os.path.join(script_dir, "experiments", default_model_path, "Experiment_parameter.json"))

    # make a local manifest file
    local_manifest = {
        "installed": [{
            "name": "Default Model",
            "location": default_model_path
        }]
    }
    json_string = json.dumps(local_manifest)
    with open(manifest_path, 'w') as outfile:
        outfile.write(json_string)
    print("Done \nDownloaded the ViNe-Seg default model.")

# Same for CASCADE
if cascade_enabled:
    has_a_model = False
    manifest_path_cascade = os.path.join(script_dir, "CASCADE_models/MANIFEST.json")

    if os.path.isfile(manifest_path_cascade):
        # manifest exists
        with open(manifest_path_cascade, 'r') as f:
            manifest = json.load(f)
        if len(manifest["installed"]) > 0:
            has_a_model = True
            # print which models are installed
    #        print("Currently installed CASCADE models:")
    #        for model in manifest["installed"]:
    #            print(model["name"])
        else:
            has_a_model = False
    else:
        # if no local manifest found, assume no models has been downloaded
        has_a_model = False

    # if no models found, download the default model
    if not has_a_model:
        print("No CASCADE Models are currently installed! Downloading the default model...")
        # get online manifest
        with urllib.request.urlopen(default_url + "MANIFEST_CASCADE.json") as url:
            online_manifest = json.loads(url.read().decode())

        # get the path of default model
        default_model_name = online_manifest["default"]["name"]
        default_model_path = online_manifest["default"]["location"]
        default_model_url = online_manifest["default"]["url"]

        # check paths for download exists
        if not os.path.exists(os.path.join(os.path.sep, script_dir, "CASCADE_models", default_model_path)):
            os.makedirs(os.path.join(os.path.sep, script_dir, "CASCADE_models", default_model_path))

        # download model
        print("Retrieving file 1 of 1.")
        urllib.request.urlretrieve(default_model_url,
                                   os.path.join(script_dir, "CASCADE_models", default_model_path) + ".zip")
        # unzip file
        my_zip = zipfile.ZipFile(os.path.join(script_dir, "CASCADE_models", default_model_path) + ".zip")
        storage_path = os.path.join(script_dir, "CASCADE_models", default_model_path)
        for file in my_zip.namelist():
            my_zip.extract(file, storage_path)
        my_zip.close()
        # remove zip file after extraction
        os.remove(os.path.join(script_dir, "CASCADE_models", default_model_path) + ".zip")

        # make a local manifest file
        local_manifest = {
            "installed": [{
                "name": default_model_name,
                "location": default_model_path
            }]
        }
        json_string = json.dumps(local_manifest)
        with open(manifest_path_cascade, 'w') as outfile:
            outfile.write(json_string)
        print("Done \nDownloaded the CASCADE default model.")