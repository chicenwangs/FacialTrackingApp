"""FaceCam: webcam face framing into a virtual camera.

The capture, framing and virtual-camera layers come from an earlier prototype with
its hand-sign macro system removed. Importing this package disables the slow MSMF hardware
transform path before OpenCV is loaded.
"""

import os

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2

# OpenCV's thread pools cost ~20MB of working set here and the image work in
# this app is small; one thread is faster overall and leaves more room for TFLite.
cv2.setNumThreads(1)
