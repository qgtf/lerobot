# Video benchmark


## Questions

What is the optimal trade-off between:
- maximizing loading time with random access,
- minimizing memory space on disk,
- maximizing success rate of policies,
- compatibility accross devices/platforms (e.g. video players, web browsers) for playing videos?

How to encode videos?
- Which video codec (`-vcodec`) to use? `libx264`, `libx265`, `libaom`/`libsvtav1`?
- How much compression (`-crf`)? No compression with `0`, normal compression with `20` or extreme with `56`?
- What pixel format to use (`-pix_fmt`)? `yuv444p` or `yuv420p`?
- How many key frames (`-g`)? A key frame every `10` frames?

How to decode videos?
- Which `decoder`? `torchvision`, `torchaudio`, `ffmpegio`, `decord`, or `nvc`?
- What scenarios to use for the requesting timestamps during benchmark? (`timestamps_mode`)

## Metrics

**Data compression ratio (lower is better)**
`video_images_size_ratio` is the ratio of the memory space on disk taken by the encoded video over the memory space taken by the original images. For instance, `video_images_size_ratio=25%` means that the video takes 4 times less memory space on disk compared to the original images.

**Loading time ratio (lower is better)**
`video_images_load_time_ratio` is the ratio of the time it takes to decode frames from the video at a given timestamps over the time it takes to load the exact same original images. Lower is better. For instance, `video_images_load_time_ratio=200%` means that decoding from video is 2 times slower than loading the original images.

**Average Mean Square Error (lower is better)**
`avg_mse` is the average mean square error between each decoded frame and its corresponding original image over all requested timestamps, and also divided by the number of pixels in the image to be comparable when switching to different image sizes.

**Average Peak Signal to Noise Ratio (higher is better)**
`avg_psnr` measures the ratio between the maximum possible power of a signal and the power of corrupting noise that affects the fidelity of its representation. Higher PSNR indicates better quality.

**Average Structural Similarity Index Measure (higher is better)**
`avg_ssim` evaluates the perceived quality of images by comparing luminance, contrast, and structure. SSIM values range from -1 to 1, where 1 indicates perfect similarity.

<!-- **Loss of a pretrained policy (higher is better)** (not available)
`loss_pretrained` is the result of evaluating with the selected encoding/decoding settings a policy pretrained on original images. It is easier to understand than `avg_l2_error`.

**Success rate after retraining (higher is better)** (not available)
`success_rate` is the result of training and evaluating a policy with the selected encoding/decoding settings. It is the most difficult metric to get but also the very best. -->

## Variables

**Image content & size**
We don't expect the same optimal settings for a dataset of images from a simulation, or from real-world in an appartment, or in a factory, or outdoor, or with lots of moving objects in the scene, etc. Similarly, loading times might not vary linearly with the image size (resolution).
For these reasons, we run this benchmark on four datasets:
- `lerobot/pusht_image`: (96 x 96 pixels) simulation with simple geometric shapes, fixed camera.
- `aliberts/aloha_mobile_shrimp_image`: (480 x 640 pixels) real-world indoor, moving camera.
- `aliberts/paris_street`: (720 x 1280 pixels) real-world outdoor, moving camera.
- `aliberts/kitchen`: (1080 x 1920 pixels) real-world indoor, fixed camera.

Note: The datasets used for this benchmark need to be image datasets, not video datasets.

**Requested timestamps**
Given the way video decoding works, once a keyframe has been loaded the decoding of subsequent frames is fast.
This of course is affected by the `-g` parameter at encoding, which specifies the frequency of the keyframes. Given our typical use cases in robotics policies which might request a few timestamps in different random places, we want to replicate these use cases with the following scenarios:
- `1_frame`: 1 frame,
- `2_frames`: 2 consecutive frames (e.g. `[t, t + 1 / fps]`),
- `6_frames`: 6 consecutive frames (e.g. `[t + i / fps for i in range(6)]`)

Note that this differs significantly from a typical use case like watching a movie, in which every frame is loaded sequentially from the beginning to the end and it's acceptable to have big values for `-g`.

Additionally, because some policies might request single timestamps that are a few frames appart, we also have the following scenario:
- `2_frames_4_space`: 2 frames space by 4 consecutive frames of spacing (e.g `[t, t + 5 / fps]`),

However, due to how video decoding is implemented with `pyav`, we don't have access to an accurate seek so in practice this scenario is essentially the same as `6_frames` since all 6 frames between `t` and `t + 5 / fps` will be decoded.

