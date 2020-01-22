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
        
    #Must always return an integer. 0 = failure, everythingthing else = success
    return 1

#-------------------------------------------------------------------------------
# Initialize
# Clears up test data and other prep work before process starts
#-------------------------------------------------------------------------------
def Initialize(StepName, SequenceObj, TestMetrics, TestResults):
    
    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # clear the output data
    TestResults.ClearAllTestResult()
    Utility.ShowProcessTextOnMainUI() # clear message

    TestResults.AddTestResult('Start_Time', DateTime.Now)
    TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
    TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())

    return 1

#-------------------------------------------------------------------------------
# CheckProbe
# Ask the user to visually check probe contact to the die
#-------------------------------------------------------------------------------
def CheckProbe(StepName, SequenceObj, TestMetrics, TestResults):
    
    probeposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ProbePresetPosition').DataItem #'BoardLoad'
    initialposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # set exposure
    # HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(15)

    # move things out of way for operator to load stuff
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(probeposition)

    #Ask operator to adjust probe
    if LogHelper.AskContinue('Adjust probe until pins are in contact with pads. Click Yes when done, No to abort.') == False:
        return 0

    # go back to initial position
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# FindSubmount
# Use vision to find the location of the die
#-------------------------------------------------------------------------------
def SetFirstLightPositionToFAU(StepName, SequenceObj, TestMetrics, TestResults):

    # define vision tool to use for easier editing
    pmfautopvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PowermeterFAUDownVisionTool').DataItem #'DieTopGF2NoGlassBlock'
    laserfautopvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserFAUDownVisionTool').DataItem #"MPOTop_2_7"
    pmfausidevision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PowermeterFAUSideVisionTool').DataItem #'DieSideGF2NoGlassBlock'
    laserfausidevision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserFAUSideVisionTool').DataItem #'MPOSideNormal'
    fautopexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUDownVisionCameraExposure').DataItem #5
    fausideexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionCameraExposure').DataItem #5
    initialposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'

    # Move hexapod to root coordinate system
    HardwareFactory.Instance.GetHardwareByName('Hexapod').EnableZeroCoordinateSystem()

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # move camera to preset position
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)

    # Get hexapod preset position from recipe and go there
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(initialposition)

    if SequenceObj.Halt:
        return 0

    # set the hexapod pivot point for this process
    initpivot = list(map(lambda x: float(x), TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPivotPoint').DataItem.split(',')))
    HardwareFactory.Instance.GetHardwareByName('Hexapod').CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

    #turn off all lights
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
    HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').SetIlluminationOff()

    # set light and exposure
    HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(initialposition)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(fautopexposure)

    # acquire image for vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    # save to file
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
    Utility.CreateDirectory(dir)
    dir = IO.Path.Combine(dir, 'FAUTop.jpg')
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

    # run vision
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(pmfautopvision)

    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the powermeter FAU top position.')
        return 0

    inputx = res['X']
    inputy = res['Y']
    inputangle = Utility.RadianToDegree(res['Angle'])

    # one more time for the laser side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(laserfautopvision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
        return 0

    outputx = res['X']
    outputy = res['Y']
    outputangle = Utility.RadianToDegree(res['Angle'])

    # done vision, back to live view
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

    if SequenceObj.Halt:
        return 0

    # adjust the yaw angle
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)

    # transform the coordinates so we know how to move
    dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

    # move Y first
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
        return 0

    if SequenceObj.Halt:
        return 0

    Utility.DelayMS(500)

    # re-take laser side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(laserfautopvision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
        return 0

    # retreive vision results
    outputangle = Utility.RadianToDegree(res['Angle'])

    # do angle adjustment one more time
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)
    # vision top once more
    # re-take laaser side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(laserfautopvision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
        return 0

    # retreive vision results
    outputx = res['X']
    outputy = res['Y']
    outputx2 = res['X2']
    outputy2 = res['Y2']

    # adjust the translation
    # dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))
    end = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

    # calculate the distance between the first and last fiber channel in order to do pivot angle compensation
    TestResults.AddTestResult('Outer_Channels_Width', Math.Round(Math.Sqrt(Math.Pow(end.Item1 - start.Item1, 2) + pow(end.Item2 - start.Item2, 2)), 5))

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

    if SequenceObj.Halt:
        return 0

    # start the translational motion again
    # first move in Y
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
        return 0

    # move in x, but with 200um gap remain
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', dest.Item1 - start.Item1 - 0.2, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
        return 0

    if SequenceObj.Halt:
        return 0

    # re-do vision one more time at close proximity to achieve better initial alignment
    # acquire image for vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    # run vision
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(pmfautopvision)

    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the powermeter FAU top position.')
        return 0

    inputx = res['X']
    inputy = res['Y']

    # one more time for the laser side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(laserfautopvision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
        return 0

    outputx = res['X']
    outputy = res['Y']

    # done vision, back to live view
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

    if SequenceObj.Halt:
        return 0

    # transform the coordinates so we know how to move
    dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

    # start the translational motion again
    # first move in Y
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
        return 0

    # move in x, but with 100um gap remain
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', dest.Item1 - start.Item1 - 0.1, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
        return 0

    if SequenceObj.Halt:
        return 0

    # do a FAU contact detection to set the actual gap
    # start move incrementally until force sensor detect contact
    # first zero out the force sensr
    HardwareFactory.Instance.GetHardwareByName('Hexapod').ZeroForceSensor()
    # get initial force
    forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
    startforce = forcesensor.ReadValueImmediate()
    # start force monitor
    threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
    backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
    farfieldgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FarFieldGap').DataItem
    # Monitor force change
    while (forcesensor.ReadValueImmediate() - startforce) < threshold:
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
        Utility.DelayMS(5)
        # check for user interrupt
        if SequenceObj.Halt:
            return 0

    # contact, open up the gap
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
    # set this position as the zero position
    TestResults.AddTestResult('Optical_Z_Zero_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
    # set far field gap for first light alignment
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -farfieldgap, Motion.AxisMotionSpeeds.Normal, True)


    # Side view to adjust FAU relative heights
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(initialposition)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(fausideexposure)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(laserfausidevision)
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU side position.')
        return 0

    laserangle = Utility.RadianToDegree(res['Angle'])

    # find the mpo side
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(pmfausidevision)
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the powermeter FAU side position.')
        return 0

    pmx = res['X']
    pmy = res['Y']
    pmangle = Utility.RadianToDegree(res['Angle'])

    # adjust the yaw angle
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('V', laserangle - pmangle, Motion.AxisMotionSpeeds.Normal, True)

    # find the laser FAU again for translational adjustment
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(laserfausidevision)
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU side position.')
        return 0

    laserx = res['X']
    lasery = res['Y']

    # turn on the camera again
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # turn off light 
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()

    # transform the coordinates so we know how to move
    dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](pmx, pmy))
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](laserx, lasery))

    # move the mpo height to match that of the die height plus whatever offset from recipe
    zoffset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightZOffsetFromVision').DataItem

    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', dest.Item2 - start.Item2 + zoffset, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move laser FAU to match powermeter FAU height position.')
        return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# FindSubmount
