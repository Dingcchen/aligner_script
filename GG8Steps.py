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
from AlignerUtil import *
from datetime import datetime
from step_manager  import *
from Alignment import *
import random


# UseOpticalSwitch = True


def Template(SequenceObj, alignment_parameters, alignment_results):
	"""
	DO NOT DELETE THIS METHOD
	This is the method pattern for all python script called by AutomationCore PythonScriptManager.
	The method arguments must be exactly as shown. They are the following:
	SequenceObj: This object has the following fields:
		ProcessSequenceName: Name of the process sequence that is invoking this step
		StepName: This is the name of the step that invokes this step. Useful for log entry and alerts to user.
		scriptFilePath: path to the script file where StepName resides
		RootPath: Path to the Aligner folder running this script
		TestMetrics: The object that holds all the process recipe values. See the C# code for usage.
		TestResults: The object that stores all process result values. See the C# code for usage.
	alignment_parameters: python dictionary that contains the input parameters to the sequence in ProcessSequenceName. This file is not automatically recorded at the end of the step
	alignment_results: python dictionary that contatins alignment result data. This file is saved after a step completes successfully
	"""

	TestResults.ClearAllTestResult()
	# alignment_parameters is cleared when stepname == Initialize by the step_manager

	sleep(2.000)
	if Stop:
		return 0

	pivot = alignment_parameters['InitialPivotPoint']
	alignment_results['Pivot'] = pivot

	sleep(2.000)
	if Stop:
		return 0

	alignment_results['Step2Result'] = 999
	LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Alert, 'Step1 done')

	#Must always return an integer. 0 = failure, everythingthing else = success
	return alignment_results

#-------------------------------------------------------------------------------
# Initialize
# Clears up test data and other prep work before process starts
#-------------------------------------------------------------------------------
def Initialize(SequenceObj, alignment_parameters, alignment_results):
	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	# clear the output data
	SequenceObj.TestResults.ClearAllTestResult()
	Utility.ShowProcessTextOnMainUI() # clear message

	SequenceObj.TestResults.AddTestResult('Start_Time', DateTime.Now)
	alignment_results['Start_Time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
	SequenceObj.TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
	alignment_results['Operator'] = UserManager.CurrentUser.Name
	SequenceObj.TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())
	alignment_results['Software_Version'] = Utility.GetApplicationVersion()

	# turn on coax lights on lenses and turn off side backlight
	# IOController.SetOutputValue('DownCamCoaxialLight', True)
	# IOController.SetOutputValue('SideCamCoaxialLight', True)
	# IOController.SetOutputValue('SideCamBacklight', False)
	IOController.GetHardwareStateTree().ActivateState('Default')

	initpivot = alignment_parameters['InitialPivotPoint']
	LogHelper.Log('Initialize', LogEventSeverity.Alert, 'initpivot {0:.3f} {1:.3f} {2:.3f}.'.format(initpivot[0], initpivot[1], initpivot[2]))
	current_position = list(Hexapod.GetAxesPositions())
	LogHelper.Log('Initialize', LogEventSeverity.Alert, 'current_position {0:.3f} {1:.3f} {2:.3f}.'.format(current_position[0], current_position[1], current_position[2]))
	pivot_point = [x+y for x,y in zip(initpivot, current_position)]
	LogHelper.Log('Initialize', LogEventSeverity.Alert, 'pivot_point {0:.3f} {1:.3f} {2:.3f}.'.format(pivot_point[0], pivot_point[1], pivot_point[2]))
	# Hexapod.CreateKSWCoordinateSystem('WORK', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	Nanocube.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z']), Array[float]([50, 50, 50]), Motion.AxisMotionSpeeds.Normal, True)


	# Hexapod.EnableCoordinateSystem("PIVOT");
	# Hexapod.EnableCoordinateSystem("WORK");
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot), True)

	# Hexapod.CreateKSFCoordinateSystem('KSF', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot))
	# Hexapod.CreateKSFCoordinateSystem('KSF')


	# Nanocube.GetHardwareStateTree().ActivateState('Center')

	return alignment_results

#-------------------------------------------------------------------------------
# CheckProbe
# Ask the user to visually check probe contact to the die
#-------------------------------------------------------------------------------
def CheckProbe(SequenceObj, alignment_parameters, alignment_results):


	probeposition = alignment_parameters['ProbePresetPosition'] #'BoardLoad'

	initialposition = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'

	# turn on the cameras
	DownCamera.Live(True)
	# SideCamera.Live(True)

	IOController.GetHardwareStateTree().ActivateState(probeposition)

	# set exposure
	DownCamera.SetExposureTime(3)

	# move things out of way for operator to load stuff
	DownCamRingLightControl.GetHardwareStateTree().ActivateState(probeposition)
	DownCameraStages.GetHardwareStateTree().ActivateState(probeposition)

	SideCamRingLightControl.GetHardwareStateTree().ActivateState(probeposition)
	SideCameraStages.GetHardwareStateTree().ActivateState(probeposition)

	#Ask operator to adjust probe
	if LogHelper.AskContinue('Adjust probe until pins are in contact with pads. Click Yes when done, No to abort.') == False:
		return 0

	# go back to initial position
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

def SnapDieText(SequenceObj, alignment_parameters, alignment_results):

	probeposition = alignment_parameters['ProbePresetPosition'] #'BoardLoad'
	die_text_position = alignment_parameters['DieTextPosition'] #'FAUToBoardInitial'

	DownCameraStages.GetHardwareStateTree().ActivateState(die_text_position)

	IOController.GetHardwareStateTree().ActivateState(die_text_position)
	# set exposure
	# DownCamera.SetExposureTime(15)

	# move things out of way for operator to load stuff
	"""
	DownCamRingLightControl.GetHardwareStateTree().ActivateState(probeposition)
	DownCameraStages.GetHardwareStateTree().ActivateState(probeposition)

	SideCamRingLightControl.GetHardwareStateTree().ActivateState(probeposition)
	SideCameraStages.GetHardwareStateTree().ActivateState(probeposition)
	"""

	# acquire image for vision
	DownCamera.Snap()
	# save to file
	TestResults = SequenceObj.TestResults
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTopText.jpg')
	DownCamera.SaveToFile(dir)

	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	# go back to initial position
	initialposition = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# FindSubmount