**Data augmentations**
We might revisit this benchmark and find better settings if we train our policies with various data augmentations to make them more robust (e.g. robust to color changes, compression, etc.).

## How the benchmark works

The benchmark evaluates both encoding and decoding of video frames.
We first iterate through every combination of `vcodec` and `pix_fmt` settings, on which we iterate through every dataset on their first episode.
For each of these iteration, we change a single encoding parameter among `g` and `crf` to one of the values specified in the parameters (we don't test every combination of those as this would be computationally too heavy).
This gives a unique set of encoding parameters which is used to encode the episode.

Then, we iterate through every combination of the decoding parameters `backend` and `timestamps_mode`. For each of these combination, we record the metrics of a number of samples (given by `--num-samples`). This is parallelized for efficiency and the number of processes can be controlled with `--num-workers`. Ideally, it's best to have a `--num-samples` that is divisible by `--num-workers`.

Intermediate results saved for each `vcodec` and `pix_fmt` combination in csv tables.
These are then all concatenated to a single table ready for analysis.

## Install

Building ffmpeg from source is required to include libx265 and libaom/libsvtav1 (av1) video codecs ([compilation guide](https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu)).

**Note:** While you still need to build torchvision with a conda-installed `ffmpeg<4.3` to use the `video_reader` decoder (as described in [#220](https://github.com/huggingface/lerobot/pull/220)), you also need another version which is custom-built with all the video codecs for encoding. For the script to then use that version, you can prepend the command above with `PATH="$HOME/bin:$PATH"`, which is where ffmpeg should be built.

## Adding a video decoder

Right now, we're only benchmarking the two video decoder available with torchvision: `pyav` and `video_reader`.
You can easily add a new decoder to benchmark by adding it to this function in the script:
```diff
def decode_video_frames(
    video_path: str,
    timestamps: list[float],
    tolerance_s: float,
    backend: str,
) -> torch.Tensor:
    if backend in ["pyav", "video_reader"]:
        return decode_video_frames_torchvision(
            video_path, timestamps, tolerance_s, backend
        )
+    elif backend == ["your_decoder"]:
+        return your_decoder_function(
+            video_path, timestamps, tolerance_s, backend
+        )
    else:
        raise NotImplementedError(backend)
```


## Example
For a quick run, you can try these parameters:
```bash
python benchmark/video/run_video_benchmark.py \
    --output-dir outputs/video_benchmark \
    --repo-ids \
        lerobot/pusht_image \
        aliberts/aloha_mobile_shrimp_image \
    --vcodec libx264 libx265 \
    --pix-fmt yuv444p yuv420p \
    --g 2 20 None \
    --crf 10 40 None \
    --timestamps-modes 1_frame 2_frames \
    --backends pyav video_reader \
    --num-samples 5 \
    --num-workers 5 \
    --save-frames 0
```

## Results

### Reproduce
We ran the benchmark with the following parameters:
```bash
# h264 and h265 encodings
python benchmark/video/run_video_benchmark.py \
    --output-dir outputs/video_benchmark \
    --repo-ids \
        lerobot/pusht_image \
        aliberts/aloha_mobile_shrimp_image \
        aliberts/paris_street \
        aliberts/kitchen \
    --vcodec libx264 libx265 \
    --pix-fmt yuv444p yuv420p \
    --g 1 2 3 4 5 6 10 15 20 40 None \
    --crf 0 5 10 15 20 25 30 40 50 None \
    --timestamps-modes 1_frame 2_frames 6_frames \
    --backends pyav video_reader \
    --num-samples 50 \
    --num-workers 5 \
    --save-frames 1

# av1 encoding (only compatible with yuv420p and pyav decoder)
python benchmark/video/run_video_benchmark.py \
    --output-dir outputs/video_benchmark \
    --repo-ids \
        lerobot/pusht_image \
        aliberts/aloha_mobile_shrimp_image \
        aliberts/paris_street \
        aliberts/kitchen \
    --vcodec libsvtav1 \
    --pix-fmt yuv420p \
    --g 1 2 3 4 5 6 10 15 20 40 None \
    --crf 0 5 10 15 20 25 30 40 50 None \
    --timestamps-modes 1_frame 2_frames 6_frames \
    --backends pyav \
    --num-samples 50 \
    --num-workers 5 \
    --save-frames 1
```

### Raw results
Full results are available [here](https://docs.google.com/spreadsheets/d/1OYJB43Qu8fC26k_OyoMFgGBBKfQRCi4BIuYitQnq3sw/edit?usp=sharing)


### Comparison with the previous benchmark
We compare the average l2 error (`avg_l2e`) used in the previous version of this benchmark with the current metrics (`avg_mse`, `avg_psnr`, `avg_ssim`).
The comparison is done on the former baseline of parameters: `vcodec=libx264`, `pix_fmt=yuv444p`, `g=2`, `crf=None`

| repo_id                            | resolution  | vcodec  | pix_fmt | g | crf | timestamps_mode | backend | avg_l2e  | avg_mse  | avg_psnr | avg_ssim |
| ---------------------------------- | ----------- | ------- | ------- | - | --- | --------------- | ------- | -------- | -------- | -------- | -------- |
| lerobot/pusht_image                | 96 x 96     | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 1.35E-04 | 5.74E-05 | 42.59    | 99.61%   |
| lerobot/pusht_image                | 96 x 96     | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 1.32E-04 | 5.47E-05 | 42.81    | 99.63%   |
| lerobot/pusht_image                | 96 x 96     | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 1.36E-04 | 5.78E-05 | 42.58    | 99.62%   |
| lerobot/pusht_image                | 96 x 96     | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 1.35E-04 | 5.74E-05 | 42.59    | 99.61%   |
| lerobot/pusht_image                | 96 x 96     | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 1.32E-04 | 5.47E-05 | 42.81    | 99.63%   |
| lerobot/pusht_image                | 96 x 96     | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 1.36E-04 | 5.78E-05 | 42.58    | 99.62%   |
| aliberts/aloha_mobile_shrimp_image | 480 x 640   | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 3.63E-05 | 2.32E-04 | 39.98    | 97.43%   |
| aliberts/aloha_mobile_shrimp_image | 480 x 640   | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 3.71E-05 | 2.88E-04 | 39.90    | 97.18%   |
| aliberts/aloha_mobile_shrimp_image | 480 x 640   | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 3.17E-05 | 1.30E-04 | 40.36    | 97.59%   |
| aliberts/aloha_mobile_shrimp_image | 480 x 640   | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 3.63E-05 | 2.32E-04 | 39.98    | 97.43%   |
| aliberts/aloha_mobile_shrimp_image | 480 x 640   | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 3.71E-05 | 2.88E-04 | 39.90    | 97.18%   |
| aliberts/aloha_mobile_shrimp_image | 480 x 640   | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 3.17E-05 | 1.30E-04 | 40.36    | 97.59%   |
| aliberts/paris_street              | 720 x 1280  | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 2.54E-05 | 2.05E-04 | 37.19    | 96.57%   |
| aliberts/paris_street              | 720 x 1280  | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 2.47E-05 | 1.95E-04 | 37.43    | 96.71%   |
| aliberts/paris_street              | 720 x 1280  | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 2.45E-05 | 1.91E-04 | 37.48    | 96.66%   |
| aliberts/paris_street              | 720 x 1280  | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 2.54E-05 | 2.05E-04 | 37.19    | 96.57%   |
| aliberts/paris_street              | 720 x 1280  | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 2.47E-05 | 1.95E-04 | 37.43    | 96.71%   |
| aliberts/paris_street              | 720 x 1280  | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 2.45E-05 | 1.91E-04 | 37.48    | 96.66%   |
| aliberts/kitchen                   | 1080 x 1920 | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 1.18E-05 | 9.67E-05 | 40.24    | 97.02%   |
| aliberts/kitchen                   | 1080 x 1920 | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 1.16E-05 | 9.38E-05 | 40.38    | 97.08%   |
| aliberts/kitchen                   | 1080 x 1920 | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 1.21E-05 | 1.27E-04 | 40.26    | 97.05%   |
| aliberts/kitchen                   | 1080 x 1920 | libx264 | yuv444p | 2 |     | 1_frame         | pyav    | 1.18E-05 | 9.67E-05 | 40.24    | 97.02%   |
| aliberts/kitchen                   | 1080 x 1920 | libx264 | yuv444p | 2 |     | 2_frames        | pyav    | 1.16E-05 | 9.38E-05 | 40.38    | 97.08%   |
| aliberts/kitchen                   | 1080 x 1920 | libx264 | yuv444p | 2 |     | 6_frames        | pyav    | 1.21E-05 | 1.27E-04 | 40.26    | 97.05%   |



## Parameters selected for LeRobotDataset

Considering these results, we chose what we think is the best set of encoding parameter:
- vcodec: `libsvtav1`
- pix-fmt: `yuv420p`
- g: `2`
- crf: `30`

Since we're using av1 encoding, we're chosing the `pyav` decoder as `video_reader` does not support it (and it's also easier to use).