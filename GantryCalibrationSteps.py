# Include all necessary assemblies from the C# side
# DO NOT REMOVE THESE REFERECES
import clr
clr.AddReference('System.Core')
import System
clr.ImportExtensions(System.Linq)
from System import IO
from System import Action
from System import Func
from System import DateTime
from System import Array
from System import String
from System import ValueTuple
from System import Math
from System.Diagnostics import Stopwatch
from System.Collections.Generic import List
clr.AddReferenceToFile('HAL.dll')
from HAL import Motion
from HAL import HardwareFactory
from HAL import HardwareInitializeState
from HAL import Vision
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoAligner.exe')
from CiscoAligner import PickAndPlace
from CiscoAligner import Station
from CiscoAligner import Alignments
from CiscoAligner import CoordinateCalibration


#-------------------------------------------------------------------------------
# Initialize
# Initialize station for calibration
#-------------------------------------------------------------------------------
def Initialize(StepName, SequenceObj, TestMetrics, TestResults):

    TestResults.ClearAllTestResult()

    Hexapod = HardwareFactory.Instance.GetHardwareByName('Hexapod')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')
    IO = HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl')

    # move the epoxy tip up first
    if not IO.SetOutputValue('EpoxyToolBackPressStates', 'Off') or not IO.SetOutputValue('EpoxyToolStates', 'Up'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to retract epoxy tool.')
        return 0

    # go to start position and ask for the vision fiducial to be installed
    Hexapod.GetHardwareStateTree().ActivateState('Load')
    Stages.GetHardwareStateTree().ActivateState('CameraCalibration')

    Utility.ShowProcessTextOnMainUI('Remove board on fixture. Move probe card to its farthest and lowest possible position and install calibration reticle.')
    # ask for the vision fiducial
    if not LogHelper.AskContinue('Follow instruction on main UI. Click OK when done, No to abort.'):
        Utility.ShowProcessTextOnMainUI()
        return 0

    Stages.GetHardwareStateTree().ActivateState('CameraCalibration')
    # calibration commited, must finish
    CoordinateCalibration.Instance.IsStationCalibrated = False
    Utility.ShowProcessTextOnMainUI()

    return 1

#-------------------------------------------------------------------------------
# FixtureCameras
# Calibrate cameras
#-------------------------------------------------------------------------------
def FixtureCameras(StepName, SequenceObj, TestMetrics, TestResults):

    if not CoordinateCalibration.Instance.FixtureCamerasToTargetStaticUpCamera():
        return 0
    else:
        Utility.ShowProcessTextOnMainUI()
        if not LogHelper.AskContinue('Please remove calibration reticle. Click OK when done, No to abort.'):
            return 0
        else:
            return 1

#-------------------------------------------------------------------------------
# ApplyOffsetCorrection
# Apply offset correction to camera calibration
#-------------------------------------------------------------------------------
def CorrectCalibrationError(StepName, SequenceObj, TestMetrics, TestResults):

    if not CoordinateCalibration.Instance.CorrectCalibrationError():
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# CalibrateContactSensor
# Calibrate contact sensor
#-------------------------------------------------------------------------------
def CalibrateContactSensor(StepName, SequenceObj, TestMetrics, TestResults):

    if not CoordinateCalibration.Instance.CalibrateContactSensor():
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# CalibrateGripper
# CAlibrate gripper finger location
#-------------------------------------------------------------------------------
def CalibrateGripper(StepName, SequenceObj, TestMetrics, TestResults):

    if not CoordinateCalibration.Instance.CalibrateGripper():
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# CalibrateEpoxyTool
# Calibrate epoxy tool tip position
#-------------------------------------------------------------------------------
def CalibrateEpoxyTool(StepName, SequenceObj, TestMetrics, TestResults):

    if not CoordinateCalibration.Instance.CalibrateEpoxyTool():
        return 0
    else:
        return 1


#-------------------------------------------------------------------------------
# Finalize
# Finalize process such as saving data
#-------------------------------------------------------------------------------
def Finalize(StepName, SequenceObj, TestMetrics, TestResults):

    if not CoordinateCalibration.Instance.Finalize():
        return 0
    else:
        return 1


#-------------------------------------------------------------------------------
# Code below not used...
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# median
# Helper function to calculate median of a list
#-------------------------------------------------------------------------------
def median(lst):
    
    even = (0 if len(lst) % 2 else 1) + 1
    half = (len(lst) - 1) / 2
    return sum(sorted(lst)[half:half + even]) / float(even)

#-------------------------------------------------------------------------------
# CalibrateDownCamera
# Calibrate the down camera to stage positions
#-------------------------------------------------------------------------------
def CalibrateCameras(StepName, SequenceObj, TestMetrics, TestResults):
    
    # camera shift distance for calibration
    CAMERA_CAL_TARGET_SHIFT = 2.0 

    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    UpCamera = HardwareFactory.Instance.GetHardwareByName('UpCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Hexapod = HardwareFactory.Instance.GetHardwareByName('Hexapod')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')

    # Generate the calibration points
    cornerpoints = [(0,0),(-CAMERA_CAL_TARGET_SHIFT / 2, 0),(0, -CAMERA_CAL_TARGET_SHIFT / 2),\
        (CAMERA_CAL_TARGET_SHIFT / 2, 0),(CAMERA_CAL_TARGET_SHIFT / 2, 0),\
        (0, CAMERA_CAL_TARGET_SHIFT / 2),(0, CAMERA_CAL_TARGET_SHIFT / 2),\
        (-CAMERA_CAL_TARGET_SHIFT / 2, 0),(-CAMERA_CAL_TARGET_SHIFT / 2, 0)]      

    # Create the calibration point collection
    downCameraPoints = List[Vision.CalibratePointPair]()
    upCameraPoints = List[Vision.CalibratePointPair]()
    DownCamAngles = []
    UpCamAngles = []

    # move to camera calibration preset position
    if not Stages.GetHardwareStateTree().ActivateState('CameraCalibration'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to down camera start calibration position.')
        return 0

    if SequenceObj.Halt:
        return 0

    # turn off all lights and then set to recipe level
    DownCamera.LightControl1.Item2.SetIlluminationOff()
    UpCamera.LightControl1.Item2.SetIlluminationOff()
        
    # turn on the cameras
    DownCamera.Live(True)
    UpCamera.Live(True)

    # start the calibration routine
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "Calibrating cameras...")

    # Get recipe parameters
    downcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamCalExposure').DataItem
    downvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamCalVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem
    # set exposure and lighting
    DownCamera.SetExposureTime(downcamexposure)
    DownCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('CameraCalibration')
    
    # remember where we started
    calibrateaxes = Array[String]([ 'X', 'Y' ])
    origin = Stages.GetAxesPositions(calibrateaxes)
    camangles = []

    # Iterate through the points and acquire calibration points
    for p in cornerpoints:
        if not Stages.MoveAxesRelative(calibrateaxes, Array[float]([p[0], p[1]]), Motion.AxisMotionSpeeds.Normal, True):
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to calibration position.')
            return 0
        # Wait for stage to settle
        Utility.DelayMS(500)

        # variable to save results
        camsnapx = []
        camsnapy = []
        camsnapangle = []

        # start acqusition
        for i in range(snaps):
            DownCamera.Snap()
            res = MachineVision.RunVisionTool(downvision)
            if res['Result'] != 'Success':
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
                return 0
            # save result
            camsnapx.append(res['X'])
            camsnapy.append(res['Y'])
            camsnapangle.append(res['Angle'])

        # Done repeat snaps, find the median for each value
        medianx = median(camsnapx)
        mediany = median(camsnapy)
        camangles.append(median(camsnapangle))

        # Add to point collection
        downCameraPoints.Add( Vision.CalibratePointPair(medianx, mediany, Stages.GetAxisPosition('X'), Stages.GetAxisPosition('Y')))

    # Down camera loop done, save angle information and reset hardware
    DownCamAngles.append(Utility.RadianToDegree(sum(camangles)/len(camangles)))
    DownCamera.LightControl1.Item2.SetIlluminationOff()
    DownCamera.Live(True)

    # Start the up camera loop
    # Get recipe parameters
    upcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamCalExposure').DataItem
    upvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamCalVisionTool').DataItem
    # set exposure and lighting
    UpCamera.SetExposureTime(upcamexposure)
    UpCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('CameraCalibration')
    
    # Back to starting position
    if not Stages.MoveAxesAbsolute(calibrateaxes, origin, Motion.AxisMotionSpeeds.Normal, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to up camera calibration start position.')
        return 0

    camangles = []
    xstart = Hexapod.GetAxisPosition("X")
    # up looking is a bit more complicated since moving Newport stage has no effect on the fiducial
    # we will move the hexapod X and use the distance to offset the Newport position reading, in effect,
    # fake the Newport position as if though it moves the fiducial.
    # Iterate through the points and acquire calibration points
    for p in cornerpoints:
        if not Hexapod.MoveAxesRelative(calibrateaxes, Array[float]([p[0], p[1]]), Motion.AxisMotionSpeeds.Normal, True):
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to calibration position.')
            return 0
        # Wait for stage to settle
        Utility.DelayMS(500)

        # variable to save results
        camsnapx = []
        camsnapy = []
        camsnapangle = []

        # start acqusition
        for i in range(snaps):
            UpCamera.Snap()
            res = MachineVision.RunVisionTool(upvision)
            if res['Result'] != 'Success':
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
                return 0
            # save result
            camsnapx.append(res['X'])
            camsnapy.append(res['Y'])
            camsnapangle.append(res['Angle'])

        # Done repeat snaps, find the median for each value
        medianx = median(camsnapx)
        mediany = median(camsnapy)
        camangles.append(median(camsnapangle))

        # Add to point collection
        upCameraPoints.Add( Vision.CalibratePointPair(medianx, mediany, Stages.GetAxisPosition('X') + (Hexapod.GetAxisPosition('X') - xstart), Stages.GetAxisPosition('Y')))

    # Down camera loop done, save angle information
    UpCamAngles.append(Utility.RadianToDegree(sum(camangles)/len(camangles)))
    UpCamera.Live(True)
    
    # done camera acquisition, reset hardware
    DownCamera.LightControl1.Item2.SetIlluminationOff()
    UpCamera.LightControl1.Item2.SetIlluminationOff()
    Hexapod.GetHardwareStateTree().ActivateState('Load')
    Stages.GetHardwareStateTree().ActivateState('CameraCalibration')

    if not LogHelper.AskContinue('Please remove calibration reticle. Click OK when done, No to abort.'):
        Utility.ShowProcessTextOnMainUI()
        return 0

    # Generate the transforms and save
    MachineVision.AddTransform('DownCameraTransform', downCameraPoints)
    MachineVision.AddTransform('UpCameraTransform', upCameraPoints)
    CoordinateCalibration.Instance.ReferenceValues['CamerasAngleOffsetDegrees'] = (sum(DownCamAngles)/len(DownCamAngles)) - (sum(UpCamAngles)/len(UpCamAngles))

    width = clr.Reference[System.Int32]()
    height = clr.Reference[System.Int32]()
    # establish and save the camera vectors
    # get the down cam center positions
    DownCamera.GetImageSize(width, height)
    # find the center position in real coordinate
    dcCalCenter = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](width.Value / 2, height.Value / 2))
    if dcCalCenter == None:
        return 0

    # get the up cam center position
    UpCamera.GetImageSize(width, height)
    # find the center position in real coordinate
    ucCalCenter = MachineVision.ApplyTransform('UpCameraTransform', ValueTuple[float,float](width.Value / 2, height.Value / 2))
    if ucCalCenter == None:
        return 0

    # memorize our center locations and vectors
    CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'] = dcCalCenter
    CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'] = ucCalCenter

    # create the vectors
    # apply the error correction here
    correctionxy = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamToDownCamCalErrorCorrection').DataItem.Split(',').Select(lambda x: float(x)).ToArray()
    CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraNoCorrectionVector'] = Vector3(dcCalCenter.Item1 - ucCalCenter.Item1, dcCalCenter.Item2 - ucCalCenter.Item2, 0)
    CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraVector'] = Vector3(-ucCalCenter.Item1 + dcCalCenter.Item1 + correctionxy[0], -ucCalCenter.Item2 + dcCalCenter.Item2 + correctionxy[1], 0)
    
    return 1



