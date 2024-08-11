# Robots in the real-world

This tutorial explains how to get started with real robots and train a neural network to control them autonomously.

It covers how to:
1. order and assemble your robot,
2. connect your robot, configure and calibrate it,
3. record your dataset and visualize it,
4. train a policy on your data and make sure it's ready for evaluation,
5. evaluate your policy and visualize the result afterwards.

Following these steps, you will reproduce behaviors like picking a lego block and placing it in a bin with a relatively high success rate like in this video: https://x.com/RemiCadene/status/1814680760592572934

While this tutorial is general and easily extendable to any type of robots by changing a configuration, it is based on the [Koch v1.1](https://github.com/jess-moss/koch-v1-1) affordable robot. Koch v1.1 is composed of a leader arm and a follower arm with 6 motors each. In addition, various cameras can record the scene and serve as visual sensors for the robot.

During data collection, you will control the follower arm by moving the leader arm. This is called "teleoperation". It is used to collect robot trajectories.
Then, you will train a neural network to imitate these trajectories. Finally, you will deploy your neural network to autonomously control your robot.

Note: If you have issue at any step of the tutorial, ask for help on [Discord](https://discord.com/invite/s3KuuzsPFb).

## 1. Order and Assemble your Koch v1.1

Follow the sourcing and assembling instructions on the [Koch v1.1 github page](https://github.com/jess-moss/koch-v1-1) to setup the follower and leader arms shown in this picture.

<div style="text-align:center;">
  <img src="../media/tutorial/koch_v1_1_leader_follower.webp?raw=true" alt="Koch v1.1 leader and follower arms" title="Koch v1.1 leader and follower arms" width="50%">
</div>

See the [video tutorial of the assembly](https://youtu.be/5mdxvMlxoos).

## 2. Configure motors, Calibrate arms, Teleoperate your Koch v1.1

Connect the leader arm (the smaller one) with the 5V alimentation and the follower arm with the 12V alimentation. Then connect both arms to your computer with USB.

**Pro tip**: In the next sections, you will understand how our code work by playing with python codes that you will copy past in your terminal. If you are new to this tutorial, we highly recommend to go through this. Next time, when you are more familiar, you can instead run the teleoperate script which will automatically:
- detect a wrong configuration for the motors, and run the configuration procedure (explained after),
- detect a missing calibration and start the calibration procedure (explained after),
- connect the robot and start teleoperation (explained after).
```bash
python lerobot/scripts/control_robot.py teleoperate \
  --robot-path lerobot/configs/robot/koch.yaml \
  --robot-overrides '~cameras'  # do not instantiate the cameras
```


### Control your motors with DynamixelMotorsBus

You can use the [`DynamixelMotorsBus`](../lerobot/common/robot_devices/motors/dynamixel.py) to efficiently read from and write to the motors connected as a chain to the corresponding usb bus. Underneath, it relies on the python [dynamixel sdk](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/sample_code/python_read_write_protocol_2_0/#python-read-write-protocol-20).

**Instantiate**

You will need to instantiate two [`DynamixelMotorsBus`](../lerobot/common/robot_devices/motors/dynamixel.py), one for each arm, with their corresponding usb port (e.g. `DynamixelMotorsBus(port="/dev/tty.usbmodem575E0031751"`).

To find their corresponding ports, run our utility script twice:
```bash
python lerobot/common/robot_devices/motors/dynamixel.py
```

A first time to find the port of the leader arm (e.g. `/dev/tty.usbmodem575E0031751`):
```
Finding all available ports for the DynamixelMotorsBus.
['/dev/tty.usbmodem575E0032081', '/dev/tty.usbmodem575E0031751']
Remove the usb cable from your DynamixelMotorsBus and press Enter when done.

**Disconnect leader arm and press Enter**

The port of this DynamixelMotorsBus is /dev/tty.usbmodem575E0031751
Reconnect the usb cable.
```

A second time to find the port of the follower arm (e.g. `/dev/tty.usbmodem575E0032081`):
```
Finding all available ports for the DynamixelMotorsBus.
['/dev/tty.usbmodem575E0032081', '/dev/tty.usbmodem575E0031751']
Remove the usb cable from your DynamixelMotorsBus and press Enter when done.

**Disconnect follower arm and press Enter**

The port of this DynamixelMotorsBus is /dev/tty.usbmodem575E0032081
Reconnect the usb cable.
```

Then you will need to list their motors with their name, motor index, and model.
Importantly, the initial motor index from factory for every motors is `1`. However, unique indices are required for these motors to function in a chain on a common bus. To this end, you will need to set different indices. We advise to follow the ascendant convention starting from index `1` (e.g. `1,2,3,4,5,6`). These indices will be written inside the persisting memory of each motor during the first connection.

Update the corresponding ports of this code with your ports and run the code to instantiate the Koch leader and follower arms:
```python
from lerobot.common.robot_devices.motors.dynamixel import DynamixelMotorsBus

leader_port = "/dev/tty.usbmodem575E0031751"
follower_port = "/dev/tty.usbmodem575E0032081"

leader_arm = DynamixelMotorsBus(
    port=leader_port,
    motors={
        # name: (index, model)
        "shoulder_pan": (1, "xl330-m077"),
        "shoulder_lift": (2, "xl330-m077"),
        "elbow_flex": (3, "xl330-m077"),
        "wrist_flex": (4, "xl330-m077"),
        "wrist_roll": (5, "xl330-m077"),
        "gripper": (6, "xl330-m077"),
    },
)

follower_arm = DynamixelMotorsBus(
    port=follower_port,
    motors={
        # name: (index, model)
        "shoulder_pan": (1, "xl430-w250"),
        "shoulder_lift": (2, "xl430-w250"),
        "elbow_flex": (3, "xl330-m288"),
        "wrist_flex": (4, "xl330-m288"),
        "wrist_roll": (5, "xl330-m288"),
        "gripper": (6, "xl330-m288"),
    },
)
```

Also, update the ports of the following lines of yaml file for Koch robot [`lerobot/configs/robot/koch.yaml`](../lerobot/configs/robot/koch.yaml):
```yaml
[...]
leader_arms:
  main:
    _target_: lerobot.common.robot_devices.motors.dynamixel.DynamixelMotorsBus
    port: /dev/tty.usbmodem575E0031751  # <- Update
    motors:
      # name: (index, model)
      shoulder_pan: [1, "xl330-m077"]
      shoulder_lift: [2, "xl330-m077"]
      elbow_flex: [3, "xl330-m077"]
      wrist_flex: [4, "xl330-m077"]
      wrist_roll: [5, "xl330-m077"]
      gripper: [6, "xl330-m077"]
follower_arms:
  main:
    _target_: lerobot.common.robot_devices.motors.dynamixel.DynamixelMotorsBus
    port: /dev/tty.usbmodem575E0032081  # <- Update
    motors:
      # name: (index, model)
      shoulder_pan: [1, "xl430-w250"]
      shoulder_lift: [2, "xl430-w250"]
      elbow_flex: [3, "xl330-m288"]
      wrist_flex: [4, "xl330-m288"]
      wrist_roll: [5, "xl330-m288"]
      gripper: [6, "xl330-m288"]
[...]
```

This file is used to instantiate your robot in all our scripts. We will explain how this works later on.

**Configure and Connect**

Then, you will need to configure your motors to be able to properly communicate with them. During the first connection of the motors, [`DynamixelMotorsBus`](../lerobot/common/robot_devices/motors/dynamixel.py) automatically detects a mismatch between the present motor indices (all `1` by factory default) and your specified motor indices (e.g. `1,2,3,4,5,6`). This triggers the configuration procedure which requires to unplug the power cord and motors, and to sequentially plug each motor again, starting from the closest to the bus.

See the [video tutorial of the configuration procedure](https://youtu.be/U78QQ9wCdpY).

Run the following code in the same python session in your terminal to connect and configure the leader arm:
```python
leader_arm.connect()
```

Here is an example of connecting the leader arm for the first time:
```
Read failed due to communication error on port /dev/tty.usbmodem575E0032081 for group_key ID_shoulder_pan_shoulder_lift_elbow_flex_wrist_flex_wrist_roll_gripper: [TxRxResult] There is no status packet!

/!\ A configuration issue has been detected with your motors:
- Verify that all the cables are connected the proper way. Before making a modification, unplug the power cord to not damage the motors. Rewire correctly. Then plug the power again and relaunch the script.
- If it's the first time that you use these motors, press Enter to configure your motors...

Motor indices detected: {9600: [1]}

1. Unplug the power cord
2. Plug/unplug minimal number of cables to only have the first 1 motor(s) (['shoulder_pan']) connected.
3. Re-plug the power cord
Press Enter to continue...

*Follow the procedure*

Setting expected motor indices: [1, 2, 3, 4, 5, 6]
```

Now do the same for the follower arm:
```python
follower_arm.connect()
```

Congrats, now both arms are well configured and connected! You won't have to follow the configuration procedure ever again!

Note: If the configuration didn't work, you might need to update the firmware using [DynamixelWizzard2](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_wizard2). You might also need to manually configure the motors. Similarly, you will need to connect each motor seperately to the bus. You will need to set correct indices and set their baudrates to `1000000`. Take a look at this video for help: https://www.youtube.com/watch?v=JRRZW_l1V-U


**Read and Write**

Just to get familiar with how `DynamixelMotorsBus` communicates with the motors, let's try to read from them:
```python
leader_pos = leader_arm.read("Present_Position")
follower_pos = follower_arm.read("Present_Position")
print(leader_pos)
print(follower_pos)
>>> array([2054,  523, 3071, 1831, 3049, 2441], dtype=int32)
>>> array([2003, 1601,   56, 2152, 3101, 2283], dtype=int32)
```

Try to move the arms in various positions and see how if affects the values.

Now let's try to enable torque in the follower arm:
```python
from lerobot.common.robot_devices.motors.dynamixel import TorqueMode

follower_arm.write("Torque_Enable", TorqueMode.ENABLED.value)
```

The follower arm should be stuck in its current position. Don't try to manually move it while torque is enabled as it might damage the motors. Instead try to move it using the code:
```python
# Get the current position
position = follower_arm.read("Present_Position")

# Update first motor (shoulder_pan) position by +10 steps
position[0] += 10
follower_arm.write("Goal_Position", position)

# Update all motors position by -30 steps
position -= 30
follower_arm.write("Goal_Position", position)

# Update gripper by +30 steps
position[-1] += 30
follower_arm.write("Goal_Position", position[-1], "gripper")
```

When you are done, disable the torque by running:
```python
# Warning: hold your robot so that it doesn't fall
follower_arm.write("Torque_Enable", TorqueMode.DISABLED.value)
```

And disconnect the two arms:
```python
leader_arm.disconnect()
follower_arm.disconnect()
```

You can also unplug the power cord which will disable torque and disconnect.

### Teleoperate your Koch v1.1 with KochRobot

**Instantiate**

Before being able to teleoperate your robot, you will need to instantiate the [`KochRobot`](../lerobot/common/robot_devices/robots/koch.py) using the previously defined `leader_arm` and `follower_arm` as shown next.

For the Koch robot, we only have one leader, so as you will see next, we call it `"main"` and define `leader_arms={"main": leader_arm}`. We do the same for the follower arm. However for other robots (e.g. Aloha), we can use two pairs of leader and follower. In this case, we would define `leader_arms={"left": left_leader_arm, "right": right_leader_arm},`. Same thing for the follower arms.

We also need to provide a path to a calibration file `calibration_path=".cache/calibration/koch.pkl"`. More on this in the next section.

Run this code to instantiate your robot:
```python
from lerobot.common.robot_devices.robots.koch import KochRobot

robot = KochRobot(
    leader_arms={"main": leader_arm},
    follower_arms={"main": follower_arm},
    calibration_path=".cache/calibration/koch.pkl",
)
```

**Calibrate and Connect**

Then, you will need to calibrate your robot so that when the leader and follower arms are in the same physical position, they have the same position values read from [`DynamixelMotorsBus`](../lerobot/common/robot_devices/motors/dynamixel.py). An important benefit of calibration is that a neural network trained on data collected on your Koch robot will transfer to another Koch robot.

During the first connection of your robot, [`KochRobot`](../lerobot/common/robot_devices/robots/koch.py) detects that the calibration file is missing. This triggers the calibration procedure which requires you to move each arm in 3 different positions.

You will follow the procedure and move the follower to these positions:

<div style="display:flex; justify-content:center;">
  <div style="width:30%; margin:10px;">
    <img src="../media/koch/follower_zero.webp?raw=true" alt="Koch v1.1 follower arm zero position" title="Koch v1.1 follower arm zero position" style="width:100%;">
    <p style="text-align:center;">1. Zero position</p>
  </div>
  <div style="width:30%; margin:10px;">
    <img src="../media/koch/follower_rotated.webp?raw=true" alt="Koch v1.1 follower arm rotated position" title="Koch v1.1 follower arm rotated position" style="width:100%;">
    <p style="text-align:center;">2. Rotated position</p>
  </div>
  <div style="width:30%; margin:10px;">
    <img src="../media/koch/follower_rest.webp?raw=true" alt="Koch v1.1 follower arm rest position" title="Koch v1.1 follower arm rest position" style="width:100%;">
    <p style="text-align:center;">3. Rest position</p>
  </div>
</div>


Then you will continue the procedure and move the leader to these positions:

<div style="display:flex; justify-content:center;">
  <div style="width:30%; margin:10px;">
    <img src="../media/koch/leader_zero.webp?raw=true" alt="Koch v1.1 leader arm zero position" title="Koch v1.1 leader arm zero position" style="width:100%;">
    <p style="text-align:center;">1. Zero position</p>
  </div>
  <div style="width:30%; margin:10px;">
    <img src="../media/koch/leader_rotated.webp?raw=true" alt="Koch v1.1 leader arm rotated position" title="Koch v1.1 leader arm rotated position" style="width:100%;">
    <p style="text-align:center;">2. Rotated position</p>
  </div>
  <div style="width:30%; margin:10px;">
    <img src="../media/koch/leader_rest.webp?raw=true" alt="Koch v1.1 leader arm rest position" title="Koch v1.1 leader arm rest position" style="width:100%;">
    <p style="text-align:center;">3. Rest position</p>
  </div>
</div>

See the [video tutorial of the calibration procedure](https://youtu.be/8drnU9uRY24).

Importantly, you don't need to be super accurate. When moving the arm to what we defined as the zero position, you are not "setting" the zero position. Our calibration procedure just counts the number of full 360 degrees rotations that your motors achieved since their birth from the factory. After calibration, all koch arms worldwide will move to the same zero position when their owner command them to go to position zero.

Regarding the 90 degrees rotated position, we use it to determine the direction of rotation of the motors. Did the number of steps decreased or increased when moving 90 degrees? After calibration, all koch arms worldwide will move to the same rotated 90 degrees position when their owner command them so.

Finally, the rest position is used for safety, so that when the calibration is done, the follower and leader arms are roughly in the same position. As a result, at the start of teleoperation, the follower won't "jump" to match the leader position, risking to damage the motors.


Run this code to calibrate and connect your robot:
```python
robot.connect()
```

The output will look like:
```
Connecting main follower arm
Connecting main leader arm
Missing calibration file '.cache/calibration/koch.pkl'. Starting calibration procedure.

Running calibration of main follower...

Move arm to zero position
[...]
Move arm to rotated position
[...]
Move arm to rest position
[...]

Running calibration of main leader...

Move arm to zero position
[...]
Move arm to rotated position
[...]
Move arm to rest position
[...]

Calibration is done! Saving calibration file '.cache/calibration/koch.pkl'
```

Now we will see how to read the position of the leader and follower arms using `read` from [`DynamixelMotorsBus`](../lerobot/common/robot_devices/motors/dynamixel.py). If the calibration is done well, the position should be similar when both arms are in a similar position.

Run this code to get the positions in degree:
```python
leader_pos = robot.leader_arms["main"].read("Present_Position")
follower_pos = robot.follower_arms["main"].read("Present_Position")
print(leader_pos)
print(follower_pos)
>>> array([-0.43945312, 133.94531, 179.82422, -18.984375, -1.9335938, 34.541016], dtype=float32)
>>> array([-0.58723712, 131.72314, 174.98743, -16.872612, 0.786213, 35.271973], dtype=float32)
```

Importantly, we also converted the "step" position to degree. This is much easier to interpet and debug. In particular, the zero position used during calibration now corresponds to 0 degree for each motor. Also, the rotated position corresponds to 90 degree for each motor.

**Teleoperate**

Now you can easily teleoperate your robot by reading the positions from the leader arm and sending them as goal positions to the follower arm.

Run this code to teleoperate:
```python
import tqdm
# Teleoperate for 30 seconds
# Fastest communication is done at a frequency of ~200Hz
for _ in tqdm.tqdm(range(30*200)):
    leader_pos = robot.leader_arms["main"].read("Present_Position")
    robot.follower_arms["main"].write("Goal_Position", leader_pos)
```

You can also teleoperate by using `teleop_step` from [`KochRobot`](../lerobot/common/robot_devices/robots/koch.py).

Run this code to teleoperate:
```python
import tqdm
for _ in tqdm.tqdm(range(30*200)):
    robot.teleop_step()
```

Teleoperation is useful to record data. To this end, you can use `teleop_step` from [`KochRobot`](../lerobot/common/robot_devices/robots/koch.py) with `record_data=True`. It outputs the follower position as `"observation.state"` and the leader position as `"action"`. It also converts the numpy arrays into torch tensors, and concatenates the positions in the case of two leader and two follower arms like in Aloha.

Run this code several time to see how (slowly) moving the leader arm affects the observation and action:
```python
leader_pos = robot.leader_arms["main"].read("Present_Position")
follower_pos = robot.follower_arms["main"].read("Present_Position")
observation, action = robot.teleop_step(record_data=True)
print(follower_pos)
print(observation)
print(leader_pos)
print(action)
>>> array([7.8223, 131.1328, 165.5859, -23.4668, -0.9668, 32.4316], dtype=float32)
>>> {'observation.state': tensor([7.8223, 131.1328, 165.5859, -23.4668, -0.9668, 32.4316])}
>>> array([3.4277, 134.1211, 179.8242, -18.5449, -1.5820, 34.7168], dtype=float32)
>>> {'action': tensor([3.4277, 134.1211, 179.8242, -18.5449, -1.5820, 34.7168])}
```

Finally, `teleop_step` from [`KochRobot`](../lerobot/common/robot_devices/robots/koch.py) with `record_data=True` can also asynchrously record frames from several cameras and add them to the observation dictionnary as `"observation.images.CAMERA_NAME"`. More on this in the next section.

When you are done, disconnect your robot:
```python
robot.disconnect()
```

### Add your cameras with OpenCVCamera

**(Optional) Use your phone as camera on Linux**

If you are using a built in laptop camera, or webcam you may ignore these steps. However, if you would like to use your phone as a camera on Linux, you must first set up a virtual camera port.

1. Install `v4l2loopback-dkms`, which is required for creating virtual camera devices, using the following command:
```python
sudo apt-get install v4l2loopback-dkms
```
2. Download [DroidCam](https://droidcam.app) on your phone (available for both iOS and Android).
3. Install [OBS Studio](https://obsproject.com/). Follow the steps based on your operating system. For Linux, you can use [Flatpak](https://flatpak.org/):
```python
flatpak install flathub com.obsproject.Studio
```
4. Install the DroidCam OBS plugin. Follow the steps based on your operating system. For Linux:
```python
flatpak install flathub com.obsproject.Studio.Plugin.DroidCam
```
5. Open OBS Studio. For Linux:
```python
flatpak run com.obsproject.Studio
```
6. Add your phone as a source. Follow the instructions [here](https://droidcam.app/obs/usage). Be sure to set the resolution to `640x480`.
7. Go to `File>Settings>Video`. Change the `Base(Canvas) Resolution` and the `Output(Scaled) Resolution` to `640x480` by manually typing it in.
8. In OBS Studio, start the virtual camera. Follow the instructions [here](https://obsproject.com/kb/virtual-camera-guide).
9. Use `v4l2-ctl` to ensure the virtual camera is set up correctly, and check the output shows a `VirtualCam`, as in the example below.
```python
v4l2-ctl --list-devices

>>> VirtualCam (platform:v4l2loopback-000):
>>> /dev/video1
```
10. Use `v4l2-ctl` to check that your Virtual camera output resolution is `640x480` as shown below. Change `/dev/video1` to the port of your virtual camera from the output of `v4l2-ctl --list-devices`. Note: If the resolution is not correct you will have to delete the Virtual Camera port and try again as it cannot be changed.
```python
v4l2-ctl -d /dev/video1 --get-fmt-video

>>> Format Video Capture:
>>>	Width/Height      : 640/480
>>>	Pixel Format      : 'YUYV' (YUYV 4:2:2)
```
From here, you should be able to proceed with the rest of the tutorial.

**(Optional) Use your iPhone as a camera on MacOS**

For using your iPhone as a camera on MacOS, enable the Continuity Camera feature:
- Make sure your Mac has macOS 13 or later and your iPhone has iOS 16 or later.
- Sign in both devices with the same Apple ID.
- Connect with a USB cable for a wired connection or turn on Wi-Fi and Bluetooth on both devices.

For more info, see [Apple support](https://support.apple.com/en-gb/guide/mac-help/mchl77879b8a/mac).

Your iPhone should be detected using our script in the next section.

**Instantiate**

You can efficiently record frames from cameras with the [`OpenCVCamera`](../lerobot/common/robot_devices/cameras/opencv.py) class. It relies on [`opencv2`](https://docs.opencv.org) to communicate with the cameras. Most cameras are compatible. For more info, see [Video I/O with OpenCV Overview](https://docs.opencv.org/4.x/d0/da7/videoio_overview.html).

To instantiate an [`OpenCVCamera`](../lerobot/common/robot_devices/cameras/opencv.py), you need a camera index (e.g. `OpenCVCamera(camera_index=0)`). When you only have one camera like a webcam of a laptop, the camera index is usually `0` but it might differ, and the camera index might change if you reboot your computer or re-plug your camera. This behavior depends on your operating system.

To find the camera indices of your cameras, you can run our utility script that will save a few frames for each camera:
```bash
python lerobot/common/robot_devices/cameras/opencv.py \
    --images-dir outputs/images_from_opencv_cameras
```

The output looks like this for two cameras:
```
Mac or Windows detected. Finding available camera indices through scanning all indices from 0 to 60
[...]
Camera found at index 0
Camera found at index 1
[...]
Connecting cameras
OpenCVCamera(0, fps=30.0, width=1920.0, height=1080.0, color_mode=rgb)
OpenCVCamera(1, fps=24.0, width=1920.0, height=1080.0, color_mode=rgb)
Saving images to outputs/images_from_opencv_cameras
Frame: 0000	Latency (ms): 39.52
[...]
Frame: 0046	Latency (ms): 40.07
Images have been saved to outputs/images_from_opencv_cameras
```

Then, look at the saved images in `outputs/images_from_opencv_cameras` to know which camera index (e.g. `0` for `camera_00` or `1` for `camera_01`) is associated to which physical camera:
```
camera_00_frame_000000.png
[...]
camera_00_frame_000047.png
camera_01_frame_000000.png
[...]
camera_01_frame_000047.png
```

Note: We save a few frames since some cameras need a few seconds to warmup. The first frame can be totally black or green.

Finally, run this code to instantiate your camera:
```python
from lerobot.common.robot_devices.cameras.opencv import OpenCVCamera

camera = OpenCVCamera(camera_index=0)
camera.connect()
color_image = camera.read()
print(color_image.shape)
print(color_image.dtype)
>>> (1080, 1920, 3)
>>> uint8
```

Note that default fps, width, height and color_mode of the given camera are used. They may differ for different cameras. You can specify them during instantiation (e.g. `OpenCVCamera(camera_index=0, fps=30, width=640, height=480`).

When done using the camera, disconnect it:
```python
camera.disconnect()
```

**Instantiate your robot with cameras**

You can also instantiate your robot with your cameras!

Adjust this code with the names and configurations of your cameras and run it:
```python
robot = KochRobot(
    leader_arms={"main": leader_arm},
    follower_arms={"main": follower_arm},
    calibration_path=".cache/calibration/koch.pkl",
    cameras={
        "laptop": OpenCVCamera(0, fps=30, width=640, height=480),
        "phone": OpenCVCamera(1, fps=30, width=640, height=480),
    },
)
robot.connect()
```

As a result, `teleop_step` with `record_data=True` will return a frame for each camera following the pytorch convention: channel first with pixels in range [0,1]

Adjust this code with the names of your cameras and run it:
```python
observation, action = robot.teleop_step(record_data=True)
print(observation["observation.images.laptop"].shape)
print(observation["observation.images.phone"].shape)
print(observation["observation.images.laptop"].min().item())
print(observation["observation.images.laptop"].max().item())
>>> torch.Size([3, 480, 640])
>>> torch.Size([3, 480, 640])
>>> 0.13137255012989044
>>> 0.98237823197230911
```

Also, update the flollowing lines of the yaml file for Koch robot [`lerobot/configs/robot/koch.yaml`](../lerobot/configs/robot/koch.yaml) with the names and configurations of your cameras:
```yaml
[...]
cameras:
  laptop:
    _target_: lerobot.common.robot_devices.cameras.opencv.OpenCVCamera
    camera_index: 0
    fps: 30
    width: 640
    height: 480
  phone:
    _target_: lerobot.common.robot_devices.cameras.opencv.OpenCVCamera
    camera_index: 1
    fps: 30
    width: 640
    height: 480
```

This file is used to instantiate your robot in all our scripts. We will explain how this works in the next section.

### Use `koch.yaml` and our `teleoperate` function

Instead of manually running the python code in a terminal window, you can use [`lerobot/scripts/control_robot.py`](../lerobot/scripts/control_robot.py) to instantiate your robot by providing the path to the robot yaml file (e.g. [`lerobot/configs/robot/koch.yaml`](../lerobot/configs/robot/koch.yaml) and control your robot with various modes as explained next.

Try running this code to teleoperate your robot (if you dont have a camera, keep reading):
```bash
python lerobot/scripts/control_robot.py teleoperate \
  --robot-path lerobot/configs/robot/koch.yaml
```

You will see a lot of lines appearing like this one:
```
INFO 2024-08-10 11:15:03 ol_robot.py:209 dt: 5.12 (195.1hz) dtRlead: 4.93 (203.0hz) dtRfoll: 0.19 (5239.0hz)
```

It contains
- `2024-08-10 11:15:03` which is the date and time of the call to the print function.
- `ol_robot.py:209` which is the end of the file name and the line number where the print function is called  (`lerobot/scripts/control_robot.py` line `209`).
- `dt: 5.12 (195.1hz)` which is the "delta time" or the number of milliseconds spent between the previous call to `robot.teleop_step()` and the current one, associated with the frequency (5.12 ms equals 195.1 Hz) ; note that you can control the maximum frequency by adding fps as argument such as `--fps 30`.
- `dtRlead: 4.93 (203.0hz)` which is the number of milliseconds it took to read the position of the leader arm using `leader_arm.read("Present_Position")`.
- `dtWfoll: 0.22 (4446.9hz)` which is the number of milliseconds it took to set a new goal position for the follower arm using `follower_arm.write("Goal_position", leader_pos)` ; note that writing is done asynchronously so it takes less time than reading.

Note: you can override any entry in the yaml file using `--robot-overrides` and the [hydra.cc](https://hydra.cc/docs/advanced/override_grammar/basic) syntax. If needed, you can override the ports like this:
```bash
python lerobot/scripts/control_robot.py teleoperate \
  --robot-path lerobot/configs/robot/koch.yaml \
  --robot-overrides \
    leader_arms.main.port=/dev/tty.usbmodem575E0031751 \
    follower_arms.main.port=/dev/tty.usbmodem575E0032081
```

Importantly: If you don't have any camera, you can remove them dynamically with this [hydra.cc](https://hydra.cc/docs/advanced/override_grammar/basic) syntax `'~cameras'`:
```bash
python lerobot/scripts/control_robot.py teleoperate \
  --robot-path lerobot/configs/robot/koch.yaml \
  --robot-overrides \
    '~cameras'
```

We advise to create a new yaml file when the command becomes too long.

## 3. Record your Dataset and Visualize it

Using what you've learned previously, you can now easily record a dataset of states and actions for one episode. You can use `busy_wait` to control the speed of teleoperation and record at a fixed `fps` (frame per seconds).

Try this code to record 30 seconds at 60 fps:
```python
import time
from lerobot.scripts.control_robot import busy_wait

record_time_s = 30
fps = 60

states = []
actions = []
for _ in range(record_time_s * fps):
    start_time = time.perf_counter()
    observation, action = robot.teleop_step(record_data=True)

    states.append(observation["observation.state"])
    actions.append(action["action"])

    dt_s = time.perf_counter() - start_time
    busy_wait(1 / fps - dt_s)

# Note that observation and action are available in RAM, but
# you could potentially store them on disk with pickle/hdf5 or
# our optimized format `LeRobotDataset`. More on this next.
```

Importantly, many utilities are still missing. For instance, if you have cameras, you will need to save the images on disk to not go out of RAM, and to do so in threads to not slow down communication with your robot. Also, you will need to store your data in a format optimized for training and web sharing like [`LeRobotDataset`](../lerobot/common/datasets/lerobot_dataset.py). More on this in the next section.

### Use `koch.yaml` and the `record` function

You can use the `record` function from [`lerobot/scripts/control_robot.py`](../lerobot/scripts/control_robot.py) to achieve efficient data recording. It encompasses many recording utilities:
1. Frames from cameras are saved on disk in threads, and encoded into videos at the end of recording.
2. Video streams from cameras are displayed in window so that you can verify them.
3. Data is stored with [`LeRobotDataset`](../lerobot/common/datasets/lerobot_dataset.py) format which is pushed to your Hugging Face page (unless `--push-to-hub 0` is provided).
4. Checkpoints are done during recording, so if any issue occurs, you can resume recording by re-running the same command again. You can also use `--force-override 1` to start recording from scratch.
5. Set the flow of data recording using command line arguments:
  - `--warmup-time-s` defines the number of seconds before starting data collection. It allows the robot devices to warmup and synchronize (10 seconds by default).
  - `--episode-time-s` defines the number of seconds for data recording for each episode (60 seconds by default).
  - `--reset-time-s` defines the number of seconds for resetting the environment after each episode (60 seconds by default).
  - `--num-episodes` defines the number of episodes to record (50 by default).
6. Control the flow during data recording using keyboard keys:
  - Press right arrow `->` at any time during episode recording to early stop and go to resetting. Same during resetting, to early stop and to go to the next episode recording.
  - Press left arrow `<-` at any time during episode recording or resetting to early stop, cancel the current episode, and re-record it.
  - Press escape `ESC` at any time during episode recording to end the session early and go straight to video encoding and dataset uploading.
7. Similarly to `teleoperate`, you can also use `--robot-path` and `--robot-overrides` to specify your robots.

Before trying `record`, if you want to push your dataset to the hub, make sure you've logged in using a write-access token, which can be generated from the [Hugging Face settings](https://huggingface.co/settings/tokens):
```bash
huggingface-cli login --token ${HUGGINGFACE_TOKEN} --add-to-git-credential
```
Also, store your Hugging Face repositery name in a variable (e.g. `cadene` or `lerobot`). For instance, run this to use your Hugging Face user name as repositery:
```bash
HF_USER=$(huggingface-cli whoami | head -n 1)
echo $HF_USER
```
If you don't want to push to hub, use `--push-to-hub 0`.

Now run this to record 5 episodes:
```bash
python lerobot/scripts/control_robot.py record \
  --robot-path lerobot/configs/robot/koch.yaml \
  --fps 30 \
  --root data \
  --repo-id ${HF_USER}/koch_test \
  --warmup-time-s 5 \
  --episode-time-s 30 \
  --reset-time-s 30 \
  --num-episodes 2
```

Note: Remember to add `--robot-overrides '~cameras'` if you don't have any cameras and you still use the default `koch.yaml` configuration.

You will see a lot of lines appearing like this one:
```
INFO 2024-08-10 15:02:58 ol_robot.py:219 dt:33.34 (30.0hz) dtRlead: 5.06 (197.5hz) dtWfoll: 0.25 (3963.7hz) dtRfoll: 6.22 (160.7hz) dtRlaptop: 32.57 (30.7hz) dtRphone: 33.84 (29.5hz)
```
It contains:
- `2024-08-10 15:02:58` which is the date and time of the call to the print function,
- `ol_robot.py:219` which is the end of the file name and the line number where the print function is called  (`lerobot/scripts/control_robot.py` line `219`).
- `dt:33.34 (30.0hz)` which is the "delta time" or the number of milliseconds spent between the previous call to `robot.teleop_step(record_data=True)` and the current one, associated with the frequency (33.34 ms equals 30.0 Hz) ; note that we use `--fps 30` so we expect 30.0 Hz ; when a step takes more time, the line appears in yellow.
- `dtRlead: 5.06 (197.5hz)` which is the delta time of reading the present position of the leader arm.
- `dtWfoll: 0.25 (3963.7hz)` which is the delta time of writing the goal position on the follower arm ; writing is asynchronous so it takes less time than reading.
- `dtRfoll: 6.22 (160.7hz)` which is the delta time of reading the present position on the follower arm.
- `dtRlaptop:32.57 (30.7hz) ` which is the delta time of capturing an image from the laptop camera in the thread running asynchrously.
- `dtRphone:33.84 (29.5hz)` which is the delta time of capturing an image from the phone camera in the thread running asynchrously.

Troubleshooting:
- On Linux, if you encounter a hanging issue when using cameras, uninstall opencv and re-install it with conda:
```bash
pip uninstall opencv-python
conda install -c conda-forge opencv=4.10.0
```
- On Linux, if you encounter any issue during video encoding with `ffmpeg: unknown encoder libsvtav1`, you can:
  - install with conda-forge by running `conda install -c conda-forge ffmpeg` (it should be compiled with `libsvtav1`),
  - or, install [Homebrew](https://brew.sh) and run `brew install ffmpeg` (it should be compiled with `libsvtav1`),
  - or, install [ffmpeg build dependencies](https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu#GettheDependencies) and [compile ffmpeg from source with libsvtav1](https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu#libsvtav1),
  - and, make sure you use the corresponding ffmpeg binary to your install with `which ffmpeg`.

At the end of data recording, your dataset will be uploaded on your Hugging Face page (e.g. https://huggingface.co/datasets/cadene/koch_test) that you can obtain by running:
```bash
echo https://huggingface.co/datasets/${HF_USER}/koch_test
```

### Advices for recording dataset

Now that you are used to data recording, you can record a bigger dataset for training. A good hello world task consists in grasping an object at various locations and placing it in a bin. We recommend to record a minimum of 50 episodes with 10 episodes per location, to not move the cameras and to grasp with a consistent behavior.

In the next sections, you will train your neural network. Once it can grasp pretty well, you can introduce slightly more variance during data collection such as more grasp locations, various grasping behaviors, various positions for the cameras, etc.

Don't be greedy or it won't work!

In the coming months, we plan to add a fundational model for robotics. We expect that finetuning it will lead to stronger generalization abilities so you won't have to be so careful about adding variations in your data collection.

### Visualize all episodes

You can visualize your dataset by running:
```bash
python lerobot/scripts/visualize_dataset_html.py \
  --root data \
  --repo-id ${HF_USER}/koch_test
```

This will launch a local web server that looks like this:
<div style="text-align:center;">
  <img src="../media/tutorial/visualize_dataset_html.webp?raw=true" alt="Koch v1.1 leader and follower arms" title="Koch v1.1 leader and follower arms" width="100%">
</div>

### Replay episode on your robot with the `replay` function

Another cool function of [`lerobot/scripts/control_robot.py`](../lerobot/scripts/control_robot.py) is `replay` which allows to replay on your robot any episode that you've recorded or from any dataset out there. It's a way to test repeatability of your robot and transferability across robots of the same type.

Run this to replay the first episode of the dataset you've just recorded:
```bash
python lerobot/scripts/control_robot.py replay \
  --robot-path lerobot/configs/robot/koch.yaml \
  --fps 30 \
  --root data \
  --repo-id ${HF_USER}/koch_test \
  --episode 0
```

Your robot should reproduce very similar movements as what you recorded. For instance, see this video where we use `replay` on a Aloha robot from [Trossen Robotics](https://www.trossenrobotics.com): https://x.com/RemiCadene/status/1793654950905680090

## 4. Train a policy on your data

### Use our `train` script

Then, you can train a policy to control your robot by running [`python lerobot/scripts/train.py`](../lerobot/scripts/train.py) script. A few arguments are required. We give an example command later on.

Firstly, provide your dataset as argument with `dataset_repo_id=${HF_USER}/koch_test`.

Secondly, provide a policy with `policy=act_koch_real`. This loads configurations from [`lerobot/configs/policy/act_koch_real.yaml`](../lerobot/configs/policy/act_koch_real.yaml). Importantly, this policy uses 2 cameras as input `laptop` and `phone`. If your dataset has different cameras, update the yaml file to account for it in the following parts:
```yaml
...
override_dataset_stats:
  observation.images.laptop:
    # stats from imagenet, since we use a pretrained vision model
    mean: [[[0.485]], [[0.456]], [[0.406]]]  # (c,1,1)
    std: [[[0.229]], [[0.224]], [[0.225]]]  # (c,1,1)
  observation.images.phone:
    # stats from imagenet, since we use a pretrained vision model
    mean: [[[0.485]], [[0.456]], [[0.406]]]  # (c,1,1)
    std: [[[0.229]], [[0.224]], [[0.225]]]  # (c,1,1)
...
  input_shapes:
    observation.images.laptop: [3, 480, 640]
    observation.images.phone: [3, 480, 640]
...
  input_normalization_modes:
    observation.images.laptop: mean_std
    observation.images.phone: mean_std
...
```

Thirdly, provide an environment as argument with `env=koch_real`. This loads configurations from [`lerobot/configs/env/koch_real.yaml`](../lerobot/configs/env/koch_real.yaml). It looks like
```yaml
fps: 30
env:
  name: real_world
  task: null
  state_dim: 6
  action_dim: 6
  fps: ${fps}
```
It should match your dataset (e.g. `fps: 30`) and your robot (e.g. `state_dim: 6` and `action_dim: 6`). We are still working on simplifying this in future versions of `lerobot`.

Optionnaly, you can use [Weights and Biases](https://docs.wandb.ai/quickstart) for visualizing training plots with `wandb.enable=true` as agument. Make sure you are logged in by running `wandb login`.

Finally, add `DATA_DIR=data` before `python lerobot/scripts/train.py` to access your dataset stored in your local `data` directory. If you dont provide `DATA_DIR`, your dataset will be downloaded from Hugging Face hub to your cache folder `$HOME/.cache/hugginface`. In future versions of `lerobot`, both directories will be in sync.

Now, start training:
```bash
DATA_DIR=data python lerobot/scripts/train.py \
  dataset_repo_id=${HF_USER}/koch_test \
  policy=act_koch_real \
  env=koch_real \
  hydra.run.dir=outputs/train/act_koch_test \
  hydra.job.name=act_koch_test \
  wandb.enable=true
```

For more information on the `train` script see the previous tutorial: [`examples/4_train_policy_with_script.md`](../examples/4_train_policy_with_script.md)

## Upload policy checkpoints to the hub

Once training is done, upload the latest checkpoint with:
```bash
huggingface-cli upload ${HF_USER}/act_koch_test \
  outputs/train/act_koch_test/checkpoints/last/pretrained_model
```

You can also upload intermediate checkpoints with:
```bash
CKPT=010000
huggingface-cli upload ${HF_USER}/act_koch_test_${CKPT} \
  outputs/train/act_koch_test/checkpoints/${CKPT}/pretrained_model
```

## 5. Evaluate your policy

Now that you have a policy checkpoint, you can easily control your robot with it using:
- `observation = robot.capture_observation()`
- `action = policy.select_action(observation)`
- `robot.send_action(action)`

Try this code for running inference for 60 seconds at 30 fps:
```python
from lerobot.common.policies.act.modeling_act import ActPolicy

inference_time_s = 60
fps = 30

ckpt_path = "outputs/train/act_koch_test/checkpoints/last/pretrained_model"
policy = ActPolicy.from_pretrained(ckpt_path)

for _ in range(inference_time_s * fps):
    start_time = time.perf_counter()
    observation = robot.capture_observation()

    # Convert to pytorch format: channel first and float32 in [0,1]
    # with batch dimension
    for name in observation:
        if "image" in name:
            observation[name] = observation[name].type(torch.float32) / 255
            observation[name] = observation[name].permute(2, 0, 1).contiguous()
        observation[name] = observation[name].unsqueeze(0)
        observation[name] = observation[name].cuda()

    action = policy.select_action(observation)
    robot.send_action(action)

    # remove batch dimension
    action = action.squeeze(0)
    action = action.to("cpu")

    dt_s = time.perf_counter() - start_time
    busy_wait(1 / fps - dt_s)
```

### Use `koch.yaml` and our `record` function

Ideally, when controlling your robot with your neural network, you would want to record evaluation episodes and to be able to visualize them later on, or even train on them like in Reinforcement Learning. This pretty much corresponds to recording a new dataset but with a neural network providing the actions instead of teleoperation.

To this end, you can use the `record` function from [`lerobot/scripts/control_robot.py`](../lerobot/scripts/control_robot.py) but with a policy checkpoint as input. Just copy the same command as previously used to record your training dataset and change two things:
1. Add a path to your policy checkpoint with `-p` (e.g. `-p outputs/train/eval_koch_test/checkpoints/last/pretrained_model`) or a model repository (e.g. `-p ${HF_USER}/act_koch_test`).
2. Change the dataset name to reflect you are running inference (e.g. `--repo-id ${HF_USER}/eval_koch_test`).

Now run this to record 5 evaluation episodes.
```bash
python lerobot/scripts/control_robot.py record \
  --robot-path lerobot/configs/robot/koch.yaml \
  --fps 30 \
  --root data \
  --repo-id ${HF_USER}/eval_koch_test \
  --warmup-time-s 5 \
  --episode-time-s 30 \
  --reset-time-s 30 \
  --num-episodes 5 \
  -p outputs/train/act_koch_test/checkpoints/last/pretrained_model
```

### Visualize evaluation afterwards

You can then visualize your evaluation dataset by running the same command as before but with the new dataset as argument:
```bash
python lerobot/scripts/visualize_dataset.py \
  --root data \
  --repo-id ${HF_USER}/eval_koch_test
```


## Next step

Join our [Discord](https://discord.com/invite/s3KuuzsPFb) to coordinate on community-driven data collection and training foundational models for robotics!