# Use vision to find the location of the die
#-------------------------------------------------------------------------------
def SetFirstLightPositionToDie(StepName, SequenceObj, TestMetrics, TestResults):

    # define vision tool to use for easier editing
    topdievision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopVisionTool').DataItem #'DieTopGF2NoGlassBlock'
    topmpovision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUTopVisionTool').DataItem #"MPOTop_2_7"
    sidedievision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieSideVisionTool').DataItem #'DieSideGF2NoGlassBlock'
    sidempovision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionTool').DataItem #'MPOSideNormal'
    dietopexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopVisionCameraExposure').DataItem #3
    mpotopexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUTopVisionCameraExposure').DataItem #4
    diesideexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieSideVisionCameraExposure').DataItem #4
    mposideexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionCameraExposure').DataItem #10
    initialposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
    focusedposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieFocusedPresetPosition').DataItem #'FAUToBoardInitial'
    # Move hexapod to root coordinate system
    HardwareFactory.Instance.GetHardwareByName('Hexapod').EnableZeroCoordinateSystem()
    
    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # move cameras to preset position
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)
    HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(initialposition)

    # set exposure
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(dietopexposure)

    # Get hexapod and camera stage preset positions from recipe and go there
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(initialposition)

    if SequenceObj.Halt:
        return 0

    # set the hexapod pivot point for this process
    initpivot = list(map(lambda x: float(x), TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPivotPoint').DataItem.split(',')))
    HardwareFactory.Instance.GetHardwareByName('Hexapod').CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

    #turn off all lights and then set to recipe level
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
    HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(initialposition)

    # acquire image for vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    # save to file
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
    Utility.CreateDirectory(dir)
    dir = IO.Path.Combine(dir, 'DieTop.jpg')
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

    # run vision
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topdievision)

    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
        return 0

    inputx = res['X']
    inputy = res['Y']
    inputangle = Utility.RadianToDegree(res['Angle'])

    # one more time for the MPO side
    # set exposure
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(mpotopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topmpovision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
        # allow operator to enter wg to wg distance
        ret = UserFormInputDialog.ShowDialog('Enter WG gap distance', 'Enter WG to WG distance in mm. Manually set initial first light position.', True)
        if ret == True:
            TestResults.AddTestResult('Outer_Channels_Width', float(UserFormInputDialog.ReturnValue))

        return 0

    outputx = res['X']
    outputy = res['Y']
    outputangle = Utility.RadianToDegree(res['Angle'])

    # done vision, back to live view
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(dietopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

    # adjust the yaw angle
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)

    # transform the coordinates so we know how to move
    dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

    # move Y first
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
        return 0

    if SequenceObj.Halt:
        return 0

    Utility.DelayMS(500)

    # re-do the vision again to have better initial angle placement
    # re-take MPO side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(mpotopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topmpovision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
        return 0

    # vision top once more
    # re-do the vision again to have better initial angle placement
    # re-take MPO side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(mpotopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topmpovision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
        return 0

    # retreive vision results
    outputx = res['X']
    outputy = res['Y']
    outputx2 = res['X2']
    outputy2 = res['Y2']

    # adjust the translation
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))
    end = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

    # calculate the distance between the first and last fiber channel in order to do pivot angle compensation
    TestResults.AddTestResult('Outer_Channels_Width', Math.Round(Math.Sqrt(Math.Pow(end.Item1 - start.Item1, 2) + pow(end.Item2 - start.Item2, 2)), 5))

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

    if SequenceObj.Halt:
        return 0

    # resume the translational motion again
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
        return 0

    # move in x, but with 200um gap remain
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', dest.Item1 - start.Item1 - TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionFinalGapX').DataItem, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
        return 0

    if SequenceObj.Halt:
        return 0


    # re-do vision one more time at close proximity to achieve better initial alignment
    # acquire image for vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(dietopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    # run vision
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topdievision)

    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
        return 0

    inputangle = Utility.RadianToDegree(res['Angle'])

    # one more time for the laser side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(mpotopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topmpovision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
        return 0

    outputangle = Utility.RadianToDegree(res['Angle'])
    
    # done vision, back to live view
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    # do angle adjustment one more time
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)

    # re-do vision one more time at close proximity to achieve better initial alignment
    # acquire image for vision
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(dietopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    # run vision
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topdievision)

    # check result
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
        return 0

    inputx = res['X']
    inputy = res['Y']
    inputangle = Utility.RadianToDegree(res['Angle'])

    # one more time for the laser side
    HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(mpotopexposure)
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topmpovision)

    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
        return 0

    outputx = res['X']
    outputy = res['Y']
    
    # done vision, back to live view
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

    if SequenceObj.Halt:
        return 0

    # transform the coordinates so we know how to move
    dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

    # start the translational motion again
    # first move in Y
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
        Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
        return 0

    # move to a location far enough for side view vision to work better
    # the light causes the die to bleed into the MPO
    processdist = dest.Item1 - start.Item1 - TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionDryAlignGapX').DataItem
    # sidevisiondist = dest.Item1 - start.Item1 - 0.3  # 300um offset for side vision
    # if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', sidevisiondist, Motion.AxisMotionSpeeds.Slow, True):
    #     LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
    #     return 0

    if SequenceObj.Halt:
        return 0

    # find the die from side camera
    HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(focusedposition)
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff() 
    HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(diesideexposure)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidedievision)
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die side position.')
        return 0

    diex = res['X']
    diey = res['Y']
    dieangle = Utility.RadianToDegree(res['Angle'])

    # find the mpo side
    HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(initialposition)
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(initialposition)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(mposideexposure)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidempovision)
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the MPO side position.')
        return 0

    mpox = res['WGX']
    mpoy = res['WGY']
    mpoangle = Utility.RadianToDegree(res['Angle'])

    # turn on the camera again
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # turn off light 
    HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()

    # transform the coordinates so we know how to move
    dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](diex, diey))
    start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](mpox, mpoy))

    # move the mpo height to match that of the die height
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move MPO to match die height position.')
        return 0

    # adjust the yaw angle
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('V', mpoangle - dieangle, Motion.AxisMotionSpeeds.Normal, True)

    # now move x to put the mpo to process distance from die
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
        return 0

    if SequenceObj.Halt:
        return 0

    # remember this postion as optical z zero
    TestResults.AddTestResult('Optical_Z_Zero_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))

    # adjust the starting Z position base on the recipe value
    if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightZOffsetFromVision').DataItem, Motion.AxisMotionSpeeds.Normal, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Z direction during initial height offset adjustment.')
        return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# FirstLightSearch
