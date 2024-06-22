#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Assess the performance of video decoding in various configurations.

This script will run different video decoding benchmarks where one parameter varies at a time.
These parameters and theirs values are specified in the BENCHMARKS dict.

All of these benchmarks are evaluated within different timestamps modes corresponding to different frame-loading scenarios:
    - `1_frame`: 1 single frame is loaded.
    - `2_frames`: 2 consecutive frames are loaded.
    - `2_frames_4_space`: 2 frames separated by 4 frames are loaded.
    - `6_frames`: 6 consecutive frames are loaded.

These values are more or less arbitrary and based on possible future usage.

These benchmarks are run on the first episode of each dataset specified in DATASET_REPO_IDS.
Note: These datasets need to be image datasets, not video datasets.
"""

import argparse
import datetime as dt
import random
import shutil
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import einops
import numpy as np
import pandas as pd
import PIL
import torch
from skimage.metrics import mean_squared_error, peak_signal_noise_ratio, structural_similarity
from tqdm import tqdm

from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
from lerobot.common.datasets.video_utils import (
    decode_video_frames_torchvision,
    encode_video_frames,
)
from lerobot.common.utils.benchmark import TimeBenchmark

BASE_ENCODING = OrderedDict(
    [
        ("vcodec", "libx264"),
        ("pix_fmt", "yuv444p"),
        ("g", 2),
        ("crf", None),
    ]
)


def parse_int_or_none(value):
    if value.lower() == "none":
        return None
    try:
        return int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid int or None: {value}") from e


def check_datasets_formats(repo_ids: list) -> None:
    for repo_id in repo_ids:
        dataset = LeRobotDataset(repo_id)
        if dataset.video:
            raise ValueError(
                f"Use only image dataset for running this benchmark. Video dataset provided: {repo_id}"
            )


def get_directory_size(directory: Path) -> int:
    total_size = 0
    for item in directory.rglob("*"):
        if item.is_file():
            total_size += item.stat().st_size
    return total_size


def load_original_frames(imgs_dir: Path, timestamps: list[float], fps: int) -> torch.Tensor:
    frames = []
    for ts in timestamps:
        idx = int(ts * fps)
        frame = PIL.Image.open(imgs_dir / f"frame_{idx:06d}.png")
        frame = torch.from_numpy(np.array(frame))
        frame = frame.type(torch.float32) / 255
        frame = einops.rearrange(frame, "h w c -> c h w")
        frames.append(frame)
    return torch.stack(frames)


def save_decoded_frames(
    imgs_dir: Path, save_dir: Path, frames: torch.Tensor, timestamps: list[float], fps: int
) -> None:
    if save_dir.exists() and len(list(save_dir.glob("frame_*.png"))) == len(timestamps):
        return

    save_dir.mkdir(parents=True, exist_ok=True)
    for i, ts in enumerate(timestamps):
        idx = int(ts * fps)
        frame_hwc = (frames[i].permute((1, 2, 0)) * 255).type(torch.uint8).cpu().numpy()
        PIL.Image.fromarray(frame_hwc).save(save_dir / f"frame_{idx:06d}_decoded.png")
        shutil.copyfile(imgs_dir / f"frame_{idx:06d}.png", save_dir / f"frame_{idx:06d}_original.png")


def save_first_episode(imgs_dir: Path, dataset: LeRobotDataset) -> Path:
    ep_num_images = dataset.episode_data_index["to"][0].item()
    if imgs_dir.exists() and len(list(imgs_dir.glob("frame_*.png"))) == ep_num_images:
        return imgs_dir

    imgs_dir.mkdir(parents=True, exist_ok=True)
    hf_dataset = dataset.hf_dataset.with_format(None)

    # We only save images from the first camera
    img_keys = [key for key in hf_dataset.features if key.startswith("observation.image")]
    imgs_dataset = hf_dataset.select_columns(img_keys[0])

    for i, item in enumerate(
        tqdm(imgs_dataset, desc=f"saving {dataset.repo_id} first episode images", leave=False)
    ):
        img = item[img_keys[0]]
        img.save(str(imgs_dir / f"frame_{i:06d}.png"), quality=100)

        if i >= ep_num_images - 1:
            break

    return imgs_dir


def sample_timestamps(timestamps_mode: str, ep_num_images: int, fps: int):
    # Start at 5 to allow for 2_frames_4_space and 6_frames
    idx = random.randint(5, ep_num_images - 1)
    match timestamps_mode:
        case "1_frame":
            frame_indexes = [idx]
        case "2_frames":
            frame_indexes = [idx - 1, idx]
        case "2_frames_4_space":
            frame_indexes = [idx - 5, idx]
        case "6_frames":
            frame_indexes = [idx - i for i in range(6)][::-1]
        case _:
            raise ValueError(timestamps_mode)

    return [idx / fps for idx in frame_indexes]


def benchmark_decoding(
    imgs_dir: Path,
    video_path: Path,
    timestamps_mode: str,
    backend: str,
    ep_num_images: int,
    fps: int,
    num_samples: int = 50,
    num_workers: int = 4,
    save_frames: bool = False,
) -> dict:
    def process_sample(t):
        time_benchmark = TimeBenchmark()
        timestamps = sample_timestamps(timestamps_mode, ep_num_images, fps)
        num_frames = len(timestamps)
        result = {
            "psnr_values": [],
            "ssim_values": [],
            "mse_values": [],
        }

        with time_benchmark:
            frames = decode_video_frames_torchvision(
                video_path, timestamps=timestamps, tolerance_s=1e-4, backend=backend
            )
        result["load_time_video_ms"] = time_benchmark.result_ms / num_frames

        with time_benchmark:
            original_frames = load_original_frames(imgs_dir, timestamps, fps)
        result["load_time_images_ms"] = time_benchmark.result_ms / num_frames

        frames_np, original_frames_np = frames.numpy(), original_frames.numpy()
        for i in range(num_frames):
            result["mse_values"].append(mean_squared_error(original_frames_np[i], frames_np[i]))
            result["psnr_values"].append(
                peak_signal_noise_ratio(original_frames_np[i], frames_np[i], data_range=1.0)
            )
            result["ssim_values"].append(
                structural_similarity(original_frames_np[i], frames_np[i], data_range=1.0, channel_axis=0)
            )

        if save_frames and t == 0:
            save_dir = video_path.with_suffix("") / f"{timestamps_mode}_{backend}"
            save_decoded_frames(imgs_dir, save_dir, frames, timestamps, fps)

        return result

    load_times_video_ms = []
    load_times_images_ms = []
    mse_values = []
    psnr_values = []
    ssim_values = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_sample, i) for i in range(num_samples)]
        for future in tqdm(as_completed(futures), total=num_samples, desc="samples", leave=False):
            result = future.result()
            load_times_video_ms.append(result["load_time_video_ms"])
            load_times_images_ms.append(result["load_time_images_ms"])
            psnr_values.extend(result["psnr_values"])
            ssim_values.extend(result["ssim_values"])
            mse_values.extend(result["mse_values"])

    avg_load_time_video_ms = float(np.array(load_times_video_ms).mean())
    avg_load_time_images_ms = float(np.array(load_times_images_ms).mean())
    video_images_load_time_ratio = avg_load_time_video_ms / avg_load_time_images_ms

    return {
        "avg_load_time_video_ms": avg_load_time_video_ms,
        "avg_load_time_images_ms": avg_load_time_images_ms,
        "video_images_load_time_ratio": video_images_load_time_ratio,
        "avg_mse": float(np.mean(mse_values)),
        "avg_psnr": float(np.mean(psnr_values)),
        "avg_ssim": float(np.mean(ssim_values)),
    }


def benchmark_encoding_decoding(
    dataset: LeRobotDataset,
    video_path: Path,
    imgs_dir: Path,
    encoding_cfg: dict,
    decoding_cfg: dict,
    num_samples: int,
    num_workers: int,
    save_frames: bool,
    overwrite: bool = False,
    seed: int = 1337,
):
    fps = dataset.fps

    if overwrite or not video_path.is_file():
        tqdm.write(f"encoding {video_path}")
        encode_video_frames(
            imgs_dir=imgs_dir,
            video_path=video_path,
            fps=fps,
            video_codec=encoding_cfg["vcodec"],
            pixel_format=encoding_cfg["pix_fmt"],
            group_of_pictures_size=encoding_cfg.get("g"),
            constant_rate_factor=encoding_cfg.get("crf"),
            overwrite=True,
        )

    ep_num_images = dataset.episode_data_index["to"][0].item()
    width, height = tuple(dataset[0][dataset.camera_keys[0]].shape[-2:])
    num_pixels = width * height
    video_size_bytes = video_path.stat().st_size
    images_size_bytes = get_directory_size(imgs_dir)
    video_images_size_ratio = video_size_bytes / images_size_bytes

    random.seed(seed)
    benchmark_table = []
    for timestamps_mode in tqdm(
        decoding_cfg["timestamps_modes"], desc="decodings (timestamps_modes)", leave=False
    ):
        for backend in tqdm(decoding_cfg["backends"], desc="decodings (backends)", leave=False):
            benchmark_row = benchmark_decoding(
                imgs_dir,
                video_path,
                timestamps_mode,
                backend,
                ep_num_images,
                fps,
                num_samples,
                num_workers,
                save_frames,
            )
            benchmark_row.update(
                **{
                    "repo_id": dataset.repo_id,
                    "resolution": f"{width} x {height}",
                    "num_pixels": num_pixels,
                    "video_size_bytes": video_size_bytes,
                    "images_size_bytes": images_size_bytes,
                    "video_images_size_ratio": video_images_size_ratio,
                    "timestamps_mode": timestamps_mode,
                    "backend": backend,
                },
                **encoding_cfg,
            )
            benchmark_table.append(benchmark_row)

    return benchmark_table


def main(
    output_dir: Path,
    repo_ids: list[str],
    # vcodec: list[str],
    pix_fmt: list[str],
    g: list[int],
    crf: list[int],
    timestamps_modes: list[str],
    backends: list[str],
    num_samples: int,
    num_workers: int,
    save_frames: bool,
):
    check_datasets_formats(repo_ids)
    encoding_benchmarks = {
        # "vcodec": vcodec,
        "pix_fmt": pix_fmt,
        "g": g,
        "crf": crf,
    }
    decoding_benchmarks = {
        "timestamps_modes": timestamps_modes,
        "backends": backends,
    }
    benchmark_table = []
    for repo_id in tqdm(repo_ids, desc="datasets"):
        dataset = LeRobotDataset(repo_id)
        imgs_dir = output_dir / "images" / dataset.repo_id.replace("/", "_")
        # We only use the first episode
        save_first_episode(imgs_dir, dataset)

        for key, values in tqdm(encoding_benchmarks.items(), desc="encodings", leave=False):
            for value in tqdm(values, desc=f"encodings ({key})", leave=False):
                encoding_cfg = BASE_ENCODING.copy()
                encoding_cfg[key] = value
                args_path = Path("_".join(str(value) for value in encoding_cfg.values()))
                video_path = output_dir / "videos" / args_path / f"{repo_id.replace('/', '_')}.mp4"
                benchmark_table += benchmark_encoding_decoding(
                    dataset,
                    video_path,
                    imgs_dir,
                    encoding_cfg,
                    decoding_benchmarks,
                    num_samples,
                    num_workers,
                    save_frames,
                )

    columns_order = ["repo_id", "resolution", "num_pixels"]
    columns_order += list(BASE_ENCODING.keys())
    columns_order += [
        "video_size_bytes",
        "images_size_bytes",
        "video_images_size_ratio",
        "timestamps_mode",
        "backend",
        "avg_load_time_video_ms",
        "avg_load_time_images_ms",
        "video_images_load_time_ratio",
        "avg_mse",
        "avg_psnr",
        "avg_ssim",
    ]
    benchmark_df = pd.DataFrame(benchmark_table, columns=columns_order)
    now = dt.datetime.now()
    csv_path = output_dir / f"{now:%Y-%m-%d}_{now:%H-%M-%S}_{num_samples}-samples.csv"
    benchmark_df.to_csv(csv_path, header=True, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/video_benchmark"),
        help="Directory where the video benchmark outputs are written.",
    )
    parser.add_argument(
        "--repo-ids",
        type=str,
        nargs="*",
        default=[
            "lerobot/pusht_image",
            "aliberts/aloha_mobile_shrimp_image",
            "aliberts/paris_street",
            "aliberts/kitchen",
        ],
        help="Datasets repo-ids to test against. First episodes only are used. Must be images.",
    )
    # TODO(aliberts): add "libaom-av1" (need to build ffmpeg with "--enable-libaom")
    # parser.add_argument(
    #     "--vcodec",
    #     type=str,
    #     nargs="*",
    #     default=["libx264", "libaom-av1"],
    #     help="Video codecs to be tested",
    # )
    parser.add_argument(
        "--pix-fmt",
        type=str,
        nargs="*",
        default=["yuv444p", "yuv420p"],
        help="Pixel formats (chroma subsampling) to be tested",
    )
    parser.add_argument(
        "--g",
        type=parse_int_or_none,
        nargs="*",
        default=[1, 2, 3, 4, 5, 6, 10, 15, 20, 40, 100, None],
        help="Group of pictures sizes to be tested.",
    )
    parser.add_argument(
        "--crf",
        type=parse_int_or_none,
        nargs="*",
        default=[0, 5, 10, 15, 20, 25, 30, 40, 50, None],
        help="Constant rate factors to be tested.",
    )
    parser.add_argument(
        "--timestamps-modes",
        type=str,
        nargs="*",
        default=[
            "1_frame",
            "2_frames",
            "2_frames_4_space",
            "6_frames",
        ],
        help="Timestamps scenarios to be tested.",
    )
    parser.add_argument(
        "--backends",
        type=str,
        nargs="*",
        default=["pyav", "video_reader"],
        help="Torchvision decoding backend to be tested.",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=50,
        help="Number of samples for each encoding x decoding config.",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=10,
        help="Number of processes for parallelized sample processing.",
    )
    parser.add_argument(
        "--save-frames",
        type=int,
        default=0,
        help="Whether to save decoded frames or not. Enter a non-zero number for true.",
    )
    args = parser.parse_args()
    main(**vars(args))
