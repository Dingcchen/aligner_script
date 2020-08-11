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
import math as math
from System.Diagnostics import Stopwatch
from System.Collections.Generic import List
clr.AddReferenceToFile('HAL.dll')
from HAL import Motion
from HAL import HardwareFactory
from HAL import HardwareInitializeState
from HAL.SourceController import ScrambleMethodType
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoAligner.exe')
from CiscoAligner import PickAndPlace
from CiscoAligner import Station
from CiscoAligner import Alignments
from time import sleep
import csv
from AlignerUtil import * 
from datetime import datetime


UseOpticalSwitch = True


def Template(StepName, SequenceObj, TestMetrics, TestResults):
	# DO NOT DELETE THIS METHOD
	# This is the method pattern for all python script called by AutomationCore PythonScriptManager.
	# The method arguments must be exactly as shown. They are the following:
	# SequenceName: This is the name of the process sequence that owns this step. This is required for retrieving process recipe values.
	# StepName: This is the name of the step that invokes this step. Useful for log entry and alerts to user.
	# TestMetrics: The object that holds all the process recipe values. See the C# code for usage.
	# TestResults: The object that stores all process result values. See the C# code for usage.

	TestResults.ClearAllTestResult()
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
	# for quick test.
	# IOController.SetOutputValue('OpticalSwitch', False)
	# AreaScan('NanocubeSpiralCVScan', SequenceObj, TestMetrics, TestResults)
	# return 1
	alignment_results = {}

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# clear the output data
	TestResults.ClearAllTestResult()
	Utility.ShowProcessTextOnMainUI() # clear message

	TestResults.AddTestResult('Start_Time', DateTime.Now)
	alignment_results['Start_Time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
	TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
	alignment_results['Operator'] = UserManager.CurrentUser.Name
	TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())
	alignment_results['Software_Version'] = Utility.GetApplicationVersion()
	
	# turn on coax lights on lenses and turn off side backlight
	IOController.SetOutputValue('DownCamCoaxialLight', True)
	IOController.SetOutputValue('SideCamCoaxialLight', True)
	IOController.SetOutputValue('SideCamBacklight', False)
	
	#HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute(['X', 'Y', 'Z'], [50, 50, 50], Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
	
	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	return 1


#-------------------------------------------------------------------------------
# CheckProbe
# Ask the user to visually check probe contact to the die
#-------------------------------------------------------------------------------
def CheckProbe(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)

	probeposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ProbePresetPosition').DataItem #'BoardLoad'
	initialposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
	
	IOController.GetHardwareStateTree().ActivateState(probeposition)
	
	# set exposure
	# HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(15)

	# move things out of way for operator to load stuff
	HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(probeposition)
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(probeposition)
	
	HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(probeposition)
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(probeposition)

	#Ask operator to adjust probe
	if LogHelper.AskContinue('Adjust probe until pins are in contact with pads. Click Yes when done, No to abort.') == False:
		return 0

	# go back to initial position
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)
	if not save_alignment_results(SequenceObj, alignment_results):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return 1
		
def SnapDieText(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	probeposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ProbePresetPosition').DataItem #'BoardLoad'
	die_text_position = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'die_text_position').DataItem #'FAUToBoardInitial'
	
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(die_text_position)
	
	# set exposure
	# HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(15)

	# move things out of way for operator to load stuff
	HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(probeposition)
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(probeposition)
	
	HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(probeposition)
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(probeposition)
	
	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTopText.jpg')
	HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# go back to initial position
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return 1

