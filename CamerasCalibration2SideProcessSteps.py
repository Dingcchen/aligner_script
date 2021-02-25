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
import math as math
from System.Diagnostics import Stopwatch
from System.Collections.Generic import List
clr.AddReferenceToFile('HAL.dll')
from HAL import Vision
from HAL import Motion
from HAL import HardwareFactory
from HAL import HardwareInitializeState
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoAligner.exe')
from CiscoAligner import PickAndPlace
from CiscoAligner import Station
from CiscoAligner import Alignments
from time import sleep
import csv
# from AlignerUtil import *
from datetime import datetime
from step_manager  import *

Hexapod = HardwareFactory.Instance.GetHardwareByName('Hexapod')
DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
LeftSideCamera = HardwareFactory.Instance.GetHardwareByName('LeftSideCamera')
RightSideCamera = HardwareFactory.Instance.GetHardwareByName('RightSideCamera')

def Template(SequenceObj, alignment_parameters, alignment_results):
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
        return alignment_results

#-------------------------------------------------------------------------------
# CalibrateDownCamera
# Calibrate the down camera to stage positions
#-------------------------------------------------------------------------------
def CalibrateDownCamera(SequenceObj, alignment_parameters, alignment_results):

    CAMERA_SHIFT = 0.6 

    if not LogHelper.AskContinue('Is a MPO loaded?'):
        return 0

    # Move hexapod to root coordinate system
    HardwareFactory.Instance.GetHardwareByName('Hexapod').EnableZeroCoordinateSystem()

    # turn on the cameras
    # HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    # HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').Live(True)
    DownCamera.Live(True)
    LeftSideCamera.Live(True)
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

    TestMetrics = SequenceObj.TestMetrics
    # snap image to load to vision
    downvision = alignment_parameters['DownVisionTool'] #'DieTopGF2NoGlassBlock'
    downcamexposure = alignment_parameters['DownCamExposure'] #'DieTopGF2NoGlassBlock'
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(downcamexposure)

    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Run vision tool ' + downvision )
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

    Utility.DelayMS(2000)

    # snap image to load to vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Run vision tool 2 ' + downvision )
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
    DownCamera.Live(False)
    LeftSideCamera.Live(False)

    if SequenceObj.Halt:
        return 0
    else:
        return alignment_results

#-------------------------------------------------------------------------------
# CalibrateLeftSideCamera
# Calibrate the side camera to stage position
#-------------------------------------------------------------------------------
def CalibrateLeftSideCamera(SequenceObj, alignment_parameters, alignment_results):
    
    CAMERA_SHIFT = 0.6 

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').Live(True)
    # set exposure
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(3)
    HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').SetExposureTime(1)

    # move to preset positions
    HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState('CameraCalibration')
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
    TestMetrics = SequenceObj.TestMetrics
    sidevision = alignment_parameters['SideVisionTool']
    # sidevision = "..\\Vision\\glass_block\\FAU_side\\TFC_FAU_GB_side_TB"
    # sidecamexposure = alignment_parameters['FAUSideVisionCameraExposure']
    # HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').SetExposureTime(sidecamexposure)

    HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').Snap()
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
    HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').Snap()
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
    HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').Snap()
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
    HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidevision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z')))

    # add it to transform and save to file
    HardwareFactory.Instance.GetHardwareByName('MachineVision').AddTransform('LeftSideCameraTransform', pointCollection)
    # turn off ring light
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
    # turn on camera live view
    HardwareFactory.Instance.GetHardwareByName('LeftSideCamera').Live(True)

    # return to load position
    # HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState('BoardLoad')

    if SequenceObj.Halt:
        return 0
    else:
        return alignment_results

#-------------------------------------------------------------------------------
# CalibrateRightSideCamera
# Calibrate the right side camera to stage position
#-------------------------------------------------------------------------------
def CalibrateRightSideCamera(SequenceObj, alignment_parameters, alignment_results):
    
    CAMERA_SHIFT = 0.6 

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').Live(True)
    # set exposure
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(3)
    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').SetExposureTime(1)

    # move to preset positions
    HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState('CameraCalibration')
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState('RightSideCameraCalibration')

    if SequenceObj.Halt:
        return 0

    # turn off all lights and then set to recipe level
    HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').SetIlluminationOff()
    # HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState('CameraCalibration')

    # Position 1
    # shift to one corner
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxesRelative(Array[String]([ 'X', 'Z' ]), Array[float]([ -CAMERA_SHIFT / 2, -CAMERA_SHIFT / 2]), Motion.AxisMotionSpeeds.Normal, True):
        return 0

    Utility.DelayMS(1000)

    # snap image to load to vision
    TestMetrics = SequenceObj.TestMetrics
    sidevision = alignment_parameters['RightSideVisionTool'] #'DieTopGF2NoGlassBlock'
    sidecamexposure = alignment_parameters['RightSideCamExposure'] #'DieTopGF2NoGlassBlock'
    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').SetExposureTime(sidecamexposure)

    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').Snap()
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
    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').Snap()
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
    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').Snap()
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
    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidevision)
    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0

    # save the positions
    pointCollection.Add( Vision.CalibratePointPair(res['X'], res['Y'], HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'), HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z')))

    # add it to transform and save to file
    HardwareFactory.Instance.GetHardwareByName('MachineVision').AddTransform('RightSideCameraTransform', pointCollection)
    # turn off ring light
    # HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
    # turn on camera live view
    HardwareFactory.Instance.GetHardwareByName('RightSideCamera').Live(True)

    # return to load position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState('BoardLoad')

    if SequenceObj.Halt:
        return 0
    else:
        return alignment_results

#-------------------------------------------------------------------------------
# Finalize
# Finalize process such as saving data
#-------------------------------------------------------------------------------
def Finalize(SequenceObj, alignment_parameters, alignment_results):

    HardwareFactory.Instance.GetHardwareByName('MachineVision').SaveAllTransforms()

    return alignment_results
