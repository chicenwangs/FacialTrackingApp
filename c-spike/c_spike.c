/* C feasibility spike: YuNet ONNX inference through ONNX Runtime's C API.
   Measures RSS and latency so it can be compared with the Python and Rust builds. */

/* The bundled ORT DLL exposes API 17 (its version info says 1.17.1). */
#define ORT_API_VERSION 17
#include <onnxruntime_c_api.h>

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <windows.h>
#include <psapi.h>

static double rss_mb(void) {
    PROCESS_MEMORY_COUNTERS counters;
    counters.cb = sizeof(counters);
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof(counters))) return 0.0;
    return (double)counters.WorkingSetSize / 1000000.0;
}

static wchar_t *to_wide(const char *text) {
    int needed = MultiByteToWideChar(CP_UTF8, 0, text, -1, NULL, 0);
    wchar_t *wide = (wchar_t *)malloc((size_t)needed * sizeof(wchar_t));
    MultiByteToWideChar(CP_UTF8, 0, text, -1, wide, needed);
    return wide;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: c_spike <model.onnx> <input.nchw.bin>\n");
        return 1;
    }

    printf("start RSS %.1f MB\n", rss_mb());
    const OrtApi *ort = OrtGetApiBase()->GetApi(17);

    OrtEnv *env = NULL;
    ort->CreateEnv(ORT_LOGGING_LEVEL_WARNING, "facecam-c-spike", &env);
    OrtSessionOptions *options = NULL;
    ort->CreateSessionOptions(&options);
    ort->SetIntraOpNumThreads(options, 1);

    wchar_t *model_path = to_wide(argv[1]);
    OrtSession *session = NULL;
    if (ort->CreateSession(env, model_path, options, &session) != NULL) {
        fprintf(stderr, "failed to load model\n");
        return 1;
    }
    printf("after model load RSS %.1f MB\n", rss_mb());

    OrtAllocator *allocator = NULL;
    ort->GetAllocatorWithDefaultOptions(&allocator);
    size_t input_count = 0;
    ort->SessionGetInputCount(session, &input_count);
    char *input_name = NULL;
    ort->SessionGetInputName(session, 0, allocator, &input_name);
    size_t output_count = 0;
    ort->SessionGetOutputCount(session, &output_count);
    char *output_name = NULL;
    ort->SessionGetOutputName(session, 0, allocator, &output_name);
    printf("inputs=%zu first=%s | outputs=%zu first=%s\n",
           input_count, input_name, output_count, output_name);

    const int64_t shape[] = {1, 3, 640, 640};
    size_t elements = 1 * 3 * 640 * 640;
    float *pixels = (float *)malloc(elements * sizeof(float));
    FILE *file = fopen(argv[2], "rb");
    if (!file || fread(pixels, sizeof(float), elements, file) != elements) {
        fprintf(stderr, "failed to read input\n");
        return 1;
    }
    fclose(file);

    OrtMemoryInfo *memory = NULL;
    ort->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &memory);
    OrtValue *input = NULL;
    ort->CreateTensorWithDataAsOrtValue(memory, pixels, elements * sizeof(float), shape, 4,
                                        ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT, &input);
    const char *input_names[] = {input_name};
    const char *output_names[] = {output_name};

    OrtValue *output = NULL;
    ort->Run(session, NULL, input_names, (const OrtValue *const *)&input, 1,
             output_names, 1, &output);
    printf("after inference RSS %.1f MB\n", rss_mb());
    ort->ReleaseValue(output);

    clock_t started = clock();
    for (int i = 0; i < 20; ++i) {
        output = NULL;
        ort->Run(session, NULL, input_names, (const OrtValue *const *)&input, 1,
                 output_names, 1, &output);
        ort->ReleaseValue(output);
    }
    double ms = (double)(clock() - started) * 1000.0 / CLOCKS_PER_SEC / 20.0;
    printf("inference %.1f ms avg over 20\n", ms);
    printf("final RSS %.1f MB\n", rss_mb());

    ort->AllocatorFree(allocator, input_name);
    ort->AllocatorFree(allocator, output_name);
    ort->ReleaseValue(input);
    ort->ReleaseMemoryInfo(memory);
    ort->ReleaseSession(session);
    ort->ReleaseSessionOptions(options);
    ort->ReleaseEnv(env);
    free(pixels);
    free(model_path);
    return 0;
}