#-------------------------------------------------------------------------------
# FindSubmount
# Use vision to find the location of the die
#-------------------------------------------------------------------------------
def SetFirstLightPositionToFAU(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	# define vision tool to use for easier editing
	pmfautopvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PowermeterFAUDownVisionTool').DataItem #'DieTopGF2NoGlassBlock'
	laserfautopvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserFAUDownVisionTool').DataItem #"MPOTop_2_7"
	pmfausidevision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PowermeterFAUSideVisionTool').DataItem #'DieSideGF2NoGlassBlock'
	laserfausidevision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserFAUSideVisionTool').DataItem #'MPOSideNormal'
	fautopexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUDownVisionCameraExposure').DataItem #5
	fausideexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionCameraExposure').DataItem #5
	initialposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'

	# Move hexapod to root coordinate system
	Hexapod.EnableZeroCoordinateSystem()

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# move camera to preset position
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)

	# Get hexapod preset position from recipe and go there
	Hexapod.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0

	# set the hexapod pivot point for this process
	initpivot = list(map(lambda x: float(x), TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPivotPoint').DataItem.split(',')))
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

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
	res = MachineVision.RunVisionTool(pmfautopvision)

	# check result
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the powermeter FAU top position.')
		return 0

	inputx = res['X']
	inputy = res['Y']
	inputangle = Utility.RadianToDegree(res['Angle'])

	# one more time for the laser side
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	res = MachineVision.RunVisionTool(laserfautopvision)

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
	Hexapod.MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# move Y first
	if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	if SequenceObj.Halt:
		return 0

	Utility.DelayMS(500)

	# re-take laser side
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	res = MachineVision.RunVisionTool(laserfautopvision)

	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
		return 0

	# retreive vision results
	outputangle = Utility.RadianToDegree(res['Angle'])

	# do angle adjustment one more time
	Hexapod.MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)
	# vision top once more
	# re-take laaser side
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	res = MachineVision.RunVisionTool(laserfautopvision)

	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
		return 0

	# retreive vision results
	outputx = res['X']
	outputy = res['Y']
	outputx2 = res['X2']
	outputy2 = res['Y2']

	# adjust the translation
	# dest = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))
	end = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

	# calculate the distance between the first and last fiber channel in order to do pivot angle compensation
	TestResults.AddTestResult('Outer_Channels_Width', Math.Round(Math.Sqrt(Math.Pow(end.Item1 - start.Item1, 2) + pow(end.Item2 - start.Item2, 2)), 5))

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)

	if SequenceObj.Halt:
		return 0

	# start the translational motion again
	# first move in Y
	if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	# move in x, but with 200um gap remain
	if not Hexapod.MoveAxisRelative('X', dest.Item1 - start.Item1 - 0.2, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0

	if SequenceObj.Halt:
		return 0

	# re-do vision one more time at close proximity to achieve better initial alignment
	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# run vision
	res = MachineVision.RunVisionTool(pmfautopvision)

	# check result
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the powermeter FAU top position.')
		return 0

	inputx = res['X']
	inputy = res['Y']

	# one more time for the laser side
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	res = MachineVision.RunVisionTool(laserfautopvision)

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
	dest = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# start the translational motion again
	# first move in Y
	if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	# move in x, but with 100um gap remain
	if not Hexapod.MoveAxisRelative('X', dest.Item1 - start.Item1 - 0.1, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0

	if SequenceObj.Halt:
		return 0

	# do a FAU contact detection to set the actual gap
	# start move incrementally until force sensor detect contact
	# first zero out the force sensr
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
	backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
	farfieldgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FarFieldGap').DataItem
	# Monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		Utility.DelayMS(5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	# contact, open up the gap
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# set this position as the zero position
	TestResults.AddTestResult('Optical_Z_Zero_Position', Hexapod.GetAxisPosition('X'))
	# set far field gap for first light alignment
	Hexapod.MoveAxisRelative('X', -farfieldgap, Motion.AxisMotionSpeeds.Normal, True)


	# Side view to adjust FAU relative heights
	HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(initialposition)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(fausideexposure)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
	res = MachineVision.RunVisionTool(laserfausidevision)
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU side position.')
		return 0

	laserangle = Utility.RadianToDegree(res['Angle'])

	# find the mpo side
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
	res = MachineVision.RunVisionTool(pmfausidevision)
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the powermeter FAU side position.')
		return 0

	pmx = res['X']
	pmy = res['Y']
	pmangle = Utility.RadianToDegree(res['Angle'])

	# adjust the yaw angle
	Hexapod.MoveAxisRelative('V', laserangle - pmangle, Motion.AxisMotionSpeeds.Normal, True)

	# find the laser FAU again for translational adjustment
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
	res = MachineVision.RunVisionTool(laserfausidevision)
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
	dest = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](pmx, pmy))
	start = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](laserx, lasery))

	# move the mpo height to match that of the die height plus whatever offset from recipe
	zoffset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightZOffsetFromVision').DataItem

	if not Hexapod.MoveAxisRelative('Z', dest.Item2 - start.Item2 + zoffset, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move laser FAU to match powermeter FAU height position.')
		return 0

	if not AlignerUtil.save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
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
	alignment_results = load_alignment_results(SequenceObj)
	def vision_FAU_top():
		sleep(0.5)
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUTopVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUTopVisionCameraExposure').DataItem #4
		#IOController.SetOutputValue('DownCamCoaxialLight', True)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(exposure)
		IOController.GetHardwareStateTree().ActivateState('FAU_top')
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
		return MachineVision.RunVisionTool(vision)
	 
	def vision_die_top():
		DieTopIOPreset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopIOPreset').DataItem 
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopVisionCameraExposure').DataItem #4
		#IOController.SetOutputValue('DownCamCoaxialLight', False)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		IOController.GetHardwareStateTree().ActivateState('GF7_Die9_top')
		HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(exposure)
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
		return MachineVision.RunVisionTool(vision)
		
	def vision_die_side():
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieSideVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieSideVisionCameraExposure').DataItem #4
		IOController.SetOutputValue('SideCamCoaxialLight', False)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(exposure)
		IOController.SetOutputValue('SideCamBacklight', True)
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
		#IOController.SetOutputValue('SideCamBacklight', False)
		return MachineVision.RunVisionTool(vision)

	def vision_FAU_side():
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionCameraExposure').DataItem #4
		IOController.SetOutputValue('SideCamCoaxialLight', False)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(exposure)
		IOController.SetOutputValue('SideCamBacklight', True)
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
		#IOController.SetOutputValue('SideCamBacklight', False)
		#HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		return MachineVision.RunVisionTool(vision)
	
	def fix_angle(input_angle, expected_angle):
		while (input_angle - expected_angle) > 90:
			input_angle -= 180
		while (input_angle - expected_angle) < 90:
			input_angle += 180
		return input_angle
		
	
	# define vision tool to use for easier editing
	initialposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
	#'FAUToBoardInitial'
	safe_approach = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'vision_align_safe_approach').DataItem #'FAUToBoardInitial'
	die_side_position = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieFocusedPresetPosition').DataItem #'FAUToBoardInitial'
	
	#vision_interim_gap_X = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionInterimGapX').DataItem #'FAUToBoardInitial'
	
	# Move hexapod to root coordinate system
	Hexapod.EnableZeroCoordinateSystem()
	
	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
	
	## turn on coax lights on lenses and turn off side backlight
	IOController.SetOutputValue('DownCamCoaxialLight', False)
	IOController.SetOutputValue('SideCamCoaxialLight', True)
	IOController.SetOutputValue('SideCamBacklight', False)

	# move cameras to preset position
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(initialposition)

	# Get hexapod and camera stage preset positions from recipe and go there
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)
	Hexapod.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0

	# set the hexapod pivot point for this process
	initpivot = list(map(lambda x: float(x), TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPivotPoint').DataItem.split(',')))
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	#turn off all lights and then set to recipe level
	HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTop.jpg')
	HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

	# run vision
	#####res = MachineVision.RunVisionTool(topdievision)
	die_res = vision_die_top()
	if die_res['Result'] != 'Success': # check result
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		return 0

	if safe_approach:
		if not LogHelper.AskContinue('Did the vision system correctly identify the die?'):
			return 0

	inputx = die_res['X']
	inputy = die_res['Y']
	die_angle = fix_angle(Utility.RadianToDegree(die_res['Angle']),90)

	# one more time for the MPO side
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	outputx = res['X']
	outputy = res['Y']
	FAU_front_face_angle = fix_angle(Utility.RadianToDegree(res['Angle']),90) ### NK 2020-06-29
	FAU_top_fiber_angle = fix_angle(Utility.RadianToDegree(res['top_fiber_angle']),0)
	FAU_bottom_fiber_angle = fix_angle(Utility.RadianToDegree(res['bottom_fiber_angle']),0)
	
	# calculate and record fiber endface to FAU angle error for top fiber
	FAU_top_fiber_to_face_angle_err_deg = FAU_front_face_angle - 90 - FAU_top_fiber_angle
	TestResults.AddTestResult('FAU_top_fiber_to_face_angle_err_deg', round(FAU_top_fiber_to_face_angle_err_deg, 5))
	
	# calculate and record fiber endface to FAU angle error for bottom fiber
	FAU_bottom_fiber_to_face_angle_err_deg = FAU_front_face_angle - 90 - FAU_top_fiber_angle
	TestResults.AddTestResult('FAU_bottom_fiber_to_face_angle_err_deg', round(FAU_bottom_fiber_to_face_angle_err_deg, 5))
	
	align_FAU_angle = FAU_front_face_angle
	if TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Angle_align_using_fibers').DataItem:
		align_FAU_angle = FAU_top_fiber_angle + 90
		
	move_angle = (align_FAU_angle - die_angle)
		
	# adjust the yaw angle
	Hexapod.MoveAxisRelative('W', move_angle, Motion.AxisMotionSpeeds.Normal, True)

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# move Y first
	if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0
	Utility.DelayMS(500)

	if SequenceObj.Halt:
		return 0
	
	# re-do the vision again to have better initial angle placement
	
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	if safe_approach:
		if not LogHelper.AskContinue('Did the vision system correctly identify the FAU?'):
			return 0

	# retreive vision results
	outputx = res['X']
	outputy = res['Y']
	outputx2 = res['X2']
	outputy2 = res['Y2']

	# adjust the translation
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))
	end = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

	# calculate the distance between the first and last fiber channel in order to do pivot angle compensation
	TestResults.AddTestResult('Measured_Channel_Pitch', round(((end.Item1 - start.Item1)**2 + (end.Item2 - start.Item2)**2)**0.5, 5))
	

	if SequenceObj.Halt:
		return 0

	# resume the translational motion again
	# if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
	# 	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
	# 	return 0 

	# move in x, but with wider gap remaining
	hexapod = Hexapod
	# if not hexapod.MoveAxisRelative('X', dest.Item1 - start.Item1 - 0.02, Motion.AxisMotionSpeeds.Slow, True):
	if not hexapod.MoveAxisRelative('X', dest.Item1 - start.Item1 - TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionDryAlignGapX').DataItem, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0
	
	if SequenceObj.Halt:
		return 0

	# one more time for the FAU side   
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	#outputangle = Utility.RadianToDegree(res['Angle'])
	
	FAU_front_face_angle = fix_angle(Utility.RadianToDegree(res['Angle']),90) ### NK 2020-06-29
	FAU_top_fiber_angle = fix_angle(Utility.RadianToDegree(res['top_fiber_angle']),0)
	FAU_bottom_fiber_angle = fix_angle(Utility.RadianToDegree(res['bottom_fiber_angle']),0)
	
	# calculate and record fiber endface to FAU angle error for top fiber
	FAU_top_fiber_to_face_angle_err_deg = FAU_front_face_angle - 90 - FAU_top_fiber_angle
	TestResults.AddTestResult('FAU_top_fiber_to_face_angle_err_deg2', round(FAU_top_fiber_to_face_angle_err_deg, 5))
	
	# calculate and record fiber endface to FAU angle error for bottom fiber
	FAU_bottom_fiber_to_face_angle_err_deg = FAU_front_face_angle - 90 - FAU_top_fiber_angle
	TestResults.AddTestResult('FAU_bottom_fiber_to_face_angle_err_deg2', round(FAU_bottom_fiber_to_face_angle_err_deg, 5))
	
	align_FAU_angle = FAU_front_face_angle
	if TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Angle_align_using_fibers').DataItem:
		align_FAU_angle = FAU_top_fiber_angle + 90
		
	move_angle = (align_FAU_angle - die_angle)


	# adjust the yaw angle
	Hexapod.MoveAxisRelative('W', move_angle, Motion.AxisMotionSpeeds.Normal, True)


	inputx = die_res['X']
	inputy = die_res['Y']
	inputangle = Utility.RadianToDegree(die_res['Angle'])

	# one more time for the FAU side	
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position (639).')
		return 0

	outputx = res['X']
	outputy = res['Y']

	if SequenceObj.Halt:
		return 0

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# start the translational motion again
	# first move in Y
	if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	if SequenceObj.Halt:
		return 0

	# Start imaging from the side
	#######################################################################################################################
	#######################################################################################################################
	
	# find the die from side camera
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(die_side_position)

	res = vision_die_side()
	if res['Result'] != 'Success':
		# if unsuccessful try again - workaround for backlight delay not working
		res = vision_die_side()
		if res['Result'] != 'Success':
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die side position.')
			return 0

	diex = res['X']
	diey = res['Y']
	dieangle = Utility.RadianToDegree(res['Angle'])

	# find the FAU side
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(initialposition)
	
	res = vision_FAU_side()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU side position.')
		return 0

	mpox = res['WGX']
	mpoy = res['WGY']
	mpoangle = Utility.RadianToDegree(res['Angle'])

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](diex, diey))
	start = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](mpox, mpoy))

	# move the mpo height to match that of the die height, include the z-offset
	if not Hexapod.MoveAxisRelative('Z', dest.Item2 - start.Item2 + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightZOffsetFromVision').DataItem, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move MPO to match die height position.')
		return 0

	# adjust the yaw angle
	Hexapod.MoveAxisRelative('V', mpoangle - dieangle, Motion.AxisMotionSpeeds.Normal, True)

	# now move x to put the mpo to process distance from die
	#if not Hexapod.MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
	#	 LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
	#	 return 0

	if SequenceObj.Halt:
		return 0

	# remember this postion as optical z zero
	# if False: #Don't move in multiple axes at once for now as pivot point is not well-defined. Not even sure why this was here... NK 2020-06-17
	#	  # now move x to put the mpo to process distance from die
	#	  if not Hexapod.MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
	#		  LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
	#		  return 0

	#	  if SequenceObj.Halt:
	#		  return 0

	#	  # remember this postion as optical z zero
	#	  TestResults.AddTestResult('Optical_Z_Zero_Position', Hexapod.GetAxisPosition('X'))
	
	# Back to imaging the top
	#######################################################################################################################
	#######################################################################################################################
	die_res = vision_die_top()
	# check result
	if die_res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		return 0

	#die_angle = Utility.RadianToDegree(res['Angle'])
	die_angle = fix_angle(Utility.RadianToDegree(die_res['Angle']),90)

	if safe_approach:
		if not LogHelper.AskContinue('Did the vision system correctly identify the die?'):
			return 0
	
	# one more time for the FAU top
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	#outputangle = Utility.RadianToDegree(res['Angle'])
	
	FAU_front_face_angle = fix_angle(Utility.RadianToDegree(res['Angle']),90) ### NK 2020-06-29
	FAU_top_fiber_angle = fix_angle(Utility.RadianToDegree(res['top_fiber_angle']),0)
	FAU_bottom_fiber_angle = fix_angle(Utility.RadianToDegree(res['bottom_fiber_angle']),0)
	
	# calculate and record fiber endface to FAU angle error for top fiber
	FAU_top_fiber_to_face_angle_err_deg = FAU_front_face_angle - 90 - FAU_top_fiber_angle
	TestResults.AddTestResult('FAU_top_fiber_to_face_angle_err_deg3', round(FAU_top_fiber_to_face_angle_err_deg, 5))
	
	# calculate and record fiber endface to FAU angle error for bottom fiber
	FAU_bottom_fiber_to_face_angle_err_deg = FAU_front_face_angle - 90 - FAU_top_fiber_angle
	TestResults.AddTestResult('FAU_bottom_fiber_to_face_angle_err_deg3', round(FAU_bottom_fiber_to_face_angle_err_deg, 5))
	
	align_FAU_angle = FAU_front_face_angle
	if TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Angle_align_using_fibers').DataItem:
		align_FAU_angle = FAU_top_fiber_angle + 90
		
	move_angle = (align_FAU_angle - die_angle)
	
	# do angle adjustment one more time
	Hexapod.MoveAxisRelative('W', move_angle, Motion.AxisMotionSpeeds.Normal, True)
	
	###############################################################################################
	### NK Correct Y Position after all other motion because it is consistently off 01-Apr-2020
	if SequenceObj.Halt:
		return 0
	
	# re-do vision one more time at close proximity to achieve better initial alignment	   
	# res = vision_die_top()
	# if res['Result'] != 'Success':
		# LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		# return 0

	inputx = die_res['X']
	inputy = die_res['Y']
	inputangle = Utility.RadianToDegree(die_res['Angle'])

	# one more time for the FAU top
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	if safe_approach:
		if not LogHelper.AskContinue('Did the vision system correctly identify the FAU?'):
			return 0

	outputx = res['X']
	outputy = res['Y']

	if SequenceObj.Halt:
		return 0

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# start the translational motion again
	# move in Y
	y_offset_from_vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightYOffsetFromVision').DataItem
	if not Hexapod.MoveAxisRelative('Y', y_offset_from_vision + dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	# move to a location far enough for side view vision to work better
	# the light causes the die to bleed into the MPO
	processdist = dest.Item1 - start.Item1 - TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionDryAlignGapX').DataItem
	TestResults.AddTestResult('optical_z0', Hexapod.GetAxisPosition('X'))

	if not Hexapod.MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0
	
	TestResults.AddTestResult('optical_z0', Hexapod.GetAxisPosition('X') + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionDryAlignGapX').DataItem)
	
	TestResults.AddTestResult('vision_align_hexapod_final_X', Hexapod.GetAxisPosition('X'))
	TestResults.AddTestResult('vision_align_hexapod_final_Y', Hexapod.GetAxisPosition('Y'))
	TestResults.AddTestResult('vision_align_hexapod_final_Z', Hexapod.GetAxisPosition('Z'))
	TestResults.AddTestResult('vision_align_hexapod_final_U', Hexapod.GetAxisPosition('U'))
	TestResults.AddTestResult('vision_align_hexapod_final_V', Hexapod.GetAxisPosition('V'))
	TestResults.AddTestResult('vision_align_hexapod_final_W', Hexapod.GetAxisPosition('W'))
	
	IOController.GetHardwareStateTree().ActivateState('default')

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0
	
	if SequenceObj.Halt:
		return 0
	else:
		return 1

#-------------------------------------------------------------------------------
# FirstLightSearch
# First light alignment on the channels, no balance
# Note: This routine find power on top and bottom channels
#-------------------------------------------------------------------------------
def FirstLightSearchDualChannels(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	search_pos = Hexapod.GetAxesPositions()
	   
	# remember this postion as optical z zero
	# in case we aligned manually, get the z position here instead of previous step
	#TestResults.AddTestResult('Optical_Z_Zero_Position', Hexapod.GetAxisPosition('X'))
	
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
	
	if not ScramblePolarizationMPC201(SequenceObj):
		return 0

	# declare variables we will use
	retries = 0
	limit = 5
	
	#Ask operator to fire the lasers
	if LogHelper.AskContinue('Fire the lasers! Click Yes when done, No to abort.') == False:
		PolarizationControl.SetScrambleEnableState(False)
		return 0

	# get the hexapod alignment algorithm
	scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
	# Reload parameters from recipe file
	minpower = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ScanMinPowerThreshold').DataItem # this value will be in hexapod analog input unit. 
	scan.Axis1 = 'Y'
	scan.Axis2 = 'Z'
	scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange1').DataItem
	scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange2').DataItem
	scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanVelocity').DataItem
	scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanFrequency').DataItem
	# scan.Threshold = minpower # Volts
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1
	scan.ExecuteOnce = SequenceObj.AutoStep

	# one scan to get initial power
	#scan.ExecuteNoneModal()
	#if scan.IsSuccess == False or	SequenceObj.Halt:
	#	 return 0

	# wait to settle
	#Utility.DelayMS(500)

	topinitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
	if topinitpower < minpower:
		# do a few scans to make sure we are in the closest range possible
		while retries < limit:
			scan.ExecuteNoneModal()
			if scan.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch1 coarse scan failed!')
				return 0

			# wait to settle
			Utility.DelayMS(2000)

			# check return condition
			p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
			if p > topinitpower or abs(p - topinitpower) / abs(p) < 0.2:
				break  # power close enough, good alignment
			if p > topinitpower:
				topinitpower = p

			retries += 1
		
		if retries >= limit:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many retries.')
			return 0	# error condition

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
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch1 fine scan failed!')
		return 0

	# save top chan aligned position
	topchanpos = Hexapod.GetAxesPositions()


	SetScanChannel(scan, 2, UseOpticalSwitch)
	# scan.Channel = 2
	# one scan to get initial power
	scan.ExecuteNoneModal()
	if scan.IsSuccess == False or  SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch2 fine scan failed!')
		return 0
	# wait to settle
	#Utility.DelayMS(500)
	if UseOpticalSwitch:
		bottominitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
	else:	
		bottominitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
	retries = 0
	if bottominitpower < minpower:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to find min power on Ch2.')
		return 0
		
	# save bottom chan aligned position
	bottomchanpos = Hexapod.GetAxesPositions()

	
	
	if not Hexapod.MoveAxisAbsolute('Y', (topchanpos[1] + bottomchanpos[1])/2, Motion.AxisMotionSpeeds.Normal, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0
		
	if not Hexapod.MoveAxisAbsolute('Z', (topchanpos[2] + bottomchanpos[2])/2, Motion.AxisMotionSpeeds.Normal, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Z direction.')
		return 0
	
	TestResults.AddTestResult('first_light_hexapod_final_X', Hexapod.GetAxisPosition('X'))
	TestResults.AddTestResult('first_light_hexapod_final_Y', Hexapod.GetAxisPosition('Y'))
	TestResults.AddTestResult('first_light_hexapod_final_Z', Hexapod.GetAxisPosition('Z'))
	TestResults.AddTestResult('first_light_hexapod_final_U', Hexapod.GetAxisPosition('U'))
	TestResults.AddTestResult('first_light_hexapod_final_V', Hexapod.GetAxisPosition('V'))
	TestResults.AddTestResult('first_light_hexapod_final_W', Hexapod.GetAxisPosition('W'))
	
	light_pos = Hexapod.GetAxesPositions()
	
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Light found [{0:.03f}, {1:.03f}, {2:.03f}]'.format(light_pos[0] - search_pos[0],light_pos[1] - search_pos[1],light_pos[2] - search_pos[2]))

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return 1


#-------------------------------------------------------------------------------
# PitchPivotSearch
# Find the pitch pivot point
#-------------------------------------------------------------------------------
def PitchPivotSearch(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	# <FiberToDiePDAttach Name="PitchPivotOffsetFromZero" Value="0.05" />
	# <FiberToDiePDAttach Name="PitchPivotNMax" Value="30" />
	# <FiberToDiePDAttach Name="PitchPivotRTol" Value="0.0065" />
	# <FiberToDiePDAttach Name="PitchPivotMinRes" Value="0.002" />
	# <FiberToDiePDAttach Name="PitchPivotOffset" Value="78" />
	# <FiberToDiePDAttach Name="PitchPivotLambda" Value="1.5,1.5" />
	# <FiberToDiePDAttach Name="PitchPivotMaxRestarts" Value="3" />
	# <FiberToDiePDAttach Name="PitchPivotMaxTinyMoves" Value="5" />
	# <FiberToDiePDAttach Name="PitchPivotTargetAngle" Value="-0.5" />

	# save the current X position
	Hexapod.GetAxisPosition('X')
	# retreive zero position
	zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
	# allow a larger gap for safe pitch pivot search
	safegap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotOffsetFromZero').DataItem
	Hexapod.MoveAxisAbsolute('X', zero - safegap, Motion.AxisMotionSpeeds.Normal, True)
	# readjust the pivot point
	# Hexapod.PivotPoint['X'] = Hexapod.PivotPoint['X'] - safegap
	# enable the new pivot point
	# Hexapod.ApplyKSDCoordinateSystem('PIVOT')

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
	pitchoffsetX = Hexapod.PivotPoint['X']
	pitchoffsetZ = Hexapod.PivotPoint['Z']
	targetpitchangle = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchPivotTargetAngle').DataItem
	# the axes plane that changes roll pivot point
	pivotaxes = Array[String](['X','Z'])
	startangle = Hexapod.GetAxisPosition('V')	  # get the starting pitch angle

	# define the delegate for algo feedback
	def EvalPivot(a):
		Hexapod.CreateKSDCoordinateSystem('PIVOT', pivotaxes, Array[float]([pitchoffsetX + a[0], pitchoffsetZ + a[1]]))
		# Hexapod.PivotPoint['X'] = pitchoffset + a[0]
		# Hexapod.ApplyKSDCoordinateSystem('PIVOT')

		Hexapod.MoveAxisAbsolute('V', startangle + targetpitchangle, Motion.AxisMotionSpeeds.Normal, True)
		pow = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal')	  # since we are aligned to channel 8 from the previous step
		# move to zero
		Hexapod.MoveAxisAbsolute('V', startangle, Motion.AxisMotionSpeeds.Normal, True)
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
	# Hexapod.MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Normal, True)
	# readjust the pivot point
	# Hexapod.PivotPoint['X'] = Hexapod.PivotPoint['X'] + safegap
	# enable the new pivot point
	Hexapod.ApplyKSDCoordinateSystem('PIVOT')
	# retrieve the new pivot point and save to data
	pivot = Hexapod.PivotPoint
	TestResults.AddTestResult('Pitch_Pivot_X', Hexapod.PivotPoint['X'])

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return 1

#-------------------------------------------------------------------------------
# BalanceDryAlignment
# Balanced dry alignment using Nanocube
#-------------------------------------------------------------------------------
def BalanceDryAlignmentNanocube(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	

	# log the aligned position 
	TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_X', topchanpos[0])
	TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_Y', topchanpos[1])
	TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_Z', topchanpos[2])
	TestResults.AddTestResult('Top_Channel_Dry_Align_Peak_Power', top_chan_peak_V)
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_X', bottomchanpos[0])
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_Y', bottomchanpos[1])
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_Z', bottomchanpos[2])
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Peak_Power', bottom_chan_peak_V)

	# record the final dry align hexapod position
	hposition = Hexapod.GetAxesPositions()
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
	TestResults.AddTestResult('Dry_Align_Balanced_Power_Top_Chan', toppow)
	TestResults.AddTestResult('Dry_Align_Balanced_Power_Bottom_Chan', bottompow)

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	return 1
		

#-------------------------------------------------------------------------------
# ApplyEpoxy
# Manually apply epoxy and establish contact point
#-------------------------------------------------------------------------------
def ApplyEpoxy(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# Ask operator to apply epoxy. Use automation later
	if not LogHelper.AskContinue('Apply epoxy. Click Yes when done.'):
		return 0

	# open to whet epoxy
	whetgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetGap').DataItem
	# move to epoxy whet position
	Hexapod.MoveAxisRelative('X', -whetgap, Motion.AxisMotionSpeeds.Slow, True)
	# wait a few seconds
	Utility.DelayMS(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetTime').DataItem)
	# back to zero position
	#zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
	#Hexapod.MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Slow, True)
	
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
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1
	scan.ExecuteOnce = SequenceObj.AutoStep
	scan.ExecuteNoneModal()
	if scan.IsSuccess == False or SequenceObj.Halt:
		return 0
	

	# do a contact to establish True bond gap
	# start move incrementally until force sensor detect contact
	# first zero out the force sensr
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
	backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
	bondgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyBondGap').DataItem
	# Monitor force change
	hexapod_initial_x = Hexapod.GetAxesPositions()[0]
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		Utility.DelayMS(5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	hexapod_distance_to_touch = Hexapod.GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# found contact point, back off set amount
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	Hexapod.MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	TestResults.AddTestResult('Optical_Z_UC_Cure_Position', Hexapod.GetAxisPosition('X'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_X', Hexapod.GetAxisPosition('X'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_Y', Hexapod.GetAxisPosition('Y'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_Z', Hexapod.GetAxisPosition('Z'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_U', Hexapod.GetAxisPosition('U'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_V', Hexapod.GetAxisPosition('V'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_W', Hexapod.GetAxisPosition('W'))
	
	
	
	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTopEpoxy.jpg')
	HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieSideEpoxy.jpg')
	HardwareFactory.Instance.GetHardwareByName('SideCamera').SaveToFile(dir)

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return 1

#-------------------------------------------------------------------------------
# NanocubeGradientClimb
# Perform nanocube gradient scan
#-------------------------------------------------------------------------------
def NanocubeGradientClimb(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	climb.ExecuteOnce = SequenceObj.AutoStep
	
	# run climb on channel 1
	SetScanChannel(climb, 1, UseOpticalSwitch)
	# climb.Channel = 1
	climb.ExecuteNoneModal()
	if climb.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch1 nanocube gradient climb failed!')
		return 0

	climb1_position = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
	climb1_ch1_peakV = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
	climb1_ch2_peakV = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Ch1 climb complete at [{0:.3f},{1:.3f},{2:.3f}]um with [{3:.3f},{4:.3f}]V signal found'.format(climb1_position[0], climb1_position[1], climb1_position[2], climb1_ch1_peakV, climb1_ch2_peakV))

	if SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Step aborted!')
		return 0
		
	if LogHelper.AskContinue('Record optical return power from powermeter.') == False:
		return 0

	# run climb on channel 2
	SetScanChannel(climb, 2, UseOpticalSwitch)
	# climb.Channel = 2
	climb.ExecuteNoneModal()
	if climb.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch1 nanocube gradient climb failed!')
		return 0

	climb2_position = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
	climb2_ch1_peakV = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
	climb2_ch2_peakV = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Ch2 climb complete at [{0:.3f},{1:.3f},{2:.3f}]um with [{3:.3f},{4:.3f}]V signal found'.format(climb2_position[0], climb2_position[1], climb2_position[2], climb2_ch1_peakV, climb2_ch2_peakV))
	
	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	if LogHelper.AskContinue('Record optical return power from powermeter.') == False:
		return 0
	return 1


#-------------------------------------------------------------------------------
# OptimizePolarizationsMPC201
# Optimize polarizations on both channels sequentially
#-------------------------------------------------------------------------------
def OptimizePolarizationsMPC201(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1):
		return 0
		
	if LogHelper.AskContinue('Channel 1 plarization is peaked!') == False:
		return 0
		
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1,mode='min'):
		return 0
		
	if LogHelper.AskContinue('Channel 1 plarization is peaked!') == False:
		return 0
	
	return 1

	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=2):
		return 0
	if LogHelper.AskContinue('Channel 2 plarization is peaked!') == False:
		return 0

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0
	
	return 1


#-------------------------------------------------------------------------------
# LoopbackAlignPowermeter
# "slow" align using the nanocube to move and powermeter for feedback
#-------------------------------------------------------------------------------
def LoopbackAlignPowermeter(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	def GridScanPowermeter(SequenceObj, axes, meter, channel, step_size = 1., scan_width = 10.):
		if(channel == 1):
			IOController.SetOutputValue('OpticalSwitch', False)
		else:
			IOController.SetOutputValue('OpticalSwitch', True)
		starting_position = Nanocube.GetAxesPosition(axes)
		max_signal = -999.0
		i_pos = starting_position - scan_width/2
		j_pos = starting_position - scan_width/2
		max_positions = [i_pos, j_pos]
		for i in range(num_steps):
			for j in range(num_steps):
				Nanocube.MoveAxesAbsolute(axes, [i_pos, j_pos], Motion.AxisMotionSpeeds.Fast, True)
				sleep(0.15)
				signal = meter.ReadPower(channel)
				if(signal > max_signal):
				    max_positions = [i_pos, j_pos]
				j_pos += step_size
				if SequenceObj.Halt:
					return False
			i_pos += step_size
		Nanocube.MoveAxesAbsolute(axes, max_positions, Motion.AxisMotionSpeeds.Fast, True)
		return True
		
	step_size = 0.5 #um
	scan_width = 10. #um
	num_steps = int(round(scan_width/step_size)) + 1
	
	starting_positions = Nanocube.GetAxesPositions()
	channel = 1
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0
	
	axes = ['Y', 'Z']
	if not GridScanPowermeter(SequenceObj, axes, Powermeter, channel, step_size, scan_width):
			return 0	
	
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0
	
	if LogHelper.AskContinue('Channel 1 loopback is peaked!') == False:
		return 0
	
	channel = 2
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0
	
	axes = ['Y', 'Z']
	if not GridScanPowermeter(SequenceObj, axes, Powermeter, channel, step_size, scan_width):
			return 0	
	
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0

	if LogHelper.AskContinue('Channel 2 loopback is peaked!') == False:
		return 0

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	return 1
	
#-------------------------------------------------------------------------------
# LoopbackAlignPowermeter
# "slow" align using the nanocube to move and powermeter for feedback
#-------------------------------------------------------------------------------
def LoopbackAlignPowermeter_cross(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	def LineScanPowermeter(SequenceObj, axis, feedback_channel, step_size = 1., scan_width = 10.):
		starting_position = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(axis)
		fb_signal = []
		scan_positions = []
		for i in range(num_steps):
			scan_positions.append(i*step_size + starting_position - scan_width/2)
			HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute(axis, scan_positions[-1], Motion.AxisMotionSpeeds.Fast, True)
			sleep(0.15)

			if (feedback_channel == 1):
				fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Powermeter').ReadPowers('1:1')[1][0])
			else:
				fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Powermeter').ReadPowers('2:1')[1][0])
			# positions.append(HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(axis))
			if SequenceObj.Halt:
				return False
	
		HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute(axis, scan_positions[fb_signal.index(max(fb_signal))], Motion.AxisMotionSpeeds.Fast, True)
		
		return True
		
	step_size = 0.5 #um
	scan_width = 10. #um
	
	num_steps = int(round(scan_width/step_size)) + 1
	
	starting_positions = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
	
	channel = 1
	
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0
	
	axis = 'Y'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
			return 0	
	axis = 'Z'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
			return 0	
	
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0
	
	if LogHelper.AskContinue('Channel 1 loopback is peaked!') == False:
		return 0
	
		
	channel = 2
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0
	
	axis = 'Y'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
			return 0	
	axis = 'Z'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
		return 0
	
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
		return 0

	if LogHelper.AskContinue('Channel 2 loopback is peaked!') == False:
		return 0
		
	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0
	#HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisRelative('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	#HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)
	return 1
	
def LineScans(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	name_prefix = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'linescan_name_prefix').DataItem
	axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'linescan_axis1').DataItem
	axis1_scan_width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'linescan_axis1_scan_width_um').DataItem
	axis1_scan_incr = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'linescan_axis1_scan_increment_um').DataItem

	axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'linescan_axis2').DataItem
	axis1_scan_width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'linescan_axis2_scan_width_um').DataItem
	axis1_scan_width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'linescan_axis2_scan_increment_um').DataItem

	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))

	init_positions = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions

	### axis 1 linescan
	# build array of positions to visit
	ax1_positions = [HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(axis1) - axis1_scan_width/2]
	while ax1_positions[-1] < (ax1_positions[0] + axis1_scan_width):
		ax1_positions.append(ax1_positions[-1] + axis1_scan_incr)

	X = []
	Y = []
	Z = []
	ch1 = []
	ch2 = []

	#check if first and last position are within nanocube range of motion
	if ax1_positions[0] < 0:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Axis 1 linescan causes nanocube position < 0.')
	elif ax1_positions[0] < 5:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Axis 1 linescan causes nanocube position < 5.')
	if ax1_positions[0] > 100:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Axis 1 linescan causes nanocube position > 100.')
	elif ax1_positions[0] > 95:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Axis 1 linescan causes nanocube position > 95.')
	
	for position in ax1_positions:
		if SequenceObj.Halt:
			HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
			HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
			HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)
			return 0
		HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute(axis1, position, Motion.AxisMotionSpeeds.Normal, True)
		sleep(0.01)
		current_pos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions
		X.append(current_pos[0])
		Y.append(current_pos[1])
		Z.append(current_pos[2])

		ch1.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5))
		ch2.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5))

	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)

	# record data to csv file
	with open(IO.Path.Combine(dir,name_prefix + '_' + axis1 + '_linescan.csv'),'wb') as csvfile:
		csvwriter = csv.writer(csvfile)
		csvwriter.writerow(['X_um','Y_um','Z_um','ch1_v','ch2_v'])
		for i in range(len(ax1_positions)):
			csvwriter.writerow([X[i],Y[i],Z[i],ch1[i],ch2[i]])

	### axis 2 linescan
	# build array of positions to visit
	ax2_positions = [HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(axis2) - axis2_scan_width/2]
	while ax2_positions[-1] < (ax2_positions[0] + axis2_scan_width):
		ax2_positions.append(ax1_positions[-1] + axis2_scan_incr)

	X = []
	Y = []
	Z = []
	ch1 = []
	ch2 = []

	#check if first and last position are within nanocube range of motion
	if ax2_positions[0] < 0:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Axis 2 linescan causes nanocube position < 0.')
	elif ax2_positions[0] < 5:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Axis 2 linescan causes nanocube position < 5.')
	if ax2_positions[0] > 100:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Axis 2 linescan causes nanocube position > 100.')
	elif ax2_positions[0] > 95:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Axis 2 linescan causes nanocube position > 95.')
	
	for position in ax2_positions:
		if SequenceObj.Halt:
			HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
			HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
			HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)
			return 0
		HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute(axis2, position, Motion.AxisMotionSpeeds.Normal, True)
		sleep(0.01)
		current_pos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions
		X.append(current_pos[0])
		Y.append(current_pos[1])
		Z.append(current_pos[2])

		ch1.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5))
		ch2.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5))

	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)

	with open(IO.Path.Combine(dir,name_prefix + '_' + axis2 + '_linescan.csv'),'wb') as csvfile:
		csvwriter = csv.writer(csvfile)
		csvwriter.writerow(['X_um','Y_um','Z_um','ch1_v','ch2_v'])
		for i in range(len(ax1_positions)):
			csvwriter.writerow([X[i],Y[i],Z[i],ch1[i],ch2[i]])
	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0
	return 1