# First light alignment on the channels, no balance
# Note: This routine find power on top channel only

#-------------------------------------------------------------------------------
def FirstLightSearchSingleChannel(StepName, SequenceObj, TestMetrics, TestResults):
    
    # remember this postion as optical z zero
    # in case we aligned manually, get the z position here instead of previous step
    TestResults.AddTestResult('Optical_Z_Zero_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # declare variables we will use
    retries = 0
    limit = 5

    # get the hexapod alignment algorithm
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    # Reload parameters from recipe file
    minpower = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanMinPower').DataItem # this value will be in hexapod analog input unit. 
    scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
    scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
    scan.Channel = 1
    scan.ExecuteOnce = SequenceObj.AutoStep

    # one scan to get initial power
    scan.ExecuteNoneModal()
    if scan.IsSuccess == False or  SequenceObj.Halt:
        return 0

    # wait to settle
    Utility.DelayMS(500)

    topinitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
    if topinitpower < minpower:
        # do a few scans to make sure we are in the closest range possible
        while retries < limit:
            scan.ExecuteNoneModal()
            if scan.IsSuccess == False or SequenceObj.Halt:
                return 0

            # wait to settle
            Utility.DelayMS(500)

            # check return condition
            p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
            if p > topinitpower or abs(p - topinitpower) / abs(p) < 0.2:
                break  # power close enough, good alignment
            if p > topinitpower:
                topinitpower = p

            retries += 1
        
        if retries >= limit:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many retries.')
            return 0    # error condition

        if HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5) < minpower:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Minimum first light power for top channel not achieved.')
            return 0

    # rescan smaller area
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    # start the scan again
    scan.ExecuteNoneModal()

    if scan.IsSuccess == False or SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# FirstLightSearch
# First light alignment on the channels, no balance
# Note: This routine find power on top and bottom channels and does roll adjust

#-------------------------------------------------------------------------------
def FirstLightSearchDualChannels(StepName, SequenceObj, TestMetrics, TestResults):
    
    # remember this postion as optical z zero
    # in case we aligned manually, get the z position here instead of previous step
    TestResults.AddTestResult('Optical_Z_Zero_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # declare variables we will use
    retries = 0
    limit = 5

    # get the hexapod alignment algorithm
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    # Reload parameters from recipe file
    minpower = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanMinPower').DataItem # this value will be in hexapod analog input unit. 
    scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
    scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
    scan.Channel = 1
    scan.ExecuteOnce = SequenceObj.AutoStep

    # one scan to get initial power
    #scan.ExecuteNoneModal()
    #if scan.IsSuccess == False or  SequenceObj.Halt:
    #    return 0

    # wait to settle
    #Utility.DelayMS(500)

    topinitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
    if topinitpower < minpower:
        # do a few scans to make sure we are in the closest range possible
        while retries < limit:
            scan.ExecuteNoneModal()
            if scan.IsSuccess == False or SequenceObj.Halt:
                return 0

            # wait to settle
            Utility.DelayMS(500)

            # check return condition
            p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
            if p > topinitpower or abs(p - topinitpower) / abs(p) < 0.2:
                break  # power close enough, good alignment
            if p > topinitpower:
                topinitpower = p

            retries += 1
        
        if retries >= limit:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many retries.')
            return 0    # error condition

        if HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5) < minpower:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Minimum first light power for top channel not achieved.')
            return 0

    # rescan smaller area
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    # start the scan again
    scan.ExecuteNoneModal()

    if scan.IsSuccess == False or SequenceObj.Halt:
        return 0

    # save top chan aligned position
    topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

    # now do channel 2
    scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
    scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
    scan.Channel = 2
    # one scan to get initial power
    #scan.ExecuteNoneModal()
    #if scan.IsSuccess == False or  SequenceObj.Halt:
    #    return 0
    # wait to settle
    #Utility.DelayMS(500)

    bottominitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
    retries = 0
    if bottominitpower < minpower:
        # do a few scans to make sure we are in the closest range possible
        while retries < limit:
            scan.ExecuteNoneModal()
            if scan.IsSuccess == False or SequenceObj.Halt:
                return 0

            # wait to settle
            Utility.DelayMS(500)

            # check return condition
            p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
            if p > bottominitpower or abs(p - bottominitpower) / abs(p) < 0.2:
                break  # power close enough, good alignment
            if p > bottominitpower:
                bottominitpower = p

            retries += 1
        
        if retries >= limit:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many retries.')
            return 0    # error condition

        if HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5) < minpower:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Minimum first light power for bottom channel not achieved.')
            return 0

    # rescan smaller area
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    # start the scan again
    scan.ExecuteNoneModal()

    if scan.IsSuccess == False or SequenceObj.Halt:
        return 0

    # save top chan aligned position
    bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

    # adjust the roll
    width = TestResults.RetrieveTestResult('Outer_Channels_Width')
    h = Math.Atan(Math.Abs(topchanpos[2] - bottomchanpos[2]))
    if h < 0.001:
        return 1    # we achieved the roll angle when the optical Z difference is less than 1 um

    # calculate the roll angle
    r = Utility.RadianToDegree(Math.Atan(h / width))
    rollangle = r
    if topchanpos[2] > bottomchanpos[2]:
        rollangle = -r

    # adjust the roll angle again
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
    # wait to settle
    Utility.DelayMS(500)

    # repeat adjustment if necessary
    retries = 0
    while retries < limit and not SequenceObj.Halt:

        # start the algorithms
        scan.Channel = 1
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # remember the final position
        topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # repeat scan for the second channel
        scan.Channel = 2
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # get the final position of second channel
        bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # double check and readjust roll if necessary
        # calculate the roll angle
        h = Math.Atan(Math.Abs(topchanpos[2] - bottomchanpos[2]))
        if h < 0.001:
           break    # we achieved the roll angle when the optical Z difference is less than 1 um

        # calculate the roll angle
        r = Utility.RadianToDegree(Math.Atan(h / width))
        rollangle = r
        if topchanpos[2] > bottomchanpos[2]:
           rollangle = -r

        # adjust the roll angle again
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)

        retries += 1
    
    # check stop conditions
    if retries >= limit:
       LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many retries.')       
       return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# OptimizeRollAngle