# Use vision to find the location of the die
#-------------------------------------------------------------------------------
def SetFirstLightPositionToFAU(SequenceObj, alignment_parameters, alignment_results):

	# define vision tool to use for easier editing
	pmfautopvision = alignment_parameters['PowermeterFAUDownVisionTool'] #'DieTopGF2NoGlassBlock'
	laserfautopvision = alignment_parameters['LaserFAUDownVisionTool'] #"MPOTop_2_7"
	pmfausidevision = alignment_parameters['PowermeterFAUSideVisionTool'] #'DieSideGF2NoGlassBlock'
	laserfausidevision = alignment_parameters['LaserFAUSideVisionTool'] #'MPOSideNormal'
	fautopexposure = alignment_parameters['FAUDownVisionCameraExposure'] #5
	fausideexposure = alignment_parameters['FAUSideVisionCameraExposure'] #5
	initialposition = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'

	# Move hexapod to root coordinate system
	Hexapod.EnableZeroCoordinateSystem()

	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	# move camera to preset position
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	# Get hexapod preset position from recipe and go there
	Hexapod.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0

	# set the hexapod pivot point for this process
	# initpivot = list(map(lambda x: float(x), alignment_parameters['InitialPivotPoint'].split(',')))
	# initpivot = alignment_parameters['InitialPivotPoint']
	# Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	#turn off all lights
	SideCamRingLightControl.SetIlluminationOff()
	DownCamRingLightControl.SetIlluminationOff()

	# set light and exposure
	DownCamRingLightControl.GetHardwareStateTree().ActivateState(initialposition)
	DownCamera.SetExposureTime(fautopexposure)

	# acquire image for vision
	DownCamera.Snap()
	# save to file
	TestResults = SequenceObj.TestResults
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'FAUTop.jpg')
	DownCamera.SaveToFile(dir)

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
	DownCamera.Snap()
	res = MachineVision.RunVisionTool(laserfautopvision)

	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
		return 0

	outputx = res['X']
	outputy = res['Y']
	outputangle = Utility.RadianToDegree(res['Angle'])

	# done vision, back to live view
	DownCamera.Live(True)

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

	sleep(.001*500)

	# re-take laser side
	DownCamera.Snap()
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
	DownCamera.Snap()
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
	# end = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

	# calculate the distance between the first and last fiber channel in order to do pivot angle compensation
	# alignment_results['Outer_Channels_Width'] = round(pow(pow(end.Item1 - start.Item1, 2) + pow(end.Item2 - start.Item2, 2),0.5), 5)

	# turn on the cameras
	DownCamera.Live(True)

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
	DownCamera.Snap()
	# run vision
	res = MachineVision.RunVisionTool(pmfautopvision)

	# check result
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the powermeter FAU top position.')
		return 0

	inputx = res['X']
	inputy = res['Y']

	# one more time for the laser side
	DownCamera.Snap()
	res = MachineVision.RunVisionTool(laserfautopvision)

	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU top position.')
		return 0

	outputx = res['X']
	outputy = res['Y']

	# done vision, back to live view
	DownCamera.Live(True)

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
	# threshold = alignment_parameters['ForceSensorContactThreshold']
	backoff = alignment_parameters['BackOffFromContactDetection']
	farfieldgap = alignment_parameters['FarFieldGap']
	# Monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < alignment_parameters['ForceSensorContactThreshold']:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		sleep(.010)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	# contact, open up the gap
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# set this position as the zero position
	alignment_results['Optical_Z_Zero_Position'] = Hexapod.GetAxisPosition('X')
	# set far field gap for first light alignment
	Hexapod.MoveAxisRelative('X', -farfieldgap, Motion.AxisMotionSpeeds.Normal, True)


	# Side view to adjust FAU relative heights
	SideCamRingLightControl.GetHardwareStateTree().ActivateState(initialposition)
	SideCamera.SetExposureTime(fausideexposure)
	RightSideCamera.Snap()
	res = MachineVision.RunVisionTool(laserfausidevision)
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU side position.')
		return 0

	laserangle = Utility.RadianToDegree(res['Angle'])

	# find the mpo side
	RightSideCamera.Snap()
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
	RightSideCamera.Snap()
	res = MachineVision.RunVisionTool(laserfausidevision)
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the laser FAU side position.')
		return 0

	laserx = res['X']
	lasery = res['Y']

	# turn on the camera again
	RightSideCamera.Live(True)

	# turn off light
	SideCamRingLightControl.SetIlluminationOff()

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](pmx, pmy))
	start = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](laserx, lasery))

	# move the mpo height to match that of the die height plus whatever offset from recipe
	zoffset = alignment_parameters['FirstLightZOffsetFromVision']

	if not Hexapod.MoveAxisRelative('Z', dest.Item2 - start.Item2 + zoffset, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move laser FAU to match powermeter FAU height position.')
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# FindSubmount
# Use vision to find the location of the die
#-------------------------------------------------------------------------------
def SetFirstLightPositionToDie(SequenceObj, alignment_parameters, alignment_results):

	def vision_FAU_top():
		sleep(0.5)
		vision = alignment_parameters['FAUTopVisionTool'] #"MPOTop_2_7"
		exposure = alignment_parameters['FAUTopVisionCameraExposure'] #4
		#IOController.SetOutputValue('DownCamCoaxialLight', True)
		ringlight_brightness = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
		DownCamRingLightControl.GetHardwareStateTree().ActivateState(ringlight_brightness)
		DownCamera.SetExposureTime(exposure)
		IOController.GetHardwareStateTree().ActivateState('FAU_top')
		sleep(0.5)
		DownCamera.Snap()
		DownCamera.Live(True)
		return MachineVision.RunVisionTool(vision)

	def vision_die_top():
		DieTopIOPreset = alignment_parameters['DieTopIOPreset']
		vision = alignment_parameters['DieTopVisionTool'] #"MPOTop_2_7"
		exposure = alignment_parameters['DieTopVisionCameraExposure'] #4
		#IOController.SetOutputValue('DownCamCoaxialLight', False)
		ringlight_brightness = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
		DownCamRingLightControl.GetHardwareStateTree().ActivateState(ringlight_brightness)
		IOController.GetHardwareStateTree().ActivateState('GF7_Die9_top')
		DownCamera.SetExposureTime(exposure)
		sleep(0.5)
		DownCamera.Snap()
		DownCamera.Live(True)
		return MachineVision.RunVisionTool(vision)

	def vision_die_side():
		vision = alignment_parameters['DieSideVisionTool'] #"MPOTop_2_7"
		exposure = alignment_parameters['DieSideVisionCameraExposure'] #4
		IOController.SetOutputValue('SideCamCoaxialLight', False)
		ringlight_brightness = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
		SideCamRingLightControl.GetHardwareStateTree().ActivateState(ringlight_brightness)
		RightSideCamera.SetExposureTime(exposure)
		IOController.SetOutputValue('SideCamBacklight', True)
		sleep(0.5)
		RightSideCamera.Snap()
		SideCamera.Live(True)
		#IOController.SetOutputValue('SideCamBacklight', False)
		return MachineVision.RunVisionTool(vision)

	def vision_FAU_side():
		vision = alignment_parameters['FAUSideVisionTool'] #"MPOTop_2_7"
		exposure = alignment_parameters['FAUSideVisionCameraExposure'] #4
		IOController.SetOutputValue('SideCamCoaxialLight', False)
		ringlight_brightness = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
		SideCamRingLightControl.GetHardwareStateTree().ActivateState(ringlight_brightness)
		RightSideCamera.SetExposureTime(exposure)
		IOController.SetOutputValue('SideCamBacklight', True)
		sleep(0.5)
		RightSideCamera.Snap()
		RightSideCamera.Live(True)
		#IOController.SetOutputValue('SideCamBacklight', False)
		#SideCamRingLightControl.GetHardwareStateTree().ActivateState(ringlight_brightness)
		return MachineVision.RunVisionTool(vision)

	def fix_angle(input_angle, expected_angle):
		while (input_angle - expected_angle) > 90:
			input_angle -= 180
		while (input_angle - expected_angle) < 90:
			input_angle += 180
		return input_angle

	TestResults = SequenceObj.TestResults
	# define vision tool to use for easier editing
	initialposition = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
	#'FAUToBoardInitial'
	safe_approach = alignment_parameters['vision_align_safe_approach'] #'FAUToBoardInitial'
	die_side_position = alignment_parameters['DieFocusedPresetPosition'] #'FAUToBoardInitial'

	#vision_interim_gap_X = alignment_parameters['VisionInterimGapX'] #'FAUToBoardInitial'

	# Move hexapod to root coordinate system
	# Hexapod.EnableZeroCoordinateSystem()

	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	## turn on coax lights on lenses and turn off side backlight
	IOController.SetOutputValue('DownCamCoaxialLight', False)
	IOController.SetOutputValue('SideCamCoaxialLight', True)
	IOController.SetOutputValue('SideCamBacklight', False)

	# move cameras to preset position
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)
	SideCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	# Get hexapod and camera stage preset positions from recipe and go there
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	# Get hexapod preset position from recipe and go there
	Hexapod.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0

	# set the hexapod pivot point for this process
	#initpivot = list(map(lambda x: float(x), alignment_parameters['InitialPivotPoint'].split(',')))
	initpivot = alignment_parameters['InitialPivotPoint']
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	#turn off all lights and then set to recipe level
	SideCamRingLightControl.SetIlluminationOff()
	# acquire image for vision
	DownCamera.Snap()
	# save to file
	sn = alignment_parameters['Assembly_SN']
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration,  sn)
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTop.jpg')
	DownCamera.SaveToFile(dir)

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
	# die_angle = fix_angle(Utility.RadianToDegree(die_res['Angle']),90)
	die_angle = Utility.RadianToDegree(die_res['Angle']) + 90
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Die position {0:.3f} {1:.3f} {2:.3f}'.format(inputx, inputy, die_angle))

	# one more time for the MPO side
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	outputx = res['X']
	outputy = res['Y']
	# FAU_front_face_angle = fix_angle(Utility.RadianToDegree(res['Angle']),90) ### NK 2020-06-29
	FAU_front_face_angle = Utility.RadianToDegree(res['Angle']) 
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'FAU position {0:.3f} {1:.3f} {2:.3f}'.format(outputx, outputy, FAU_front_face_angle))

	move_angle = (FAU_front_face_angle - die_angle)

	# adjust the yaw angle
	Hexapod.MoveAxisRelative('W', move_angle, Motion.AxisMotionSpeeds.Normal, True)

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# move Y first
	if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0
	sleep(.001*500)

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
	# outputx2 = res['X2']
	# outputy2 = res['Y2']

	# adjust the translation
	start = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))
	# end = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

	# calculate the distance between the first and last fiber channel in order to do pivot angle compensation
	# alignment_results['Measured_Channel_Pitch'] = round(((end.Item1 - start.Item1)**2 + (end.Item2 - start.Item2)**2)**0.5, 5)


	if SequenceObj.Halt:
		return 0

	# resume the translational motion again
	# if not Hexapod.MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
	#	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
	#	return 0

	# move in x, but with wider gap remaining
	hexapod = Hexapod
	# if not hexapod.MoveAxisRelative('X', dest.Item1 - start.Item1 - 0.02, Motion.AxisMotionSpeeds.Slow, True):
	if not hexapod.MoveAxisRelative('X', dest.Item1 - start.Item1 - alignment_parameters['VisionDryAlignGapX'], Motion.AxisMotionSpeeds.Normal, True): # slow times out
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
	move_angle = (FAU_front_face_angle - die_angle)

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
	SideCameraStages.GetHardwareStateTree().ActivateState(die_side_position)

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

	if safe_approach:
		if not LogHelper.AskContinue('Did the vision system correctly identify the die side?'):
			return 0


	# find the FAU side
	SideCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	res = vision_FAU_side()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU side position.')
		return 0

	mpox = res['X']
	mpoy = res['Y']
	mpoangle = Utility.RadianToDegree(res['Angle'])

	if safe_approach:
		if not LogHelper.AskContinue('Did the vision system correctly identify the die side?'):
			return 0

	# transform the coordinates so we know how to move
	dest = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](diex, diey))
	start = MachineVision.ApplyTransform('SideCameraTransform', ValueTuple[float,float](mpox, mpoy))

	### calculate z move, but don't actually move until the very end
	z_offset = alignment_parameters['FirstLightZOffsetFromVision']
	z_move_final = dest.Item2 - start.Item2 + z_offset
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'WGX WGY {0:.3f} {1:.3f}.'.format(mpox, mpoy))
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'z_move_final {0:.3f} {1:.3f} {2:.3f}.'.format(dest.Item2, start.Item2, z_offset))

	# move the mpo height to match that of the die height, include the z-offset
	# if not Hexapod.MoveAxisRelative('Z', z_move_final, Motion.AxisMotionSpeeds.Slow, True):
	#	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move MPO to match die height position.')
	#	return 0

	# adjust the yaw angle
	Hexapod.MoveAxisRelative('V', mpoangle - dieangle, Motion.AxisMotionSpeeds.Normal, True)

	# now move x to put the mpo to process distance from die
	#if not Hexapod.MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
	#	 LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
	#	 return 0

	if SequenceObj.Halt:
		return 0

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
	move_angle = (FAU_front_face_angle - die_angle)

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
	y_offset_from_vision = alignment_parameters['FirstLightYOffsetFromVision']
	if not Hexapod.MoveAxisRelative('Y', y_offset_from_vision + dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	# move to a location far enough for side view vision to work better
	# the light causes the die to bleed into the MPO
	processdist = dest.Item1 - start.Item1 - alignment_parameters['VisionDryAlignGapX']
	alignment_results['optical_z0'] = Hexapod.GetAxisPosition('X')

	if not Hexapod.MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0
	
	if not Hexapod.MoveAxisRelative('Z', z_move_final, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move MPO to match die height position.')
		return 0

	alignment_results['optical_z0'] = Hexapod.GetAxisPosition('X') + alignment_parameters['VisionDryAlignGapX']
	alignment_results['vision_align_position'] = get_positions(SequenceObj)

	IOController.GetHardwareStateTree().ActivateState('default')

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# FirstLightSearch
# First light alignment on the channels, no balance
# Note: This routine find power on top and bottom channels
#-------------------------------------------------------------------------------
def FirstLightSearchDualChannels(SequenceObj, alignment_parameters, alignment_results):

	"""
	if LogHelper.AskContinue('Move to vision align position?'):
		if not set_positions(SequenceObj, alignment_results['vision_align_position']):
			return 0
	"""
	
	SGRX8Switch.SetClosePoints(2, 5)
	search_pos = Hexapod.GetAxesPositions()

	use_polarization_controller = alignment_parameters['use_polarization_controller']

	#Ask operator to check scrambler is enabled, if polarization controller is not used.
	if not use_polarization_controller:
		if LogHelper.AskContinue('Enable polarization scrmabler! Click Yes when done, No to abort.') == False:
			return 0

	# remember this postion as optical z zero
	# in case we aligned manually, get the z position here instead of previous step
	#alignment_results['Optical_Z_Zero_Position'] = Hexapod.GetAxisPosition('X')

	Nanocube.GetHardwareStateTree().ActivateState('Center')

	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	if use_polarization_controller :
		if not ScramblePolarizationMPC201(SequenceObj):
			return 0

	# declare variables we will use
	retries = 0
	limit = 5

	#Ask operator to fire the lasers
	if LogHelper.AskContinue('Fire the lasers! Click Yes when done, No to abort.') == False:
		if use_polarization_controller :
			PolarizationControl.SetScrambleEnableState(False)
		return 0

	# get the hexapod alignment algorithm
	scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
	# Reload parameters from recipe file
	# minpower = alignment_parameters['ScanMinPowerThreshold'] # this value will be in hexapod analog input unit.
	scan.Axis1 = 'Y'
	scan.Axis2 = 'Z'
	scan.Range1 = alignment_parameters['HexapodRoughScanRange1']
	scan.Range2 = alignment_parameters['HexapodRoughScanRange2']
	scan.Velocity = alignment_parameters['HexapodRoughScanVelocity']
	scan.Frequency = alignment_parameters['HexapodRoughScanFrequency']
	# scan.Threshold = minpower # Volts
	SetScanChannel(scan, 1, alignment_parameters['UseOpticalSwitch'])
	# scan.Channel = 1
	scan.ExecuteOnce = SequenceObj.AutoStep
	# scan.UseCurrentPosition = True

	found_light_ch1 = False
	topinitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
	if topinitpower < alignment_parameters['ScanMinPowerThreshold']:
		# do a few scans to make sure we are in the closest range possible

		scan.ExecuteNoneModal()
		if scan.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch1 coarse scan failed!')
			return 0

		# wait to settle
		sleep(.001*2000)

		for i in range(20): # in case of scrambling polarization, check multiple times for power to exceed threshold
			if ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument) >= alignment_parameters['ScanMinPowerThreshold']:
				found_light_ch1 = True
				break
			sleep(0.01)
	else:
		found_light_ch1 = True

	if not found_light_ch1:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Minimum first light power {0:.3f} for top channel not achieved.'.format(alignment_parameters['ScanMinPowerThreshold']))
		return 0

	positions = Hexapod.GetAxesPositions()
	LogHelper.Log('RastScan', LogEventSeverity.Warning, 'Hexapod found first light at [{0:.3f}, {1:.3f}, {2:.3f}].'.format(positions[0],positions[1],positions[2]))

	if not	HexapodSpiralScan(SequenceObj, 1, scan_dia_mm = .10, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwitch = alignment_parameters['UseOpticalSwitch']):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch1 fine scan failed!')
		return 0

	# save top chan aligned position
	topchanpos = Hexapod.GetAxesPositions()

	SGRX8Switch.SetClosePoints(2, 6)

	if not	HexapodSpiralScan(SequenceObj, 2, scan_dia_mm = .05, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwitch = alignment_parameters['UseOpticalSwitch']):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Ch2 fine scan failed!')
		return 0
	if alignment_parameters['UseOpticalSwitch']:
		bottominitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
	else:
		bottominitpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
	retries = 0
	if bottominitpower < alignment_parameters['ScanMinPowerThreshold']:
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

	light_pos = Hexapod.GetAxesPositions()

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Light found [{0:.03f}, {1:.03f}, {2:.03f}]'.format(light_pos[0] - search_pos[0],light_pos[1] - search_pos[1],light_pos[2] - search_pos[2]))

	alignment_results['vision_align_position'] = get_positions(SequenceObj)
	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results


#-------------------------------------------------------------------------------
# PitchPivotSearch
# Find the pitch pivot point
#-------------------------------------------------------------------------------
def PitchPivotSearch(SequenceObj, alignment_parameters, alignment_results):

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
	zero = alignment_results['Optical_Z_Zero_Position']
	# allow a larger gap for safe pitch pivot search
	safegap = alignment_parameters['PitchPivotOffsetFromZero']
	Hexapod.MoveAxisAbsolute('X', zero - safegap, Motion.AxisMotionSpeeds.Normal, True)
	# readjust the pivot point
	# Hexapod.PivotPoint['X'] = Hexapod.PivotPoint['X'] - safegap
	# enable the new pivot point
	# Hexapod.ApplyKSDCoordinateSystem('PIVOT')

	pitchpivotsearch = Alignments.AlignmentFactory.Instance.SelectAlignment('SimplexMaximumSearch')
	# Reload the parameters
	pitchpivotsearch.NMax = alignment_parameters['PitchPivotNMax']
	pitchpivotsearch.RTol = alignment_parameters['PitchPivotRTol']
	pitchpivotsearch.MinRes = alignment_parameters['PitchPivotMinRes']
	pitchpivotsearch.Lambda = (str)(alignment_parameters['PitchPivotLambda'])
	pitchpivotsearch.MaxRestarts = alignment_parameters['PitchPivotMaxRestarts']
	pitchpivotsearch.MaxTinyMoves = alignment_parameters['PitchPivotMaxTinyMoves']
	pitchpivotsearch.ExecuteOnce = SequenceObj.AutoStep

	# pitchoffset = alignment_parameters['PitchPivotOffset']
	pitchoffsetX = Hexapod.PivotPoint['X']
	pitchoffsetZ = Hexapod.PivotPoint['Z']
	targetpitchangle = alignment_parameters['PitchPivotTargetAngle']
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
	alignment_results['Pitch_Pivot_X'] = Hexapod.PivotPoint['X']

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# BalanceDryAlignment
# Balanced dry alignment using Nanocube
#-------------------------------------------------------------------------------
def BalanceDryAlignmentNanocube(SequenceObj, alignment_parameters, alignment_results):

	UseOpticalSwitch = alignment_parameters['UseOpticalSwitch']
	use_polarization_controller = alignment_parameters['use_polarization_controller']
	base_dist = alignment_parameters['FirstLight_WG2WG_dist_mm']
	threshold = alignment_parameters["ScanMinPowerThreshold"]
	fau_flip = alignment_parameters["FAUFlipped"]
	# log the aligned position
	roll_align_result = OptimizeRollAngle(SequenceObj, base_dist, use_polarization_controller, threshold, max_z_difference_um = 0.5, UseOpticalSwitch = UseOpticalSwitch, fau_flip=fau_flip)

	if roll_align_result is False:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Roll optimize failed!')
		return 0

	alignment_results['Dry_Align_Results'] = roll_align_result

	return alignment_results


#-------------------------------------------------------------------------------
# RollBalanceAlign for Tsumimoto dual MCF.
# Roll balanced align, but wet
# Touches the die with the force sensor and moves to bond gap
# Uses much tighter spec for roll align
#-------------------------------------------------------------------------------
def OrcaLampRollBalanceAlign(SequenceObj, alignment_parameters, alignment_results):

	fau_flip = alignment_parameters["FAUFlipped"]
	WG2WG_dist_mm = alignment_parameters['FirstLight_WG2WG_dist_mm']
	powerThresdhold = alignment_parameters["ScanMinPowerThreshold"]
	max_z_difference_um = 0.2  # um
	
	opticalSwitchChn1 = OpticalSwitch(SGRX8Switch, 0, 5, "chn 1")
	opticalSwitchChn2 = OpticalSwitch(SGRX8Switch, 0, 6, "chn 2")

	laserAtChn1 = None
	meter1 = Meter_nanocube(1)
	meter2 = Meter_nanocube(2)
	topAlignment = SearchMaxPosition('TX', laserAtChn1, meter1, opticalSwitchChn1, powerThresdhold)
	bottomAlignment = SearchMaxPosition('RX', laserAtChn1, meter2, opticalSwitchChn2, powerThresdhold)

	scan_channels = (topAlignment, bottomAlignment)

	testRollAlign = TwoChannelRollAlignment(scan_channels, WG2WG_dist_mm, max_z_difference_um, fau_flip=fau_flip)

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Flipped {0} wave guide distant {1}'.format(fau_flip, WG2WG_dist_mm))
	if not testRollAlign.Iteration(SequenceObj, num=10):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Roll optimize failed!')
		return 0

	# Move back to original coordinate.
	# Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	return testRollAlign

#-------------------------------------------------------------------------------
# DryBalanceAlign
# Roll balanced align, 
# Touches the die with the force sensor and moves to bond gap
# Uses much tighter spec for roll align
#-------------------------------------------------------------------------------
def DryBalanceAlign(SequenceObj, alignment_parameters, alignment_results):

	#Ask operator to check both channels are connected
	if LogHelper.AskContinue('Connect both channels from optical switch! Click Yes when done, No to abort.') == False:
		return 0

	testRollAlign = OrcaLampRollBalanceAlign(SequenceObj, alignment_parameters, alignment_results)

	if(testRollAlign is False):
		return 0
	else:
		alignment_results['Dry_Align_Results'] = testRollAlign.Results

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results
	
	
#-------------------------------------------------------------------------------
# WetBalanceAlign
# Dry balanced align, but wet
# Touches the die with the force sensor and moves to bond gap
# Uses much tighter spec for roll align
#-------------------------------------------------------------------------------
def WetBalanceAlign(SequenceObj, alignment_parameters, alignment_results):

	#Ask operator to check both channels are connected
	if LogHelper.AskContinue('Connect both channels from optical switch! Click Yes when done, No to abort.') == False:
		return 0

	UseOpticalSwitch = alignment_parameters['UseOpticalSwitch']
	use_polarization_controller = alignment_parameters['use_polarization_controller']

	#Ask operator to check scrambler is enabled, if polarization controller is not used.
	if not use_polarization_controller:
		if LogHelper.AskContinue('Enable polarization scrmabler! Click Yes when done, No to abort.') == False:
			return 0


	# Re-establish the contact point again
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	# threshold = alignment_parameters['ForceSensorContactThreshold']
	backoff = alignment_parameters['BackOffFromContactDetection']
	bondgap = alignment_parameters['EpoxyBondGap']
	initpivot = alignment_parameters['InitialPivotPoint']
	fau_flip = alignment_parameters["FAUFlipped"]
	hexapod_initial_x = Hexapod.GetAxesPositions()[0]

	# monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < alignment_parameters['ForceSensorContactThreshold']:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		sleep(0.01)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	Hexapod.CreateKSFCoordinateSystem('WORK', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )
	sleep(0.5)
	# found contact point, back off set amount
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)

	hexapod_distance_to_touch = Hexapod.GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# put the required bondgap
	Hexapod.MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)
	"""
	"""

	roll_align_result = OrcaLampRollBalanceAlign(SequenceObj, alignment_parameters, alignment_results)
	# roll_align_result = OptimizeRollAngle(SequenceObj, alignment_parameters['FirstLight_WG2WG_dist_mm'], use_polarization_controller, alignment_parameters["ScanMinPowerThreshold"], max_z_difference_um = 0.2, UseOpticalSwitch = UseOpticalSwitch, fau_flip=fau_flip)

	# Move back to original coordinate.
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	if roll_align_result is False :
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Roll optimize failed!')
		return 0

	alignment_results['Wet_Align_Results'] = roll_align_result.Results

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# ApplyEpoxy
# Manually apply epoxy and establish contact point
#-------------------------------------------------------------------------------
def ApplyEpoxy(SequenceObj, alignment_parameters, alignment_results):


	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)


	# back to zero position
	#zero = alignment_results['Optical_Z_Zero_Position']
	#Hexapod.MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Slow, True)

	"""
	UseOpticalSwitch = alignment_parameters['UseOpticalSwitch']
	current_scan_channel = 1
	if ReadMonitorSignal(SetScanChannel(None, current_scan_channel, UseOpticalSwitch))[0] < alignment_parameters['ScanMinPowerThreshold']:
		if not HexapodSpiralScan(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwitch = UseOpticalSwitch):
			if not HexapodSpiralScan(SequenceObj, current_scan_channel,scan_dia_mm=.090, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwitch = UseOpticalSwitch):
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod spiral scan failed on channel 1!')
				return False
	"""

	# do a contact to establish True bond gap
	# start move incrementally until force sensor detect contact
	# first zero out the force sensr
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	# threshold = alignment_parameters['ForceSensorContactThreshold']
	backoff = alignment_parameters['BackOffFromContactDetection']
	bondgap = alignment_parameters['EpoxyBondGap']
	# Monitor force change
	hexapod_initial_x = Hexapod.GetAxesPositions()[0]
	while (forcesensor.ReadValueImmediate() - startforce) < alignment_parameters['ForceSensorContactThreshold']:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		sleep(.001*5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	hexapod_distance_to_touch = Hexapod.GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# found contact point, back off set amount
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	Hexapod.MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	# Ask operator to apply epoxy. Use automation later
	if not LogHelper.AskContinue('Apply epoxy. Click Yes when done.'):
		return 0

	# open to whet epoxy
	whetgap = alignment_parameters['EpoxyWhetGap']
	# move to epoxy whet position
	Hexapod.MoveAxisRelative('X', -whetgap, Motion.AxisMotionSpeeds.Slow, True)
	# wait a few seconds
	sleep(.001*alignment_parameters['EpoxyWhetTime'])

	hexapod_initial_x = Hexapod.GetAxesPositions()[0]
	while (forcesensor.ReadValueImmediate() - startforce) < alignment_parameters['ForceSensorContactThreshold']:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		sleep(.001*5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	hexapod_distance_to_touch = Hexapod.GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# found contact point, back off set amount
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	Hexapod.MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	# acquire image for vision
	DownCamera.Snap()
	# save to file
	TestResults = SequenceObj.TestResults
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTopEpoxy.jpg')
	DownCamera.SaveToFile(dir)

	# acquire image for vision
	RightSideCamera.Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieSideEpoxy.jpg')
	RightSideCamera.SaveToFile(dir)

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# TestResultStep
# Optimize polarizations on both channels sequentially
#-------------------------------------------------------------------------------
def TestResultStep(SequenceObj, alignment_parameters, alignment_results):

	"""
	if not alignment_parameters['use_polarization_controller']:
		return 0
	"""


	if(alignment_parameters['UseOpticalSwitch']):
		laserSwitch = 'OpticalSwitch2X2'
	else:
		laserSwitch = None

	filename = "..\\Data\\MCF_loopback_test_result.csv"
	csvfile = open(filename, 'wb')
	csvfile.write("Loopback test result.\r\n")
	testcases_result = MCF_RunAllScenario(SequenceObj, laserSwitch, csvfile=csvfile)
	alignment_results['Test Case Results']  = testcases_result
	writeCSV(csvfile, alignment_results)

	csvfile.close()

	# if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1):
	#	return 0

	if LogHelper.AskContinue('Channel 1 plarization is peaked!') == False:
		return 0

	return alignment_results


#-------------------------------------------------------------------------------
# LoopbackAlignPowermeter
# "slow" align using the nanocube to move and powermeter for feedback
#-------------------------------------------------------------------------------
def LoopbackAlignPowermeter(SequenceObj, alignment_parameters, alignment_results):

	LaserSwitch = alignment_parameters['LaserSwitch']

	def GridScanPowermeter(SequenceObj, axes, meter, channel, step_size = 1., scan_width = 10.):
		SetLaserChannel(channel, LaserSwitch)
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
	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	axes = ['Y', 'Z']
	if not GridScanPowermeter(SequenceObj, axes, Powermeter, channel, step_size, scan_width):
			return 0

	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	if LogHelper.AskContinue('Channel 1 loopback is peaked!') == False:
		return 0

	channel = 2
	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	axes = ['Y', 'Z']
	if not GridScanPowermeter(SequenceObj, axes, Powermeter, channel, step_size, scan_width):
			return 0

	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	if LogHelper.AskContinue('Channel 2 loopback is peaked!') == False:
		return 0

	return alignment_results

#-------------------------------------------------------------------------------
# LoopbackAlignPowermeter
# "slow" align using the nanocube to move and powermeter for feedback
#-------------------------------------------------------------------------------
def LoopbackAlignPowermeter_cross(SequenceObj, alignment_parameters, alignment_results):

	def LineScanPowermeter(SequenceObj, axis, feedback_channel, step_size = 1., scan_width = 10.):
		starting_position = Nanocube.GetAxisPosition(axis)
		fb_signal = []
		scan_positions = []
		for i in range(num_steps):
			scan_positions.append(i*step_size + starting_position - scan_width/2)
			Nanocube.MoveAxisAbsolute(axis, scan_positions[-1], Motion.AxisMotionSpeeds.Fast, True)
			sleep(0.15)

			if (feedback_channel == 1):
				fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Powermeter').ReadPowers('1:1')[1][0])
			else:
				fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Powermeter').ReadPowers('2:1')[1][0])
			# positions.append(Nanocube.GetAxisPosition(axis))
			if SequenceObj.Halt:
				return False

		Nanocube.MoveAxisAbsolute(axis, scan_positions[fb_signal.index(max(fb_signal))], Motion.AxisMotionSpeeds.Fast, True)

		return True

	step_size = 0.5 #um
	scan_width = 10. #um

	num_steps = int(round(scan_width/step_size)) + 1

	starting_positions = Nanocube.GetAxesPositions()

	channel = 1

	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	axis = 'Y'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
			return 0
	axis = 'Z'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
			return 0

	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	if LogHelper.AskContinue('Channel 1 loopback is peaked!') == False:
		return 0


	channel = 2
	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	axis = 'Y'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
			return 0
	axis = 'Z'
	if not LineScanPowermeter(SequenceObj, axis, channel, step_size, scan_width):
		return 0

	if alignment_parameters['use_polarization_controller']:
		if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=channel):
			return 0

	if LogHelper.AskContinue('Channel 2 loopback is peaked!') == False:
		return 0

	#Nanocube.MoveAxisRelative('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	#Nanocube.MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)
	return alignment_results

def LineScans(SequenceObj, alignment_parameters, alignment_results):

	name_prefix = alignment_parameters['linescan_name_prefix']
	axis1 = alignment_parameters['linescan_axis1']
	axis1_scan_width = alignment_parameters['linescan_axis1_scan_width_um']
	axis1_scan_incr = alignment_parameters['linescan_axis1_scan_increment_um']

	axis1 = alignment_parameters['linescan_axis2']
	axis1_scan_width = alignment_parameters['linescan_axis2_scan_width_um']
	axis1_scan_width = alignment_parameters['linescan_axis2_scan_increment_um']

	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])

	init_positions = Nanocube.GetAxesPositions

	### axis 1 linescan
	# build array of positions to visit
	ax1_positions = [Nanocube.GetAxisPosition(axis1) - axis1_scan_width/2]
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
			Nanocube.MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
			Nanocube.MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
			Nanocube.MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)
			return 0
		Nanocube.MoveAxisAbsolute(axis1, position, Motion.AxisMotionSpeeds.Normal, True)
		sleep(0.01)
		current_pos = Nanocube.GetAxesPositions
		X.append(current_pos[0])
		Y.append(current_pos[1])
		Z.append(current_pos[2])

		ch1.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5))
		ch2.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5))

	Nanocube.MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)

	# record data to csv file
	with open(IO.Path.Combine(dir,name_prefix + '_' + axis1 + '_linescan.csv'),'wb') as csvfile:
		csvwriter = csv.writer(csvfile)
		csvwriter.writerow(['X_um','Y_um','Z_um','ch1_v','ch2_v'])
		for i in range(len(ax1_positions)):
			csvwriter.writerow([X[i],Y[i],Z[i],ch1[i],ch2[i]])

	### axis 2 linescan
	# build array of positions to visit
	ax2_positions = [Nanocube.GetAxisPosition(axis2) - axis2_scan_width/2]
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
			Nanocube.MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
			Nanocube.MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
			Nanocube.MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)
			return 0
		Nanocube.MoveAxisAbsolute(axis2, position, Motion.AxisMotionSpeeds.Normal, True)
		sleep(0.01)
		current_pos = Nanocube.GetAxesPositions
		X.append(current_pos[0])
		Y.append(current_pos[1])
		Z.append(current_pos[2])

		ch1.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5))
		ch2.append(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5))

	Nanocube.MoveAxisAbsolute('X', init_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Y', init_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Z', init_positions[2], Motion.AxisMotionSpeeds.Normal, True)

	with open(IO.Path.Combine(dir,name_prefix + '_' + axis2 + '_linescan.csv'),'wb') as csvfile:
		csvwriter = csv.writer(csvfile)
		csvwriter.writerow(['X_um','Y_um','Z_um','ch1_v','ch2_v'])
		for i in range(len(ax1_positions)):
			csvwriter.writerow([X[i],Y[i],Z[i],ch1[i],ch2[i]])

	return alignment_results

