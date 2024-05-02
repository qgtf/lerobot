import importlib

import gymnasium as gym
import pytest
import torch
from gymnasium.utils.env_checker import check_env

import lerobot
from lerobot.common.envs.factory import make_envs
from lerobot.common.envs.utils import preprocess_observations
from lerobot.common.utils.utils import init_hydra_config

from .utils import DEFAULT_CONFIG_PATH, DEVICE, require_env

OBS_TYPES = ["state", "pixels", "pixels_agent_pos"]


@pytest.mark.parametrize("obs_type", OBS_TYPES)
@pytest.mark.parametrize("env_name, env_task", lerobot.env_task_pairs)
@require_env
def test_env(env_name, env_task, obs_type):
    if env_name == "aloha" and obs_type == "state":
        pytest.skip("`state` observations not available for aloha")

    package_name = f"gym_{env_name}"
    importlib.import_module(package_name)
    env = gym.make(f"{package_name}/{env_task}", obs_type=obs_type)
    check_env(env.unwrapped, skip_render_check=True)
    env.close()


@pytest.mark.parametrize("env_name", lerobot.available_envs)
@require_env
def test_factory(env_name):
    cfg = init_hydra_config(
        DEFAULT_CONFIG_PATH,
        overrides=[f"env={env_name}", f"device={DEVICE}"],
    )

    env = make_envs(cfg, n_envs=1)
    obs, _ = env.reset()
    obs = preprocess_observations(obs)

    # test image keys are float32 in range [0,1]
    for key in obs:
        if "image" not in key:
            continue
        img = obs[key]
        assert img.dtype == torch.float32
        # TODO(rcadene): we assume for now that image normalization takes place in the model
        assert img.max() <= 1.0
        assert img.min() >= 0.0

    env.close()
