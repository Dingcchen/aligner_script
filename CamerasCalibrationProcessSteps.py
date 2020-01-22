# Include all necessary assemblies from the C# side
# DO NOT REMOVE THESE REFERECES
import clr
clr.AddReference('System.Core')
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

def Template(StepName, SequenceObj, TestMetrics, TestResults):
    # DO NOT DELETE THIS METHOD
    # This is the method pattern for all python script called by AutomationCore PythonScriptManager.
    # The method arguments must be exactly as shown. They are the following:
    # SequenceName: This is the name of the process sequence that owns this step. This is required for retrieving process recipe values.
    # StepName: This is the name of the step that invokes this step. Useful for log entry and alerts to user.
    # TestMetrics: The object that holds all the process recipe values. See the C# code for usage.
    # TestResults: The object that stores all process result values. See the C# code for usage.

    TestResults.ClearAllTestResult()

    Utility.DelayMS(2000)
    if Stop:
        return 0

    pivot = TestMetrics.GetTestMetricItem(SequenceName, 'InitialPivotPoint').DataItem
    TestResults.AddTestResult('Pivot', pivot)

    Utility.DelayMS(2000)
    if Stop:
        return 0

    TestResults.AddTestResult('Step2Result', 999)
    LogHelper.Log(StepName, LogEventSeverity.Alert, 'Step1 done')
        
    # Must always return an integer. 0 = failure, everythingthing else = success
    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# CalibrateDownCamera
# Calibrate the down camera to stage positions
#-------------------------------------------------------------------------------
def CalibrateDownCamera(StepName, SequenceObj, TestMetrics, TestResults):

    CAMERA_SHIFT = 0.6 

    if not LogHelper.AskContinue('Is a MPO loaded?'):
        return 0

    # Move hexapod to root coordinate system
    HardwareFactory.Instance.GetHardwareByName('Hexapod').EnableZeroCoordinateSystem()

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
    # set exposure
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(5)

    # move to preset positions
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState('CameraCalibration')
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState('CameraCalibration')

    if SequenceObj.Halt:
        return 0

    # turn off all lights and then set to recipe level
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
    HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState('CameraCalibration')

    # Position 1
    # shift to one corner
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxesRelative(Array[String]([ 'X', 'Y' ]), Array[float]([ -CAMERA_SHIFT / 2, -CAMERA_SHIFT / 2]), Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    downvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownVisionTool').DataItem #'DieTopGF2NoGlassBlock'
    downcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamExposure').DataItem #'DieTopGF2NoGlassBlock'
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(downcamexposure)

    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(downvision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection = List[Vision.CalibratePointPair]()
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y')))

    # Position 2
    # shift X
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', CAMERA_SHIFT, Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(downvision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y')))

    # Position 3
    # shift Y
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', CAMERA_SHIFT, Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(downvision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y')))

    # Position 4
    # shift X
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -CAMERA_SHIFT, Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(downvision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y')))

    # add it to transform and save to file
    HardwareFactory.Instance.GetHardwareByName('MachineVision').AddTransform('DownCameraTransform', pointCollection)

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# CalibrateSideCamera
# Calibrate the side camera to stage position
#-------------------------------------------------------------------------------
def CalibrateSideCamera(StepName, SequenceObj, TestMetrics, TestResults):
    
    CAMERA_SHIFT = 0.6 

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
    # set exposure
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(3)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(10)

    # move to preset positions
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState('CameraCalibration')
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState('CameraCalibration')

    if SequenceObj.Halt:
        return 0

    # turn off all lights and then set to recipe level
    HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').SetIlluminationOff()
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState('CameraCalibration')

    # Position 1
    # shift to one corner
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxesRelative(Array[String]([ 'X', 'Z' ]), Array[float]([ -CAMERA_SHIFT / 2, -CAMERA_SHIFT / 2]), Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    sidevision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'SideVisionTool').DataItem #'DieTopGF2NoGlassBlock'
    sidecamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'SideCamExposure').DataItem #'DieTopGF2NoGlassBlock'
    HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(sidecamexposure)

    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidevision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection = List[Vision.CalibratePointPair]()
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z')))
    
    # Position 2
    # shift X
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', CAMERA_SHIFT, Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidevision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z')))

    # Position 3
    # shift Y
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', CAMERA_SHIFT, Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidevision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z')))

    # Position 4
    # shift X
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -CAMERA_SHIFT, Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidevision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z')))

    # add it to transform and save to file
    HardwareFactory.Instance.GetHardwareByName('MachineVision').AddTransform('SideCameraTransform', pointCollection)
    # turn off ring light
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
    # turn on camera live view
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # return to load position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState('BoardLoad')

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Finalize
# Finalize process such as saving data
#-------------------------------------------------------------------------------
def Finalize(StepName, SequenceObj, TestMetrics, TestResults):

    HardwareFactory.Instance.GetHardwareByName('MachineVision').SaveAllTransforms()

    return 1