#-------------------------------------------------------------------------------
# UVCure
# UV cure the epoxy bond
#-------------------------------------------------------------------------------
def UVCure(SequenceObj, alignment_parameters, alignment_results):

	# acquire image for vision
	DownCamera.Snap()
	sleep(1)
	# save to file
	dir = IO.Path.Combine(SequenceObj.TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'ASM_Top_Pre_UV.jpg')
	DownCamera.SaveToFile(dir)

	# acquire image for vision
	RightSideCamera.Snap()
	sleep(1)
	# save to file
	dir = IO.Path.Combine(SequenceObj.TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'ASM_Side_Pre_UV.jpg')
	RightSideCamera.SaveToFile(dir)

	loadposition = alignment_parameters['LoadPresetPosition']
	uvposition = alignment_parameters['UVPresetPosition']

	if not DownCameraStages.GetHardwareStateTree().ActivateState(uvposition):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move down camera stages!')
		return 0

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Start UV')
	# get the uv profile
	profile = alignment_parameters['UVCureStepProfiles']
	# this is a hack, here we sum up the time of all the steps
	# and display count down timer
	#uvtime = sum(map(lambda x: float(x.split(':')[0]), SequenceObj.TestMetrics.GetTestMetricItem('UVCureStepProfiles', profile).split(',')))
	uvtime = sum(map(lambda x: float(x.split(':')[0]), SequenceObj.TestMetrics.GetTestMetricItem('UVCureStepProfiles', profile).DataItem.split(',')))

	# log the profile used
	alignment_results['UV_Cure_Profile'] = profile

	# create collection to track UV power
	UVPowerTracking = List[Array[float]]()
	stopwatch = Stopwatch()
	stopwatch.Start()

	# create the delegate for the UV cure function
	def LogPower(i):
		UVPowerTracking.Add(Array[float]([round(float(stopwatch.ElapsedMilliseconds) / 1000, 1), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 5), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 5)]))
		Utility.ShowProcessTextOnMainUI('UV cure time ' + str(uvtime - int(stopwatch.ElapsedMilliseconds / 1000)) + ' seconds remaining.')

	# start UV exposure
	stepParams = SequenceObj.TestMetrics.GetTestMetricItem('UVCureStepProfiles', profile).DataItem
	ret = HardwareFactory.Instance.GetHardwareByName('UVSource').StartStepUVExposures(stepParams, '1,2', Action[int](LogPower))

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
	alignment_results['Post_UV_Cure_Power_Top_Outer_Chan'] = toppow
	alignment_results['Post_UV_Cure_Power_Bottom_Outer_Chan'] = bottompow

	"""
	# retrieve wet align power
	# bottompowinput = alignment_results['Wet_Align_Balanced_Power_Top_Chan']
	# toppowinput = alignment_results['Wet_Align_Balanced_Power_Bottom_Chan']
	bottompowinput = alignment_results['Wet_Align_Results']['bottom_chan_peak_power'][0]
	toppowinput = alignment_results['Wet_Align_Results']['top_chan_peak_power'][0]

	# save process values
	alignment_results['Post_UV_Cure_Power_Top_Chan_Loss'] = round(toppowinput - toppow, 6)
	alignment_results['Post_UV_Cure_Power_Bottom_Chan_Loss'] = round(bottompowinput - bottompow, 6)
	"""

	# save the power tracking to a file
	# save uv cure power tracking
	###SequenceObj.TestResults.SaveArrayResultsToStorage(alignment_results['Assembly_SN', 'UVCureChannelPowers', 'Elapsed Time(s),Top Chan Signal(V),Bottom Chan Signal(V)', UVPowerTracking])
	Utility.ShowProcessTextOnMainUI()

	# if not ret or SequenceObj.Halt:
	# 	return 0

	initialposition = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
	if not DownCameraStages.GetHardwareStateTree().ActivateState(initialposition):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move down camera stages!')
		return 0

	# turn on the cameras
	DownCamera.Live(False)
	RightSideCamera.Live(False)

	sleep(1)

	# acquire image for vision
	DownCamera.Snap()
	sleep(1)
	# save to file
	dir = IO.Path.Combine(SequenceObj.TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'ASM_Top_Post_UV.jpg')
	DownCamera.SaveToFile(dir)

	# acquire image for vision
	RightSideCamera.Snap()
	sleep(1)
	dir = IO.Path.Combine(dir, 'ASM_Side_Post_UV.jpg')
	RightSideCamera.SaveToFile(dir)

	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# Unload