#-------------------------------------------------------------------------------
# UVCure
# UV cure the epoxy bond
#-------------------------------------------------------------------------------
def UVCure(StepName, SequenceObj, TestMetrics, TestResults):
	alignment_results = load_alignment_results(SequenceObj)
	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'ASM_Top_Pre_UV.jpg')
	HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'ASM_Side_Pre_UV.jpg')
	HardwareFactory.Instance.GetHardwareByName('SideCamera').SaveToFile(dir)

	loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem
	uvposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UVPresetPosition').DataItem
	
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

	
	# move UV wands into position
	HardwareFactory.Instance.GetHardwareByName('UVWandStages').GetHardwareStateTree().ActivateState(uvposition)

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

	# retrieve wet align power
	bottompowinput = TestResults.RetrieveTestResult('Wet_Align_Balanced_Power_Top_Chan')
	toppowinput = TestResults.RetrieveTestResult('Wet_Align_Balanced_Power_Bottom_Chan')

	# save process values
	TestResults.AddTestResult('Post_UV_Cure_Power_Top_Chan_Loss', round(toppowinput - toppow, 6))
	TestResults.AddTestResult('Post_UV_Cure_Power_Bottom_Chan_Loss', round(bottompowinput - bottompow, 6))
	
	# save the power tracking to a file
	# save uv cure power tracking
	TestResults.SaveArrayResultsToStorage(TestResults.RetrieveTestResult('Assembly_SN'), 'UVCureChannelPowers', 'Elapsed Time(s),Top Chan Signal(V),Bottom Chan Signal(V)', UVPowerTracking)
	Utility.ShowProcessTextOnMainUI()

	
	HardwareFactory.Instance.GetHardwareByName('UVWandStages').GetHardwareStateTree().ActivateState(loadposition)

	if not ret or SequenceObj.Halt:
		return 0
		
	initialposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)
		
	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'ASM_Top_Post_UV.jpg')
	HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
	# save to file
	#dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	#Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'ASM_Side_Post_UV.jpg')
	HardwareFactory.Instance.GetHardwareByName('SideCamera').SaveToFile(dir)

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
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
	alignment_results = load_alignment_results(SequenceObj)

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

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
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
	alignment_results = load_alignment_results(SequenceObj)
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
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(probeposition)

	
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

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
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
	alignment_results = load_alignment_results(SequenceObj)
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

	# # retrieve dry align power
	# bottompowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')
	# toppowinput = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')

	# # save process values
	# TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan_Loss', round(toppowinput - toppow, 6))
	# TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan_Loss', round(bottompowinput - bottompow, 6))

	# Get the preset position names from recipe
	#unloadpos = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UnloadPresetPosition').DataItem #BoardLoad
	probeposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ProbePresetPosition').DataItem #'BoardLoad'
	fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem
	# boardvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BoardVaccumPortName').DataItem

	# move things out of way for operator to load stuff
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(probeposition)	 
	
	# Ask operator to unfasten the board brace
	if not LogHelper.AskContinue('Disconnect the FAU. Click Yes when done, No to abort. Vacuum will release automatically.'):
		return 0

	# here we need to turn off the vacuum and do some other unload related sequences. 
	HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
	   
	# wait for a second for the vacuum to release
	Utility.DelayMS(5000)

	# Ask operator to adjust probe
	if not LogHelper.AskContinue('Raise the probe and release board clamp. Click Yes when done, No to abort.'):
		return 0

	# here we lower the board fixture platform
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(boardvac, False)

	# wait for a second for the vacuum to release
	# Utility.DelayMS(5000)

	# move hexapod to unload position
	# Hexapod.GetHardwareStateTree().ActivateState(unloadpos)

	TestResults.AddTestResult('End_Time', DateTime.Now)

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
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
	alignment_results = load_alignment_results(SequenceObj)
	# get process values
	#inputtop = TestResults.RetrieveTestResult('Optical_Input_Power_Top_Outer_Chan')
	#inputbottom = TestResults.RetrieveTestResult('Optical_Input_Power_Bottom_Outer_Chan')
	drytop = TestResults.RetrieveTestResult('Dry_Align_Power_Top_Outer_Chan')
	drybottom = TestResults.RetrieveTestResult('Dry_Align_Power_Bottom_Outer_Chan')
	wettop = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')
	wetbottom = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')
	uvtop = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Top_Outer_Chan')
	uvbottom = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan')
	releasetop = TestResults.RetrieveTestResult('Post_Release_Power_Top_Outer_Chan')
	releasebottom = TestResults.RetrieveTestResult('Post_Release_Power_Bottom_Outer_Chan')

	# save process values
	#TestResults.AddTestResult('Dry_Align_Power_Top_Outer_Chan_Loss', round(inputtop - drytop, 6))
	#TestResults.AddTestResult('Dry_Align_Power_Bottom_Outer_Chan_Loss', round(inputbottom - drybottom, 6))

	#TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan_Loss', round(drytop - wettop, 6))
	#TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan_Loss', round(drybottom - wetbottom, 6))

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

	if not save_alignment_results(SequenceObj, alignment_results):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0

	return 1

#-------------------------------------------------------------------------------
# AreaScan: testing routine
#-------------------------------------------------------------------------------
def AreaScan(scanAlgorithm, SequenceObj, TestMetrics, TestResults):

	nanocube = HardwareFactory.Instance.GetHardwareByName('Nanocube')
	# get the hexapod alignment algorithm
	scan = nanocube.GetPIAreaScan(Motion.AreaScanType.SPIRAL_CV)
	scan.RoutineName = '1'
	scan.Axis1 = 'Y'
	scan.Axis2 = 'Z'
	scan.Range1 = 60.0
	scan.Range2 = 3.0
	scan.Velocity = 50
	scan.Frequency = 4
	scan.MidPosition1 = 50
	scan.MidPosition2 = 50
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1
	scan.SaveRecordData = True
	# scan.ExecuteOnce = SequenceObj.AutoStep

	# one scan to get initial power
	scan.ExecuteNoneModal()
	if scan.IsSuccess == False or  SequenceObj.Halt:
		return 0

	# wait to settle
	Utility.DelayMS(500)