# Find the optimal roll angle for loop back on both channels
# NOTE: This routine is designed for loop back, not PD signal
#-------------------------------------------------------------------------------
def OptimizeRollAngleHexapod(StepName, SequenceObj, TestMetrics, TestResults):
    
    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # get the alignment algorithms
    hscan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    optimalrollsearch = Alignments.AlignmentFactory.Instance.SelectAlignment('SimplexMaximumSearch')

    # get hexapod search parameters from recipe file
    hscan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
    hscan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
    hscan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    hscan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    hscan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    hscan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
    
    hscan.Channel = 1
    hscan.ExecuteOnce = SequenceObj.AutoStep

    # Load the simplex search parameter to optimize roll angle
    optimalrollsearch.NMax = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollNMax').DataItem
    optimalrollsearch.RTol = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollRTol').DataItem
    optimalrollsearch.MinRes = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMinRes').DataItem
    optimalrollsearch.Lambda = (str)(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollLambda').DataItem)
    optimalrollsearch.MaxRestarts = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxRestarts').DataItem
    optimalrollsearch.MaxTinyMoves = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxTinyMoves').DataItem
    optimalrollsearch.ExecuteOnce = SequenceObj.AutoStep

    startangle = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U')   # get the starting pitch angle
    # Now we will start the optimal roll angle search using the Nanocube for speed and accuracy
    # define the delegate for algo feedback
    def EvalRoll(a):
        # tweak the roll angle then optimize power with Nanocube
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('U', startangle + a[0], Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)
        # scan for optimal
        hscan.ExecuteNoneModal()
        # wait to settle
        Utility.DelayMS(500)

        return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)  # we want to maximize the bottom channel power since doing so means we are aligned in roll

    # connect the call back function
    optimalrollsearch.EvalFunction = Func[Array[float],float](EvalRoll)
    # start roll optimization
    optimalrollsearch.ExecuteNoneModal()

    if optimalrollsearch.IsSuccess == False or  SequenceObj.Halt:
        return 0

    # wait to settle
    Utility.DelayMS(500)

    #save the final data for bottom channel
    position = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('First_Light_Top_Channel_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6))
    TestResults.AddTestResult('First_Light_Bottom_Channel_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6))
    TestResults.AddTestResult('First_Light_Hexapod_X', position[0])
    TestResults.AddTestResult('First_Light_Hexapod_Y', position[1])
    TestResults.AddTestResult('First_Light_Hexapod_Z', position[2])
    TestResults.AddTestResult('First_Light_Hexapod_U', position[3])
    TestResults.AddTestResult('First_Light_Hexapod_V', position[4])
    TestResults.AddTestResult('First_Light_Hexapod_W', position[5])

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# OptimizeRollAngle
# Find the optimal roll angle for loop back on both channels
# NOTE: This routine is designed for loop back, not PD signal
#-------------------------------------------------------------------------------
def OptimizeRollAngleNanocube(StepName, SequenceObj, TestMetrics, TestResults):
    
    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # get the alignment algorithms
    nscan = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeRasterScan')
    optimalrollsearch = Alignments.AlignmentFactory.Instance.SelectAlignment('SimplexMaximumSearch')
  
    # get nanocube scan parameters
    nscan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis1').DataItem
    nscan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis2').DataItem
    # we are working in um when dealing with Nanocube
    nscan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanRange1').DataItem * 1000
    nscan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanRange2').DataItem * 1000
    # start at the middle position
    nscan.Axis1Position = 50
    nscan.Axis2Position = 50
    nscan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanVelocity').DataItem * 1000
    nscan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanFrequency').DataItem
    nscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
    nscan.Channel = 1
    nscan.ExecuteOnce = SequenceObj.AutoStep

    # Load the simplex search parameter to optimize roll angle
    optimalrollsearch.NMax = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollNMax').DataItem
    optimalrollsearch.RTol = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollRTol').DataItem
    optimalrollsearch.MinRes = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMinRes').DataItem
    optimalrollsearch.Lambda = (str)(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollLambda').DataItem)
    optimalrollsearch.MaxRestarts = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxRestarts').DataItem
    optimalrollsearch.MaxTinyMoves = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxTinyMoves').DataItem
    optimalrollsearch.ExecuteOnce = SequenceObj.AutoStep

    startangle = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U')   # get the starting pitch angle
    # Now we will start the optimal roll angle search using the Nanocube for speed and accuracy
    # define the delegate for algo feedback
    def EvalRoll(a):
        # tweak the roll angle then optimize power with Nanocube
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('U', startangle + a[0], Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)
        # scan for optimal
        nscan.ExecuteNoneModal()
        # wait to settle
        Utility.DelayMS(500)

        # double check Nanocube position and make sure it's always within the motion range
        axis1offset = (float)(HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(nscan.Axis1) - nscan.Axis1Position)
        axis2offset = (float)(HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(nscan.Axis2) - nscan.Axis2Position)

        if Math.Abs(axis1offset) >= nscan.Range1 / 2 or Math.Abs(axis2offset) >= nscan.Range2 / 2:
            if Math.Abs(axis1offset) > nscan.Range1 / 2:
                HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisRelative(nscan.Axis1, -axis1offset, Motion.AxisMotionSpeeds.Normal, True)
                HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative(nscan.Axis1, axis1offset / 1000, Motion.AxisMotionSpeeds.Normal, True)

            if Math.Abs(axis2offset) > nscan.Range2 / 2:
                HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisRelative(nscan.Axis2, -axis2offset, Motion.AxisMotionSpeeds.Normal, True)
                HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative(nscan.Axis2, axis2offset / 1000, Motion.AxisMotionSpeeds.Normal, True)

                # wait to settle
            Utility.DelayMS(500)

            # optimize again
            nscan.ExecuteNoneModal()

            # wait to settle
            Utility.DelayMS(500)

        return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)  # we want to maximize the bottom channel power since doing so means we are aligned in roll

    # connect the call back function
    optimalrollsearch.EvalFunction = Func[Array[float],float](EvalRoll)
    # start roll optimization
    optimalrollsearch.ExecuteNoneModal()

    if optimalrollsearch.IsSuccess == False or  SequenceObj.Halt:
        return 0

    # wait to settle
    Utility.DelayMS(500)

    #save the final data for bottom channel
    position = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('First_Light_Top_Channel_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6))
    TestResults.AddTestResult('First_Light_Bottom_Channel_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6))
    TestResults.AddTestResult('First_Light_Hexapod_X', position[0])
    TestResults.AddTestResult('First_Light_Hexapod_Y', position[1])
    TestResults.AddTestResult('First_Light_Hexapod_Z', position[2])
    TestResults.AddTestResult('First_Light_Hexapod_U', position[3])
    TestResults.AddTestResult('First_Light_Hexapod_V', position[4])
    TestResults.AddTestResult('First_Light_Hexapod_W', position[5])

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# PitchPivotSearch
# Find the pitch pivot point
#-------------------------------------------------------------------------------
def PitchPivotSearch(StepName, SequenceObj, TestMetrics, TestResults):

    # save the current X position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X')
    # retreive zero position
    zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
    # allow a larger gap for safe pitch pivot search
    safegap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotOffsetFromZero').DataItem
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero - safegap, Motion.AxisMotionSpeeds.Normal, True)
    # readjust the pivot point
    # HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] - safegap
    # enable the new pivot point
    # HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')

    pitchpivotsearch = Alignments.AlignmentFactory.Instance.SelectAlignment('SimplexMaximumSearch')
    # Reload the parameters
    pitchpivotsearch.NMax = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotNMax').DataItem
    pitchpivotsearch.RTol = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotRTol').DataItem
    pitchpivotsearch.MinRes = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotMinRes').DataItem
    pitchpivotsearch.Lambda = (str)(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotLambda').DataItem)
    pitchpivotsearch.MaxRestarts = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotMaxRestarts').DataItem
    pitchpivotsearch.MaxTinyMoves = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotMaxTinyMoves').DataItem
    pitchpivotsearch.ExecuteOnce = SequenceObj.AutoStep

    # pitchoffset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotOffset').DataItem
    pitchoffsetX = HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X']
    pitchoffsetZ = HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['Z']
    targetpitchangle = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotTargetAngle').DataItem
    # the axes plane that changes roll pivot point
    pivotaxes = Array[String](['X','Z'])
    startangle = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('V')   # get the starting pitch angle

    # define the delegate for algo feedback
    def EvalPivot(a):
        HardwareFactory.Instance.GetHardwareByName('Hexapod').CreateKSDCoordinateSystem('PIVOT', pivotaxes, Array[float]([pitchoffsetX + a[0], pitchoffsetZ + a[1]]))
        # HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = pitchoffset + a[0]
        # HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')

        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', startangle + targetpitchangle, Motion.AxisMotionSpeeds.Normal, True)
        pow = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal')   # since we are aligned to channel 8 from the previous step
        # move to zero
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', startangle, Motion.AxisMotionSpeeds.Normal, True)
        return pow

    # connect the call back function
    pitchpivotsearch.EvalFunction = Func[Array[float], float](EvalPivot)

    # start the pitch pivot point search
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Searching for pitch pivot point.')

    # start alignment
    pitchpivotsearch.ExecuteNoneModal()

    # check status
    if not pitchpivotsearch.IsSuccess or SequenceObj.Halt:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Pitch pivot seearch failed.')
        return 0

    # move back to pre-scan position
    # HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Normal, True)
    # readjust the pivot point
    # HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] + safegap
    # enable the new pivot point
    HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')
    # retrieve the new pivot point and save to data
    pivot = HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint
    TestResults.AddTestResult('Pitch_Pivot_X', HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'])

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# BalanceDryAlignment
# Balanced dry alignment using Hexapod only
#-------------------------------------------------------------------------------
def BalanceDryAlignmentHexapod(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # retreive zero position
    zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
    # move back to zero position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Normal, True)

    # get the alignment algorithms
    hscan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')

    hscan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    hscan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    hscan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    hscan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    hscan.ExecuteOnce = SequenceObj.AutoStep

    # set up a loop to zero in on the roll angle
    width = TestResults.RetrieveTestResult('Outer_Channels_Width')
    retries = 0

    while retries < 3 and not SequenceObj.Halt:

        # start the algorithms
        hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
        hscan.Channel = 1
        hscan.ExecuteNoneModal()
        # check scan status
        if hscan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # wait to settle
        Utility.DelayMS(500)

        # remember the final position
        topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # repeat scan for the second channel
        hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
        hscan.Channel = 2

        # start the algorithms again
        hscan.ExecuteNoneModal()
        # check scan status
        if hscan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # wait to settle
        Utility.DelayMS(500)

        # get the final position of second channel
        bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # double check and readjust roll if necessary
        # calculate the roll angle
        h = Math.Atan(Math.Abs(topchanpos[1] - bottomchanpos[1]))
        if h < 1:
           break    # we achieved the roll angle when the optical Z difference is less than 1 um

        # calculate the roll angle
        r = Utility.RadianToDegree(Math.Atan(h / width))
        rollangle = -r
        if topchanpos[2] > bottomchanpos[2]:
           rollangle = -rollangle

        # adjust the roll angle again
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)

        retries += 1

    if retries >= 3 or SequenceObj.Halt:
       return 0

    # balanced position
    ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
    zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

    # record the final dry align hexapod position
    hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('Dry_Align_Hexapod_X', hposition[0])
    TestResults.AddTestResult('Dry_Align_Hexapod_Y', hposition[1])
    TestResults.AddTestResult('Dry_Align_Hexapod_Z', hposition[2])
    TestResults.AddTestResult('Dry_Align_Hexapod_U', hposition[3])
    TestResults.AddTestResult('Dry_Align_Hexapod_V', hposition[4])
    TestResults.AddTestResult('Dry_Align_Hexapod_W', hposition[5])

    # save powers
    toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
        power = pm. ReadPowers()
        toppow = power.Item2[0]
        bottompow = power.Item2[1]

    # save process values
    TestResults.AddTestResult('Dry_Align_Power_Top_Outer_Chan', toppow)
    TestResults.AddTestResult('Dry_Align_Power_Bottom_Outer_Chan', bottompow)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# BalanceDryAlignment
# Balanced dry alignment using Nanocube
#-------------------------------------------------------------------------------
def BalanceDryAlignmentNanocube(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # retreive zero position
    zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
    # move back to zero position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Normal, True)

    # here we do channel balance with Nanocube 2D scan
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeRasterScan')
    climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')

    # get nanocube scan parameters
    scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis1').DataItem
    scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis2').DataItem
    # we are working in um when dealing with Nanocube
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanRange1').DataItem * 1000
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanRange2').DataItem * 1000
    # start at the middle position
    scan.Axis1Position = 50
    scan.Axis2Position = 50
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanVelocity').DataItem * 1000
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanFrequency').DataItem
    scan.ExecuteOnce = SequenceObj.AutoStep

    climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis1').DataItem
    climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis2').DataItem
    climb.ExecuteOnce = SequenceObj.AutoStep

    # set up a loop to zero in on the roll angle
    width = TestResults.RetrieveTestResult('Outer_Channels_Width')
    topchanpos = [ 50.0, 50.0, 50.0 ]
    bottomchanpos = [ 50.0, 50.0, 50.0 ]
    retries = 0

    while retries < 5 and not SequenceObj.Halt:

        # start the algorithms
        scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
        scan.Channel = 1
        climb.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
        climb.Channel = 1
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        #climb.ExecuteNoneModal()
        # check climb status
        #if scan.IsSuccess == False or SequenceObj.Halt:
        #    return 0

        # remember the final position
        topchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

        # repeat scan for the second channel
        scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
        scan.Channel = 2
        climb.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
        climb.Channel = 2

        # start the algorithms again
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        #climb.ExecuteNoneModal()
        # check climb status
        #if scan.IsSuccess == False or SequenceObj.Halt:
        #    return 0

        # get the final position of second channel
        bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

        # double check and readjust roll if necessary
        # calculate the roll angle
        h = Math.Atan(Math.Abs(topchanpos[1] - bottomchanpos[1]))
        if h < 1:
           break    # we achieved the roll angle when the optical Z difference is less than 1 um

        # calculate the roll angle
        r = Utility.RadianToDegree(Math.Atan(h / width))
        rollangle = -r
        if topchanpos[2] > bottomchanpos[2]:
           rollangle = -rollangle

        # adjust the roll angle again
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)

        retries += 1

    if retries >= 5 or SequenceObj.Halt:
       return 0

    # balanced position
    middle = (topchanpos[2] + bottomchanpos[2]) / 2

    # log the aligned position 
    TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_X', topchanpos[0])
    TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_Y', topchanpos[1])
    TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_Z', topchanpos[2])
    TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_X', bottomchanpos[0])
    TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_Y', bottomchanpos[1])
    TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_Z', bottomchanpos[2])
	# balance the Z (side to side) distance
    HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', middle, Motion.AxisMotionSpeeds.Normal, True)

    # record the final dry align hexapod position
    hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('Dry_Align_Hexapod_X', hposition[0])
    TestResults.AddTestResult('Dry_Align_Hexapod_Y', hposition[1])
    TestResults.AddTestResult('Dry_Align_Hexapod_Z', hposition[2])
    TestResults.AddTestResult('Dry_Align_Hexapod_U', hposition[3])
    TestResults.AddTestResult('Dry_Align_Hexapod_V', hposition[4])
    TestResults.AddTestResult('Dry_Align_Hexapod_W', hposition[5])

    # record the final dry align nanocube position
    nposition = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
    TestResults.AddTestResult('Dry_Align_Nanocube_X', nposition[0])
    TestResults.AddTestResult('Dry_Align_Nanocube_Y', nposition[1])
    TestResults.AddTestResult('Dry_Align_Nanocube_Z', nposition[2])

    # save powers
    toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
        power = pm. ReadPowers()
        toppow = power.Item2[0]
        bottompow = power.Item2[1]

    # save process values
    TestResults.AddTestResult('Dry_Align_Power_Top_Outer_Chan', toppow)
    TestResults.AddTestResult('Dry_Align_Power_Bottom_Outer_Chan', bottompow)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# ApplyEpoxy
# Manually apply epoxy and establish contact point
#-------------------------------------------------------------------------------
def ApplyEpoxy(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # Ask operator to apply epoxy. Use automation later
    if not LogHelper.AskContinue('Apply epoxy. Click Yes when done.'):
        return 0

    # open to whet epoxy
    whetgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetGap').DataItem
    # move to epoxy whet position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -whetgap, Motion.AxisMotionSpeeds.Slow, True)
    # wait a few seconds
    Utility.DelayMS(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetTime').DataItem)
    # back to zero position
    zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Slow, True)

    # do a contact to establish True bond gap
    # start move incrementally until force sensor detect contact
    # first zero out the force sensr
    HardwareFactory.Instance.GetHardwareByName('Hexapod').ZeroForceSensor()
    # get initial force
    forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
    startforce = forcesensor.ReadValueImmediate()
    # start force monitor
    threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
    backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
    bondgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyBondGap').DataItem
    # Monitor force change
    while (forcesensor.ReadValueImmediate() - startforce) < threshold:
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
        Utility.DelayMS(5)
        # check for user interrupt
        if SequenceObj.Halt:
            return 0

    # found contact point, back off set amount
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
    # put the required bondgap
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

    TestResults.AddTestResult('Optical_Z_UC_Cure_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# BalanceWedAlignment
# Balance alignment of the channels in epoxy using Hexapod only
#-------------------------------------------------------------------------------
def BalanceWedAlignmentHexapod(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # get the alignment algorithms
    hscan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')

    hscan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    hscan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    hscan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    hscan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    hscan.ExecuteOnce = SequenceObj.AutoStep

    # set up a loop to zero in on the roll angle
    width = TestResults.RetrieveTestResult('Outer_Channels_Width')
    retries = 0

    while retries < 3 and not SequenceObj.Halt:

        # start the algorithms
        hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
        hscan.Channel = 1
        hscan.ExecuteNoneModal()
        # check scan status
        if hscan.IsSuccess == False or SequenceObj.Halt:
            return 0

         # wait to settle
        Utility.DelayMS(500)

        # remember the final position
        topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # repeat scan for the second channel
        hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
        hscan.Channel = 2

        # start the algorithms again
        hscan.ExecuteNoneModal()
        # check scan status
        if hscan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # wait to settle
        Utility.DelayMS(500)

        # get the final position of second channel
        bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # double check and readjust roll if necessary
        # calculate the roll angle
        h = Math.Atan(Math.Abs(topchanpos[1] - bottomchanpos[1]))
        if h < 1:
           break    # we achieved the roll angle when the optical Z difference is less than 1 um

        # calculate the roll angle
        r = Utility.RadianToDegree(Math.Atan(h / width))
        rollangle = -r
        if topchanpos[2] > bottomchanpos[2]:
           rollangle = -rollangle

        # adjust the roll angle again
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)

        retries += 1
    
    # check stop conditions
    if retries >= 3 or SequenceObj.Halt:
       return 0

    # balanced position
    ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
    zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

    # record final wet align hexapod position
    hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('Wet_Align_Hexapod_X', hposition[0])
    TestResults.AddTestResult('Wet_Align_Hexapod_Y', hposition[1])
    TestResults.AddTestResult('Wet_Align_Hexapod_Z', hposition[2])
    TestResults.AddTestResult('Wet_Align_Hexapod_U', hposition[3])
    TestResults.AddTestResult('Wet_Align_Hexapod_V', hposition[4])
    TestResults.AddTestResult('Wet_Align_Hexapod_W', hposition[5])

    # save powers
    toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
        power = pm. ReadPowers()
        toppow = power.Item2[0]
        bottompow = power.Item2[1]

    # save process values
    TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan', toppow)
    TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan', bottompow)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# BalanceWedAlignment
# Balance alignment of the channels in epoxy using Nanocube
#-------------------------------------------------------------------------------
def BalanceWedAlignmentNanoCube(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # here we do channel balance with Nanocube 2D scan
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeRasterScan')
    climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')

    # we don't need to reload the scan parameters since they haven't changed
    # set up a loop to zero in on the roll angle
    width = TestResults.RetrieveTestResult('Outer_Channels_Width')
    topchanpos = [ 50.0, 50.0, 50.0 ]
    bottomchanpos = [ 50.0, 50.0, 50.0 ]
    retries = 0

    while retries < 5 and not SequenceObj.Halt:

        # start the algorithms
        scan.Channel = 1
        climb.Channel = 1
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        #climb.ExecuteNoneModal()
        # check climb status
        #if scan.IsSuccess == False or SequenceObj.Halt:
        #    return 0

        # remember the final position
        topchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

        # repeat scan for the second channel
        scan.Channel = 2
        climb.Channel = 2
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        #climb.ExecuteNoneModal()
        # check climb status
        #if scan.IsSuccess == False or SequenceObj.Halt:
        #    return 0

        # get the final position of second channel
        bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

        # double check and readjust roll if necessary
        # calculate the roll angle
        h = Math.Atan(Math.Abs(topchanpos[1] - bottomchanpos[1]))
        if h < 1:
           break    # we achieved the roll angle when the optical Z difference is less than 1 um

        # calculate the roll angle
        r = Utility.RadianToDegree(Math.Atan(h / width))
        rollangle = -r
        if topchanpos[2] > bottomchanpos[2]:
           rollangle = -rollangle

        # adjust the roll angle again
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)

        retries += 1
    
    # check stop conditions
    if retries >= 5 or SequenceObj.Halt:
       return 0

    # balanced position
    middle = (topchanpos[2] + bottomchanpos[2]) / 2

    # log the aligned position 
    TestResults.AddTestResult('Top_Channel_Wet_Align_Nanocube_X', topchanpos[0])
    TestResults.AddTestResult('Top_Channel_Wet_Align_Nanocube_Y', topchanpos[1])
    TestResults.AddTestResult('Top_Channel_Wet_Align_Nanocube_Z', topchanpos[2])
    TestResults.AddTestResult('Bottom_Channel_Wet_Align_Nanocube_X', bottomchanpos[0])
    TestResults.AddTestResult('Bottom_Channel_Wet_Align_Nanocube_Y', bottomchanpos[1])
    TestResults.AddTestResult('Bottom_Channel_Wet_Align_Nanocube_Z', bottomchanpos[2])

    # record final wet align hexapod position
    hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('Wet_Align_Hexapod_X', hposition[0])
    TestResults.AddTestResult('Wet_Align_Hexapod_Y', hposition[1])
    TestResults.AddTestResult('Wet_Align_Hexapod_Z', hposition[2])
    TestResults.AddTestResult('Wet_Align_Hexapod_U', hposition[3])
    TestResults.AddTestResult('Wet_Align_Hexapod_V', hposition[4])
    TestResults.AddTestResult('Wet_Align_Hexapod_W', hposition[5])

    # record the final wet align nanocube position
    nposition = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
    TestResults.AddTestResult('Wet_Align_Nanocube_X', nposition[0])
    TestResults.AddTestResult('Wet_Align_Nanocube_Y', nposition[1])
    TestResults.AddTestResult('Wet_Align_Nanocube_Z', nposition[2])

    # balance the Z (side to side) distance
    HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', (topchanpos[2] + bottomchanpos[2]) / 2, Motion.AxisMotionSpeeds.Normal, True)

        # save powers
    toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
        power = pm. ReadPowers()
        toppow = power.Item2[0]
        bottompow = power.Item2[1]

    # save process values
    TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan', toppow)
    TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan', bottompow)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# UVCure
# UV cure the epoxy bond
#-------------------------------------------------------------------------------
def UVCure(StepName, SequenceObj, TestMetrics, TestResults):

    loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem
    uvposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UVPresetPosition').DataItem
    # move UV wands into position
    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(uvposition)

    # get the uv profile
    profile = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UVCureStepProfiles').DataItem
    # this is a hack, here we sum up the time of all the steps
    # and display count down timer
    uvtime = sum(map(lambda x: float(x.split(':')[0]), TestMetrics.GetTestMetricItem('UVCureStepProfiles', profile).DataItem.split(',')))
    # log the profile used
    TestResults.AddTestResult('UV_Cure_Profile', profile)
    
    # create collection to track UV power
    UVPowerTracking = List[Array[float]]()
    stopwatch = Stopwatch()
    stopwatch.Start()

    # create the delegate for the UV cure function
    def LogPower(i):
        UVPowerTracking.Add(Array[float]([round(float(stopwatch.ElapsedMilliseconds) / 1000, 1), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 5), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 5)]))
        Utility.ShowProcessTextOnMainUI('UV cure time ' + str(uvtime - int(stopwatch.ElapsedMilliseconds / 1000)) + ' seconds remaining.')

    # start UV exposure
    ret = HardwareFactory.Instance.GetHardwareByName('UVSource').StartStepUVExposures(TestMetrics.GetTestMetricItem('UVCureStepProfiles', profile).DataItem, '', Action[int](LogPower))

    # stop timer when UV done
    stopwatch.Stop()

    # save powers
    toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
        power = pm. ReadPowers()
        toppow = power.Item2[0]
        bottompow = power.Item2[1]

    # save process values
    TestResults.AddTestResult('Post_UV_Cure_Power_Top_Outer_Chan', toppow)
    TestResults.AddTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan', bottompow)

    # retrieve dry align power
    bottompowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')
    toppowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')

    # save process values
    TestResults.AddTestResult('Post_UV_Cure_Power_Top_Outer_Chan_Loss', round(toppowinput - toppow, 6))
    TestResults.AddTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan_Loss', round(bottompowinput - bottompow, 6))
    
    # save the power tracking to a file
    # save uv cure power tracking
    TestResults.SaveArrayResultsToStorage(TestResults.RetrieveTestResult('Assembly_SN'), 'UVCureChannelPowers', 'Elapsed Time(s),Top Chan Signal(V),Bottom Chan Signal(V)', UVPowerTracking)
    Utility.ShowProcessTextOnMainUI()

    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)

    if not ret or SequenceObj.Halt:
        return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Unload
# Release gripper and unload FAU
#-------------------------------------------------------------------------------
def UnloadFAU(StepName, SequenceObj, TestMetrics, TestResults):


    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # Get the preset position names from recipe
    loadpos = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #BoardLoad
    laserfauvacuumport = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserFAUVaccumPortName').DataItem
    pmfauvacuumport = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PowerMeterFAUVaccumPortName').DataItem

    # move things out of way for operator to load stuff
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadpos)
    
    # here we need to turn off the vacuum and do some other unload related sequences. 
    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(laserfauvacuumport, False)
    
    # wait for a second for the vacuum to release
    Utility.DelayMS(1000)

    # get power based on instrument    
    toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
        toppower = pm.ReadPowers().Item2[0]
        bottompower = pm.ReadPowers().Item2[1]

    # save process values
    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan', toppower)
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan', bottompower)

    # Ask operator to unfasten the board brace
    if not LogHelper.AskContinue('Release the laser side fiber clamps. Power meter side fiber vacuum will release automatically when this dialog box closes. Click Yes when done, No to abort. '):
        return 0

    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(pmfauvacuumport, False)
    TestResults.AddTestResult('End_Time', DateTime.Now)

    if SequenceObj.Halt:
        return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Unload
# Release gripper and unload die
#-------------------------------------------------------------------------------
def UnloadDie(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # save powers
    toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
        power = pm. ReadPowers()
        toppow = power.Item2[0]
        bottompow = power.Item2[1]

    # save process values
    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan', toppow)
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan', bottompow)

    # retrieve dry align power
    bottompowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')
    toppowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')

    # save process values
    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan_Loss', round(toppowinput - toppow, 6))
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan_Loss', round(bottompowinput - bottompow, 6))

    # Get the preset position names from recipe
    loadpos = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #BoardLoad
    probeposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ProbePresetPosition').DataItem #'BoardLoad'
    fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem
    dievac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'TargetVaccumPortName').DataItem

    # move things out of way for operator to load stuff
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(probeposition)
    
    # Ask operator to adjust probe
    if not LogHelper.AskContinue('Raise the probe before unload. Click Yes when done, No to abort.'):
        return 0

    # Ask operator to unfasten the board brace
    if not LogHelper.AskContinue('Remove the fiber clamps. Click Yes when done, No to abort. Vacuum will release automatically.'):
        return 0

    # here we need to turn off the vacuum and do some other unload related sequences. 
    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
    
    # wait for a second for the vacuum to release
    Utility.DelayMS(1000)

    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)
    
    # wait for a second for the vacuum to release
    Utility.DelayMS(1000)

    # get power based on instrument    
    toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
        toppower = pm.ReadPowers().Item2[0]
        bottompower = pm.ReadPowers().Item2[1]

    # save process values
    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan', toppower)
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan', bottompower)

    TestResults.AddTestResult('End_Time', DateTime.Now)

    if SequenceObj.Halt:
        return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Unload
# Release gripper and unload die
#-------------------------------------------------------------------------------
def UnloadBoard(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # save powers
    toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
        power = pm. ReadPowers()
        toppow = power.Item2[0]
        bottompow = power.Item2[1]

    # save process values
    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan', toppow)
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan', bottompow)

    # retrieve dry align power
    bottompowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')
    toppowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')

    # save process values
    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan_Loss', round(toppowinput - toppow, 6))
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan_Loss', round(bottompowinput - bottompow, 6))

    # Get the preset position names from recipe
    unloadpos = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UnloadPresetPosition').DataItem #BoardLoad
    probeposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ProbePresetPosition').DataItem #'BoardLoad'
    fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem
    boardvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BoardVaccumPortName').DataItem

    # move things out of way for operator to load stuff
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(probeposition)   
    
    # Ask operator to unfasten the board brace
    if not LogHelper.AskContinue('Disconnect the MPO. Click Yes when done, No to abort. Vacuum will release automatically.'):
        return 0

    # here we need to turn off the vacuum and do some other unload related sequences. 
    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
       
    # wait for a second for the vacuum to release
    Utility.DelayMS(5000)

    # Ask operator to adjust probe
    if not LogHelper.AskContinue('Raise the probe and release board clamp. Click Yes when done, No to abort.'):
        return 0

    # here we lower the board fixture platform
    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(boardvac, False)

    # wait for a second for the vacuum to release
    Utility.DelayMS(5000)

    # move hexapod to unload position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(unloadpos)

    TestResults.AddTestResult('End_Time', DateTime.Now)

    if SequenceObj.Halt:
        return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1


#-------------------------------------------------------------------------------
# Finalize
# Save data to the file
#-------------------------------------------------------------------------------
def Finalize(StepName, SequenceObj, TestMetrics, TestResults):

    # get process values
    inputtop = TestResults.RetrieveTestResult('Optical_Input_Power_Top_Outer_Chan')
    inputbottom = TestResults.RetrieveTestResult('Optical_Input_Power_Bottom_Outer_Chan')
    drytop = TestResults.RetrieveTestResult('Dry_Align_Power_Top_Outer_Chan')
    drybottom = TestResults.RetrieveTestResult('Dry_Align_Power_Bottom_Outer_Chan')
    wettop = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')
    wetbottom = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')
    uvtop = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Top_Outer_Chan')
    uvbottom = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan')
    releasetop = TestResults.RetrieveTestResult('Post_Release_Power_Top_Outer_Chan')
    releasebottom = TestResults.RetrieveTestResult('Post_Release_Power_Bottom_Outer_Chan')

    # save process values
    TestResults.AddTestResult('Dry_Align_Power_Top_Outer_Chan_Loss', round(inputtop - drytop, 6))
    TestResults.AddTestResult('Dry_Align_Power_Bottom_Outer_Chan_Loss', round(inputbottom - drybottom, 6))

    TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan_Loss', round(drytop - wettop, 6))
    TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan_Loss', round(drybottom - wetbottom, 6))

    TestResults.AddTestResult('Post_UV_Cure_Power_Top_Outer_Chan_Loss', round(wettop - uvtop, 6))
    TestResults.AddTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan_Loss', round(wetbottom - uvbottom, 6))

    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan_Loss', round(uvtop - releasetop, 6))
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan_Loss', round(uvbottom - releasebottom, 6))

    #check user comment
    if TestResults.IsTestResultExists('Comment') == False:
        if Station.Instance.UserComment:
            TestResults.AddTestResult('Comment', Station.Instance.UserComment)
    else:
        if Station.Instance.UserComment:
            TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult('Comment') + ' ' + Station.Instance.UserComment)
        else:
            TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult('Comment'))

    #save the data file
    TestResults.SaveTestResultsToStorage(TestResults.RetrieveTestResult('Assembly_SN'))

    return 1