# Release gripper and unload FAU
#-------------------------------------------------------------------------------
def UnloadFAU(SequenceObj, alignment_parameters, alignment_results):


	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	# Get the preset position names from recipe
	loadpos = alignment_parameters['LoadPresetPosition'] #BoardLoad
	laserfauvacuumport = alignment_parameters['LaserFAUVaccumPortName']
	pmfauvacuumport = alignment_parameters['PowerMeterFAUVaccumPortName']

	# move things out of way for operator to load stuff
	DownCameraStages.GetHardwareStateTree().ActivateState(loadpos)

	# get power based on instrument
	toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]

	# save process values
	alignment_results['Post_Release_Power_Top_Outer_Chan'] = toppower
	alignment_results['Post_Release_Power_Bottom_Outer_Chan'] = bottompower

	# Ask operator to unfasten the board brace
	if not LogHelper.AskContinue('Release the laser side fiber clamps. Power meter side fiber vacuum will release automatically when this dialog box closes. Click Yes when done, No to abort. '):
		return 0

	HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(pmfauvacuumport, False)
	alignment_results['End_Time'] = DateTime.Now


	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# Unload
# Release gripper and unload die
#-------------------------------------------------------------------------------
def UnloadDie(SequenceObj, alignment_parameters, alignment_results):

	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	# save powers
	toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
		power = pm. ReadPowers()
		toppow = power.Item2[0]
		bottompow = power.Item2[1]

	# save process values
	alignment_results['Post_Release_Power_Top_Outer_Chan'] = toppow
	alignment_results['Post_Release_Power_Bottom_Outer_Chan'] = bottompow

	# retrieve dry align power
	bottompowinput = alignment_results['Wet_Align_Power_Bottom_Outer_Chan']
	toppowinput = alignment_results['Wet_Align_Power_Top_Outer_Chan']

	# save process values
	alignment_results['Post_Release_Power_Top_Outer_Chan_Loss'] = round(toppowinput - toppow, 6)
	alignment_results['Post_Release_Power_Bottom_Outer_Chan_Loss'] = round(bottompowinput - bottompow, 6)

	# Get the preset position names from recipe
	loadpos = alignment_parameters['LoadPresetPosition'] #BoardLoad
	probeposition = alignment_parameters['ProbePresetPosition'] #'BoardLoad'
	fauvac = alignment_parameters['FAUVaccumPortName']
	dievac = alignment_parameters['TargetVaccumPortName']

	# move things out of way for operator to load stuff
	DownCameraStages.GetHardwareStateTree().ActivateState(probeposition)
	SideCameraStages.GetHardwareStateTree().ActivateState(probeposition)


	# Ask operator to adjust probe
	if not LogHelper.AskContinue('Raise the probe before unload. Click Yes when done, No to abort.'):
		return 0

	# Ask operator to unfasten the board brace
	if not LogHelper.AskContinue('Remove the fiber clamps. Click Yes when done, No to abort. Vacuum will release automatically.'):
		return 0

	# here we need to turn off the vacuum and do some other unload related sequences.
	HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)

	# wait for a second for the vacuum to release
	sleep(.001*1000)

	HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)

	# wait for a second for the vacuum to release
	sleep(.001*1000)

	# get power based on instrument
	toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]

	# save process values
	alignment_results['Post_Release_Power_Top_Outer_Chan'] = toppower
	alignment_results['Post_Release_Power_Bottom_Outer_Chan'] = bottompower

	alignment_results['End_Time'] = DateTime.Now

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results


