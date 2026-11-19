# C feasibility spike

`c_spike.c` runs the FaceCam YuNet ONNX model through ONNX Runtime's C API and prints working set and inference time. It is a measurement tool, not part of the app.

Measured here: start 4.3 MB, after model load 18.6 MB, after inference 39.9 MB, final 56.8 MB; 13.8 ms average over 20 inferences at 640×640. A C rewrite would therefore not reduce memory by itself — see the comparison table in the main README.

## Build

1. Get ONNX Runtime headers and `onnxruntime.lib`, for example from the NuGet package `Microsoft.ML.OnnxRuntime` (extract `build/native/include` and `runtimes/win-x64/native`).
2. From a VS 2022 Developer Command Prompt (`vcvars64.bat`):

```bat
cl /nologo /O2 /I "<include>" c_spike.c /link /LIBPATH:<lib> onnxruntime.lib psapi.lib /OUT:c_spike.exe
```

3. Put `onnxruntime.dll` on PATH, then:

```bat
c_spike.exe ..\models\face_detection_yunet_2023mar.onnx <input.nchw.bin>
```

The input file is raw NCHW float32, 1×3×640×640. The bundled ORT DLL exposes API 17, so the source calls `GetApi(17)` explicitly.