#-------------------------------------------------------------------------------
# LocateGripper
# Locate position of gripper
#-------------------------------------------------------------------------------
def LocateGripper(StepName, SequenceObj, TestMetrics, TestResults):

    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    UpCamera = HardwareFactory.Instance.GetHardwareByName('UpCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')
    IO = HardwareFactory.Instance.GetHardwareByName('IOControl')
    HeightSensor = HardwareFactory.Instance.GetHardwareByName('HeightSensor')

    upcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamGripperExposure').DataItem
    upvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamGripperVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem
    GripperZMeasureStartHeight = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'GripperZMeasureStartHeight').DataItem
    zlim = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'GripperMeasureToolHeightZLimit').DataItem

    # move to the up looking gripper inspect position
    if not Stages.GetHardwareStateTree().ActivateState('UpCameraGripper'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move to up camera gripper position.")
        return 0

    # set exposure and lighting
    DownCamera.LightControl1.Item2.SetIlluminationOff()
    UpCamera.SetExposureTime(upcamexposure)
    UpCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('UpCameraGripper')

    # create the results collection
    camsnapx = []
    camsnapy = []

    # start acqusition
    for i in range(snaps):
        UpCamera.Snap()
        res = MachineVision.RunVisionTool(upvision)
        if res['Result'] != 'Success':
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the gripper finger.')
            return 0
        # save result
        camsnapx.append(res['X'])
        camsnapy.append(res['Y'])

    # found, transform the coordinate
    calp = MachineVision.ApplyTransform('UpCameraTransform', ValueTuple[float,float](median(camsnapx), median(camsnapy)))
    if calp == None:
        return 0

    # turn on the cameras
    DownCamera.Live(True)
    UpCamera.Live(True)

    # Generate the position vector
    CoordinateCalibration.Instance.TargetVectors['GripperToDownCameraNoCorrectionVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraNoCorrectionVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    CoordinateCalibration.Instance.TargetVectors['GripperToDownCameraVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    UpCamera.LightControl1.Item2.SetIlluminationOff()

    return 1

#-------------------------------------------------------------------------------
# LocateEpoxyTip
# Locate position of epoxy tip
#-------------------------------------------------------------------------------
def LocateEpoxyTip(StepName, SequenceObj, TestMetrics, TestResults):

    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    UpCamera = HardwareFactory.Instance.GetHardwareByName('UpCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')
    HeightSensor = HardwareFactory.Instance.GetHardwareByName('HeightSensor')
    IO = HardwareFactory.Instance.GetHardwareByName('IOControl')
    MIO = HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl')

    upcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamEpoxyTipExposure').DataItem
    upvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamEpoxyTipVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem
    EpoxyTipZMeasureStartHeight = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTipZMeasureStartHeight').DataItem
    zlim = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTipMeasureToolHeightZLimit').DataItem

    # move to the up looking gripper inspect position
    if not Stages.GetHardwareStateTree().ActivateState('UpCameraEpoxyTip'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move to up camera epoxy tool tip position.")
        return 0

    # set exposure and lighting
    DownCamera.LightControl1.Item2.SetIlluminationOff()
    UpCamera.SetExposureTime(upcamexposure)
    UpCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('UpCameraEpoxyTip')

    # move the epoxy tip down first
    if not MIO.SetOutputValue('EpoxyToolBackPressStates', 'On') or not MIO.SetOutputValue('EpoxyToolStates', 'Down'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to extend epoxy tool.')
        return 0

    # create the results collection
    camsnapx = []
    camsnapy = []

    # start acqusition
    for i in range(snaps):
        UpCamera.Snap()
        res = MachineVision.RunVisionTool(upvision)
        if res['Result'] != 'Success':
            MIO.SetOutputValue('EpoxyToolBackPressStates', 'Off')
            MIO.SetOutputValue('EpoxyToolStates', 'Up')
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the epoxy tool tip.')
            return 0
        # save result
        camsnapx.append(res['X'])
        camsnapy.append(res['Y'])

    # found, transform the coordinate
    calp = MachineVision.ApplyTransform('UpCameraTransform', ValueTuple[float,float](median(camsnapx), median(camsnapy)))
    if calp == None:
        return 0

    # turn on the cameras
    DownCamera.Live(True)
    UpCamera.Live(True)

    # Generate the position vector
    CoordinateCalibration.Instance.TargetVectors['EpoxyStampToDownCameraNoCorrectionVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraNoCorrectionVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    CoordinateCalibration.Instance.TargetVectors['EpoxyStampToDownCameraVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    UpCamera.LightControl1.Item2.SetIlluminationOff()
    # move the epoxy tip down first
    if not MIO.SetOutputValue('EpoxyToolStates', 'Up'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to retract epoxy tool.')
        return 0

    return 1

#-------------------------------------------------------------------------------
# LocateContactSensor
# Locate and measure the height of the contact sensor
#-------------------------------------------------------------------------------
def LocateContactSensor(StepName, SequenceObj, TestMetrics, TestResults):
    
    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    UpCamera = HardwareFactory.Instance.GetHardwareByName('UpCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')
    HeightSensor = HardwareFactory.Instance.GetHardwareByName('HeightSensor')

    # Get recipe parameters
    downcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamContactSensorExposure').DataItem
    downvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamFindContactSensorVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem
    
    if not Stages.GetHardwareStateTree().ActivateState('DownCameraContactSensor'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move to contact sensor position.")
        return 0

    # set exposure and lighting
    DownCamera.SetExposureTime(downcamexposure)
    DownCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('DownCameraContactSensor')

    # create the results collection
    camsnapx = []
    camsnapy = []

    # start acqusition
    for i in range(snaps):
        DownCamera.Snap()
        res = MachineVision.RunVisionTool(downvision)
        if res['Result'] != 'Success':
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the contact sensor.')
            return 0
        # save result
        camsnapx.append(res['X'])
        camsnapy.append(res['Y'])

    # found, transform the coordinate
    calp = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](median(camsnapx), median(camsnapy)))
    if calp == None:
        return 0

    DownCamera.LightControl1.Item2.SetIlluminationOff()
    # turn on the cameras
    DownCamera.Live(True)
    UpCamera.Live(True)

    # Now attempt measure the height of the button
    # create a vector from button to down camera
    contactSensorsPosVector = Vector3(Stages.GetAxisPosition('X') - calp.Item1, Stages.GetAxisPosition('Y') - calp.Item2, 0)
    downCamToContactSensorVector = contactSensorsPosVector\
       + Vector3(CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)
    # save this vector
    CoordinateCalibration.Instance.TargetVectors['DownCameraToHeightSensorCenterVector'] = downCamToContactSensorVector

    # now we need to find where the depth sensor is relative to the fiducial
    # Go to the depth sensor to touch sensor preset position and look for the center of the button
    if not Stages.GetHardwareStateTree().ActivateState('HeightSensorAtContactSensor'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to contact sensor position.')
        return 0
    Utility.DelayMS(1000)

    # Get recipe parameters
    searchSteps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ContactSensorSweepStepSizes').DataItem.Split(',').Select(lambda x: float(x)).ToArray()
    sweep = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ContactSensorSweepRange').DataItem
    drop = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ContactSensorSweepHeightDrop').DataItem

    # Start the sweep of the displacement sensor over the button
    # first do a quick sweep so we don't miss the button and go on forever  
             
    axes = [ 'X', 'Y' ]
    
    # start the sweep
    for a in axes:
        # remember where we started
        start = Stages.GetAxisPosition(a)
        # other tracking parameters
        dir = 1
        edges = [0.0, 0.0]
        # currheight = HeightSensor.ReadDisplacement().Item2[0]
        # do both positive and negative halves
        for x in range(2):
            dir = -dir
            accumSteps = 0.0
            # first loop move in larget step
            for step in searchSteps:
                # range check
                while abs(accumSteps) <= sweep / 2:
                    # do the motion
                    if not Stages.MoveAxisRelative(a, dir * step, Motion.AxisMotionSpeeds.Normal, True):
                        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to initiate motor move.')
                        return 0     #error
                    Utility.DelayMS(200)
                    accumSteps += dir * step
                    # check reading
                    # if (HeightSensor.ReadDisplacement().Item2[0] - currheight) > drop:
                    if HeightSensor.ReadDisplacement().Item2[0] > drop:
                        # we hit the edge. Back off, reduce step size and continue
                        Stages.MoveAxisRelative(a, -dir * step, Motion.AxisMotionSpeeds.Normal, True)
                        accumSteps += -dir * step
                        break

                # error checking
                if abs(accumSteps) > sweep / 2:
                    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Sweep moved out of range limit.')
                    return 0     #error

            # we should be at the edge here, get a reading and return to start
            edges[x] = Stages.GetAxisPosition(a)
            if not Stages.MoveAxisAbsolute(a, start, Motion.AxisMotionSpeeds.Normal, True):
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to initiate motor move.')
                return 0     #error

        # we should have both edges now. Move to the middle of the edges
        if not Stages.MoveAxisAbsolute(a, sum(edges) / len(edges), Motion.AxisMotionSpeeds.Normal, True):
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to initiate motor move.')
            return 0     #error

    # all good if we are here
    # save the depth sensor position back to the preset tree
    Stages.GetHardwareStateTree().AddState('', 'HeightSensorAtContactSensor')

    # create a vector from depth sensor to top cam
    CoordinateCalibration.Instance.TargetVectors['DownCameraToHeightSensorVector'] = Vector3(Stages.GetAxisPosition('X')\
       - downCamToContactSensorVector.X, Stages.GetAxisPosition('Y') - downCamToContactSensorVector.Y, 0)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# GetGripperAndEpoxyToolHeights
# Measure the height of the gripper and epoxy tool
#-------------------------------------------------------------------------------
def GetGripperAndEpoxyToolHeights(StepName, SequenceObj, TestMetrics, TestResults):
        
    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    UpCamera = HardwareFactory.Instance.GetHardwareByName('UpCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')
    IO = HardwareFactory.Instance.GetHardwareByName('IOControl')
    HeightSensor = HardwareFactory.Instance.GetHardwareByName('HeightSensor')
    MIO = HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl')

    GripperZMeasureStartHeight = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'GripperZMeasureStartHeight').DataItem
    zlim = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'GripperMeasureToolHeightZLimit').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem

    # Now measure the gripper height
    gripperToContactSensorVector = CoordinateCalibration.Instance.TargetVectors['GripperToDownCameraVector'] + CoordinateCalibration.Instance.TargetVectors['DownCameraToHeightSensorCenterVector']

    # move the gripper to the touch sensor button position
    if not Stages.MoveAxesUsingSafeSequence(Array[float]([ gripperToContactSensorVector.X, gripperToContactSensorVector.Y, GripperZMeasureStartHeight ]), Motion.AxisMotionSpeeds.Fast):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move gripper to contact sensor position.")
        return 0
    
    # return 1

    # find the gripper height
    gripperz = GetToolHeight([0.1, 0.01, 0.002], IO.FindByName('ContactSensor'), True, zlim, SequenceObj)
    if gripperz < 0:
        Stages.GetHardwareStateTree().ActivateState('Load')
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to detect gripper Z position.')
        return 0

    # move height sensor to contact sensor button and set reference
    if not Stages.GetHardwareStateTree().ActivateState('HeightSensorAtContactSensor'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move height sensor to contact sensor position.')
        return 0

    # move Z to measure
    if not Stages.MoveAxisAbsolute('Z', gripperz, Motion.AxisMotionSpeeds.Normal, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to gripper height measurement position.')
        return 0

    Utility.DelayMS(500)  # give it time to settle   
    heights = []
    for i in range(snaps):
        # measure height and save it back to the part
        heights.append(HeightSensor.ReadDisplacement().Item2[0])

    # get the median value
    grippergap = median(heights)

    # save it back to collection
    CoordinateCalibration.Instance.ReferenceValues['GripperDisplacementGap'] = grippergap
    CoordinateCalibration.Instance.ReferenceValues['GripperDisplacementGapZ'] = gripperz

    # Epoxy tip turn
    EpoxyTipZMeasureStartHeight = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTipZMeasureStartHeight').DataItem
    zlim = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTipMeasureToolHeightZLimit').DataItem

     # Now measure the epoxy tool tip height
    epoxyTipToContactSensorVector = CoordinateCalibration.Instance.TargetVectors['EpoxyStampToDownCameraVector'] + CoordinateCalibration.Instance.TargetVectors['DownCameraToHeightSensorCenterVector']

    # move the gripper to the touch sensor button position
    if not Stages.MoveAxesUsingSafeSequence(Array[float]([ epoxyTipToContactSensorVector.X, epoxyTipToContactSensorVector.Y, EpoxyTipZMeasureStartHeight ]), Motion.AxisMotionSpeeds.Fast):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move epoxy tool to contact sensor position.")
        return 0

    # move the epoxy tip down again
    if not MIO.SetOutputValue('EpoxyToolBackPressStates', 'On') or not MIO.SetOutputValue('EpoxyToolStates', 'Down'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to extend epoxy tool.')
        return 0

    # find the gripper height
    epoxytipz = GetToolHeight([0.1, 0.01, 0.002], IO.FindByName('ContactSensor'), True, zlim, SequenceObj)
    # retract the epoxy tool
    if not MIO.SetOutputValue('EpoxyToolBackPressStates', 'Off') or not MIO.SetOutputValue('EpoxyToolStates', 'Up'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to retract epoxy tool.')
        return 0

    if epoxytipz < 0:
        Stages.GetHardwareStateTree().ActivateState('Load')
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to detect epoxy tool tip Z position.')
        return 0

    # move height sensor to contact sensor button and set reference
    if not Stages.GetHardwareStateTree().ActivateState('HeightSensorAtContactSensor'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move height sensor to contact sensor position.')
        return 0

    # move Z to measure
    if not Stages.MoveAxisAbsolute('Z', epoxytipz, Motion.AxisMotionSpeeds.Normal, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to epoxy tool tip height measurement position.')
        return 0

    Utility.DelayMS(500)  # give it time to settle   
    heights = []
    for i in range(snaps):
        # measure height and save it back to the part
        heights.append(HeightSensor.ReadDisplacement().Item2[0])

    # get the median value
    epoxytipgap = median(heights)

    # save it back to collection
    CoordinateCalibration.Instance.ReferenceValues['EpoxyToolDisplacementGap'] = epoxytipgap
    CoordinateCalibration.Instance.ReferenceValues['EpoxyToolDisplacementGapZ'] = epoxytipz

    return 1

#-------------------------------------------------------------------------------
# GetToolHeight
# Measure the Z height of the gripper and epoxy tool
#-------------------------------------------------------------------------------
def GetToolHeight(searchSteps, contactSensor, contactState, hardlimit, SequenceObj):

    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')

    # first check the touch sensor is in the right state before we start
    if contactSensor.ReadValueImmediate() == contactState:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Contact sensor is in the wrong state. Sensor may be disconnected.")
        return -1

    initialpos = Stages.GetAxisPosition('Z')
    # start the detection loops
    for step in searchSteps:
        while contactSensor.ReadValueImmediate() != contactState:
            # check for halt command
            if SequenceObj.Halt:
                return -1

            # move stage for the next measurement
            if not Stages.MoveAxisRelative('Z', -step, Motion.AxisMotionSpeeds.Slow, True):
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to increment in Z.")
                return -1

            if Stages.GetAxisPosition("Z") <= hardlimit:    # keep from crashing
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Stage exceeded the Z position limit.")
                return -1

            Utility.DelayMS(100)

        # touch sensor triggered, back off a little if not last step
        if searchSteps.index(step) != len(searchSteps) - 1:
            if not Stages.MoveAxisRelative('Z', step * 3, Motion.AxisMotionSpeeds.Slow, True):
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Stage failed to move in Z.")
                return -1
        else:
            # back offa little bit if the end
            if not Stages.MoveAxisRelative('Z', step * 2, Motion.AxisMotionSpeeds.Slow, True):
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Stage failed to move in Z.")
                return -1

    height = Stages.GetAxisPosition('Z')
    # return to start point
    if not Stages.MoveAxisAbsolute('Z', initialpos, Motion.AxisMotionSpeeds.Slow, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Stage failed to return to initial Z position.")
        return -1

    # all good, set status and height
    return height

#-------------------------------------------------------------------------------
# LocateGripperAndHeight
# Locate and measure the height of the LSA gripper
#-------------------------------------------------------------------------------
def LocateGripperAndHeight(StepName, SequenceObj, TestMetrics, TestResults):

    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    UpCamera = HardwareFactory.Instance.GetHardwareByName('UpCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')
    IO = HardwareFactory.Instance.GetHardwareByName('IOControl')
    HeightSensor = HardwareFactory.Instance.GetHardwareByName('HeightSensor')

    upcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamGripperExposure').DataItem
    upvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamGripperVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem
    GripperZMeasureStartHeight = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'GripperZMeasureStartHeight').DataItem
    zlim = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'GripperMeasureToolHeightZLimit').DataItem

    # move to the up looking gripper inspect position
    if not Stages.GetHardwareStateTree().ActivateState('UpCameraGripper'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move to up camera gripper position.")
        return 0

    # set exposure and lighting
    DownCamera.LightControl1.Item2.SetIlluminationOff()
    UpCamera.SetExposureTime(upcamexposure)
    UpCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('UpCameraGripper')

    # create the results collection
    camsnapx = []
    camsnapy = []

    # start acqusition
    for i in range(snaps):
        UpCamera.Snap()
        res = MachineVision.RunVisionTool(upvision)
        if res['Result'] != 'Success':
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the gripper finger.')
            return 0
        # save result
        camsnapx.append(res['X'])
        camsnapy.append(res['Y'])

    # found, transform the coordinate
    calp = MachineVision.ApplyTransform('UpCameraTransform', ValueTuple[float,float](median(camsnapx), median(camsnapy)))
    if calp == None:
        return 0

    # turn on the cameras
    DownCamera.Live(True)
    UpCamera.Live(True)

    # Generate the position vector
    CoordinateCalibration.Instance.TargetVectors['GripperToDownCameraNoCorrectionVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraNoCorrectionVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    CoordinateCalibration.Instance.TargetVectors['GripperToDownCameraVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    UpCamera.LightControl1.Item2.SetIlluminationOff()

    # Now measure the gripper height
    gripperToContactSensorVector = CoordinateCalibration.Instance.TargetVectors['GripperToDownCameraVector'] + CoordinateCalibration.Instance.TargetVectors['DownCameraToHeightSensorCenterVector']

    # move the gripper to the touch sensor button position
    if not Stages.MoveAxesUsingSafeSequence(Array[float]([ gripperToContactSensorVector.X, gripperToContactSensorVector.Y, GripperZMeasureStartHeight ]), Motion.AxisMotionSpeeds.Fast):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move gripper to contact sensor position.")
        return 0
    
    # return 1

    # find the gripper height
    gripperz = GetToolHeight([0.1, 0.01, 0.002], IO.FindByName('ContactSensor'), True, zlim, SequenceObj)
    if gripperz < 0:
        Stages.GetHardwareStateTree().ActivateState('Load')
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to detect gripper Z position.')
        return 0

    # move height sensor to contact sensor button and set reference
    if not Stages.GetHardwareStateTree().ActivateState('HeightSensorAtContactSensor'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move height sensor to contact sensor position.')
        return 0

    # move Z to measure
    if not Stages.MoveAxisAbsolute('Z', gripperz, Motion.AxisMotionSpeeds.Normal, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to gripper height measurement position.')
        return 0

    Utility.DelayMS(500)  # give it time to settle   
    heights = []
    for i in range(snaps):
        # measure height and save it back to the part
        heights.append(HeightSensor.ReadDisplacement().Item2[0])

    # get the median value
    grippergap = median(heights)

    # save it back to collection
    CoordinateCalibration.Instance.ReferenceValues['GripperDisplacementGap'] = grippergap
    CoordinateCalibration.Instance.ReferenceValues['GripperDisplacementGapZ'] = gripperz

    return 1

#-------------------------------------------------------------------------------
# LocateEpoxyToolAndHeight
# Locate and measure the height of the epoxy tool
#-------------------------------------------------------------------------------
def LocateEpoxyToolAndHeight(StepName, SequenceObj, TestMetrics, TestResults):

    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    UpCamera = HardwareFactory.Instance.GetHardwareByName('UpCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Stages = HardwareFactory.Instance.GetHardwareByName('AxesStageController')
    HeightSensor = HardwareFactory.Instance.GetHardwareByName('HeightSensor')
    IO = HardwareFactory.Instance.GetHardwareByName('IOControl')
    MIO = HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl')

    upcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamEpoxyTipExposure').DataItem
    upvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UpCamEpoxyTipVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem
    EpoxyTipZMeasureStartHeight = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTipZMeasureStartHeight').DataItem
    zlim = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTipMeasureToolHeightZLimit').DataItem

    # move to the up looking gripper inspect position
    if not Stages.GetHardwareStateTree().ActivateState('UpCameraEpoxyTip'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move to up camera epoxy tool tip position.")
        return 0

    # set exposure and lighting
    DownCamera.LightControl1.Item2.SetIlluminationOff()
    UpCamera.SetExposureTime(upcamexposure)
    UpCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('UpCameraEpoxyTip')

    # move the epoxy tip down first
    if not MIO.SetOutputValue('EpoxyToolBackPressStates', 'On') or not MIO.SetOutputValue('EpoxyToolStates', 'Down'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to extend epoxy tool.')
        return 0

    # create the results collection
    camsnapx = []
    camsnapy = []

    # start acqusition
    for i in range(snaps):
        UpCamera.Snap()
        res = MachineVision.RunVisionTool(upvision)
        if res['Result'] != 'Success':
            MIO.SetOutputValue('EpoxyToolBackPressStates', 'Off')
            MIO.SetOutputValue('EpoxyToolStates', 'Up')
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the epoxy tool tip.')
            return 0
        # save result
        camsnapx.append(res['X'])
        camsnapy.append(res['Y'])

    # found, transform the coordinate
    calp = MachineVision.ApplyTransform('UpCameraTransform', ValueTuple[float,float](median(camsnapx), median(camsnapy)))
    if calp == None:
        return 0

    # turn on the cameras
    DownCamera.Live(True)
    UpCamera.Live(True)

    # Generate the position vector
    CoordinateCalibration.Instance.TargetVectors['EpoxyStampToDownCameraNoCorrectionVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraNoCorrectionVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    CoordinateCalibration.Instance.TargetVectors['EpoxyStampToDownCameraVector'] = Vector3(calp.Item1, calp.Item2, 0)\
       - Vector3(CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item1, CoordinateCalibration.Instance.ReferenceLocations['UpCameraCenterRWC'].Item2, 0)\
      + CoordinateCalibration.Instance.TargetVectors['UpCameraToDownCameraVector'] + Vector3(Stages.GetAxisPosition('X')\
     - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item1, Stages.GetAxisPosition('Y')\
    - CoordinateCalibration.Instance.ReferenceLocations['DownCameraCenterRWC'].Item2, 0)

    UpCamera.LightControl1.Item2.SetIlluminationOff()

    # Now measure the epoxy tool tip height
    epoxyTipToContactSensorVector = CoordinateCalibration.Instance.TargetVectors['EpoxyStampToDownCameraVector'] + CoordinateCalibration.Instance.TargetVectors['DownCameraToHeightSensorCenterVector']

    # move the gripper to the touch sensor button position
    if not Stages.MoveAxesUsingSafeSequence(Array[float]([ epoxyTipToContactSensorVector.X, epoxyTipToContactSensorVector.Y, EpoxyTipZMeasureStartHeight ]), Motion.AxisMotionSpeeds.Fast):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, "Failed to move epoxy tool to contact sensor position.")
        return 0
    
    # return 1

    # find the gripper height
    epoxytipz = GetToolHeight([0.1, 0.01, 0.002], IO.FindByName('ContactSensor'), True, zlim, SequenceObj)
    # retract the epoxy tool
    if not MIO.SetOutputValue('EpoxyToolBackPressStates', 'Off') or not MIO.SetOutputValue('EpoxyToolStates', 'Up'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to retract epoxy tool.')
        return 0

    if epoxytipz < 0:
        Stages.GetHardwareStateTree().ActivateState('Load')
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to detect epoxy tool tip Z position.')
        return 0

    # move height sensor to contact sensor button and set reference
    if not Stages.GetHardwareStateTree().ActivateState('HeightSensorAtContactSensor'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move height sensor to contact sensor position.')
        return 0

    # move Z to measure
    if not Stages.MoveAxisAbsolute('Z', epoxytipz, Motion.AxisMotionSpeeds.Normal, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to epoxy tool tip height measurement position.')
        return 0

    Utility.DelayMS(500)  # give it time to settle   
    heights = []
    for i in range(snaps):
        # measure height and save it back to the part
        heights.append(HeightSensor.ReadDisplacement().Item2[0])

    # get the median value
    epoxytipgap = median(heights)

    # save it back to collection
    CoordinateCalibration.Instance.ReferenceValues['EpoxyToolDisplacementGap'] = epoxytipgap
    CoordinateCalibration.Instance.ReferenceValues['EpoxyToolDisplacementGapZ'] = epoxytipz

    return 1