def TestResultsStep(SequenceObj, alignment_parameters, alignment_results):

	fau_flip = alignment_parameters["FAUFlipped"]
	WG2WG_dist_mm = alignment_parameters['FirstLight_WG2WG_dist_mm']
	powerThresdhold = alignment_parameters["ScanMinPowerThreshold"]
	assembly_name = alignment_parameters['Assembly_SN']
	max_z_difference_um = 0.2  # um


	title = GetAndCheckUserInput('Test result title ', 'Please test result title')
	opticalSwitchChn1 = OpticalSwitch(SGRX8Switch, 0, 5, "chn 1")
	opticalSwitchChn2 = OpticalSwitch(SGRX8Switch, 0, 6, "chn 2")

	laserAtChn1 = None
	meter1 = Meter_nanocube(1)
	meter2 = Meter_nanocube(2)

	TX_testResult = TestResult("Tx rev Iff ", laserAtChn1, meter1, opticalSwitchChn1)
	RX_testResult = TestResult("RX Iff ", laserAtChn1, meter2, opticalSwitchChn2)

	testcases =  (
            TX_testResult,
            RX_testResult,
		)
	testResults = TestResults(testcases)
	testResults.run(SequenceObj)

	alignment_results[title] = testResults.Results

	filename = "..\\Data\\" + assembly_name
	csvfile = open(filename, 'wb')
	csvfile.write("Loopback test result.\r\n")
	writeCSV(csvfile, alignment_results)
	csvfile.close()

	return alignment_results

#-------------------------------------------------------------------------------
# Unload
# Release gripper and unload die
#-------------------------------------------------------------------------------
def UnloadBoard(SequenceObj, alignment_parameters, alignment_results):

	# turn on the cameras
	DownCamera.Live(True)
	RightSideCamera.Live(True)

	# save powers
	toppow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompow = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)


	# save process values
	alignment_results['Post_Release_Power_Top_Outer_Chan'] = toppow
	alignment_results['Post_Release_Power_Bottom_Outer_Chan'] = bottompow

	# # retrieve dry align power
	# bottompowinput = alignment_results['Wet_Align_Power_Bottom_Outer_Chan']
	# toppowinput = alignment_results['Wet_Align_Power_Top_Outer_Chan']

	# # save process values
	# alignment_results['Post_Release_Power_Top_Outer_Chan_Loss'] = round(toppowinput - toppow, 6)
	# alignment_results['Post_Release_Power_Bottom_Outer_Chan_Loss'] = round(bottompowinput - bottompow, 6)

	# Get the preset position names from recipe
	#unloadpos = alignment_parameters['UnloadPresetPosition'] #BoardLoad
	probeposition = alignment_parameters['ProbePresetPosition'] #'BoardLoad'
	fauvac = alignment_parameters['FAUVaccumPortName']
	# boardvac = alignment_parameters['BoardVaccumPortName']

	# move things out of way for operator to load stuff
	DownCameraStages.GetHardwareStateTree().ActivateState(probeposition)

	# Ask operator to unfasten the board brace
	if not LogHelper.AskContinue('Disconnect the FAU. Click Yes when done, No to abort. Vacuum will release automatically.'):
		return 0

	# Ask operator to adjust probe
	if not LogHelper.AskContinue('Raise the probe and release board clamp. Click Yes when done, No to abort.'):
		return 0

	DownCameraStages.GetHardwareStateTree().ActivateState(alignment_parameters['LoadPresetPosition'])

	# here we lower the board fixture platform
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(boardvac, False)

	# wait for a second for the vacuum to release
	# sleep(.001*5000)

	# move hexapod to unload position
	# Hexapod.GetHardwareStateTree().ActivateState(unloadpos)
	alignment_results['End_Time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results


#-------------------------------------------------------------------------------
# Finalize
# Save data to the file
#-------------------------------------------------------------------------------
def Finalize(SequenceObj, alignment_parameters, alignment_results):

	# get process values
	#inputtop = alignment_results['Optical_Input_Power_Top_Outer_Chan']
	#inputbottom = alignment_results['Optical_Input_Power_Bottom_Outer_Chan']
	drytop = alignment_results['Dry_Align_Power_Top_Outer_Chan']
	drybottom = alignment_results['Dry_Align_Power_Bottom_Outer_Chan']
	wettop = alignment_results['Wet_Align_Power_Top_Outer_Chan']
	wetbottom = alignment_results['Wet_Align_Power_Bottom_Outer_Chan']
	uvtop = alignment_results['Post_UV_Cure_Power_Top_Outer_Chan']
	uvbottom = alignment_results['Post_UV_Cure_Power_Bottom_Outer_Chan']
	releasetop = alignment_results['Post_Release_Power_Top_Outer_Chan']
	releasebottom = alignment_results['Post_Release_Power_Bottom_Outer_Chan']

	# save process values
	#alignment_results['Dry_Align_Power_Top_Outer_Chan_Loss'] = round(inputtop - drytop, 6)
	#alignment_results['Dry_Align_Power_Bottom_Outer_Chan_Loss'] = round(inputbottom - drybottom, 6)

	#alignment_results['Wet_Align_Power_Top_Outer_Chan_Loss'] = round(drytop - wettop, 6)
	#alignment_results['Wet_Align_Power_Bottom_Outer_Chan_Loss'] = round(drybottom - wetbottom, 6)

	alignment_results['Post_UV_Cure_Power_Top_Outer_Chan_Loss'] = round(wettop - uvtop, 6)
	alignment_results['Post_UV_Cure_Power_Bottom_Outer_Chan_Loss'] = round(wetbottom - uvbottom, 6)

	alignment_results['Post_Release_Power_Top_Outer_Chan_Loss'] = round(uvtop - releasetop, 6)
	alignment_results['Post_Release_Power_Bottom_Outer_Chan_Loss'] = round(uvbottom - releasebottom, 6)

	#check user comment
	if TestResults.IsTestResultExists('Comment') == False:
		if Station.Instance.UserComment:
			alignment_results['Comment'] = Station.Instance.UserComment
	else:
		if Station.Instance.UserComment:
			alignment_results['Comment'] = alignment_results['Comment' + ' ' + Station.Instance.UserComment]
		else:
			alignment_results['Comment'] = alignment_results['Comment']

	#save the data file
	TestResults.SaveTestResultsToStorage(alignment_results['Assembly_SN'])

	return alignment_results

#-------------------------------------------------------------------------------
# AreaScan: testing routine
#-------------------------------------------------------------------------------
def AreaScan(scanAlgorithm, SequenceObj, TestMetrics, TestResults):

	nanocube = Nanocube
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
	SetScanChannel(scan, 1, alignment_parameters['UseOpticalSwitch'])
	# scan.Channel = 1
	scan.SaveRecordData = True
	# scan.ExecuteOnce = SequenceObj.AutoStep

	# one scan to get initial power
	scan.ExecuteNoneModal()
	if scan.IsSuccess == False or  SequenceObj.Halt:
		return 0

	# wait to settle
	sleep(.001*500)


