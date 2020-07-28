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
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoAligner.exe')
from CiscoAligner import PickAndPlace
from CiscoAligner import Station
from CiscoAligner import Alignments
from time import sleep
import csv
from AlignerUtil import * 

UseOpticalSwitch = True

#-------------------------------------------------------------------------------
# OptimizePolarizationMPC201
# Helper function to optimize polarization
# Very slow, use FastOptimizePolarizationMPC201 instead
#-------------------------------------------------------------------------------
def OptimizePolarizationMPC201(SequenceObj,control_device_name = 'PolarizationControl',feedback_device = 'Powermeter', feedback_channel = 1, mode = 'max', step_size = .1, convergence_band_percent = 10):
	polarization_controller = HardwareFactory.Instance.GetHardwareByName(control_device_name)
	polarization_controller_channels = ['1','2','3','4']

	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in polarization_controller_channels:
		if not polarization_controller.SetPolarization(1, channel):
			return False
	
	num_steps = int(2*round(1/step_size,0)) + 1

	converged = False
	if mode == 'max':
		last_optimum = -99
	else:
		last_optimum = 99

	while not converged:
		for channel in polarization_controller_channels:
			#loop through the polarization states on this channel and record the feedback signal
			fb_signal = []
			for i in range(num_steps):
				if not polarization_controller.SetPolarization(i*step_size, channel):
					return False
				sleep(0.15)
				if feedback_device=='Powermeter':
					if (feedback_channel == 1):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1')[1][0])
					elif (feedback_channel == 2):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1')[1][0])
					else:
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel)[1][0])
				elif feedback_device=='HexapodAnalogInput':
					fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel))
				elif feedback_device=='NanocubeAnalogInput':
					fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Nanocube').ReadAnalogInput(feedback_channel))
				else:
					return False
				if SequenceObj.Halt:
					return False
			#set the channel to the max (or min) polarization value found
			if mode == 'max':
				if not polarization_controller.SetPolarization(step_size*fb_signal.index(max(fb_signal)), channel):
						return False
			else:
				if not polarization_controller.SetPolarization(step_size*fb_signal.index(min(fb_signal)), channel):
						return False
		sleep(0.2)
		if feedback_device=='Powermeter':
			if (feedback_channel == 1):
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1'))[1][0]
			elif (feedback_channel == 2):
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1'))[1][0]
			else:
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel))[1][0]
		elif feedback_device=='HexapodAnalogInput':
			current_optimum = HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel)
		elif feedback_device=='NanocubeAnalogInput':
			current_optimum = HardwareFactory.Instance.GetHardwareByName('Nanocube').ReadAnalogInput(feedback_channel)
		else:
			return False
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.02f} dBm'.format(current_optimum)) # add other devices!!!
		if abs((current_optimum - last_optimum)/current_optimum) < convergence_band_percent/100.0:
			converged = True
		last_optimum = current_optimum

	return True
	
#-------------------------------------------------------------------------------
# FastOptimizePolarizationMPC201
# Helper function to optimize polarization
#-------------------------------------------------------------------------------
def FastOptimizePolarizationMPC201(SequenceObj,control_device_name = 'PolarizationControl',feedback_device = 'Powermeter', feedback_channel = 1, mode = 'max', step_size = .1, convergence_band_percent = 10):
	polarization_controller = HardwareFactory.Instance.GetHardwareByName(control_device_name)
	if feedback_device == 'Powermeter':
		HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(False)
	polarization_controller_channels = ['1','2','3','4']
	peak_position = [2,2,2,2]

	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in range(len(polarization_controller_channels)):
		# if not polarization_controller.SetPolarization(1, channel):
			# return False
		peak_position[channel] = polarization_controller.ReadPolarization(polarization_controller_channels[channel])[0]
	
	num_steps = int(2*round(1/step_size,0)) + 1

	converged = False
	if mode == 'max':
		last_optimum = -99
	else:
		last_optimum = 99

	while not converged:
		for channel in range(len(polarization_controller_channels)):
			#loop through the polarization states on this channel and record the feedback signal
			fb_signal = []
			positions = []
			i=0
			search_positive = True
			search_negative = True
			next_position = peak_position[channel]
			while True:
				if not polarization_controller.SetPolarization(next_position, polarization_controller_channels[channel]):
					if feedback_device == 'Powermeter':
						HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
					return False
				positions.append(next_position)
				#sleep(0.15)
				
				if feedback_device=='Powermeter':
					if (feedback_channel == 1):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1')[1][0])
					elif (feedback_channel == 2):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1')[1][0])
					else:
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel)[1][0])
				elif feedback_device=='HexapodAnalogInput':
					fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel))
				elif feedback_device=='NanocubeAnalogInput':
					fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Nanocube').ReadAnalogInput(feedback_channel))
				else:
					if feedback_device == 'Powermeter':
						HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
					return False
				if SequenceObj.Halt:
					if feedback_device == 'Powermeter':
						HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
					return False
				
				#decide where to search next
				if search_positive:
					next_position = positions[-1] + step_size
				elif search_negative:
					next_position = positions[-1] - step_size
				else:
					break
				
				# wrap paddle values between 0 and 4
				if next_position < 0:
					next_position += 4
				elif next_position > 4:
					next_position -= 4
				
				#check if signal is increasing or decreasing and update search direction if needed
				if len(positions) >= 3:
					if mode == 'max':
						if search_positive:
							# if power has dropped for the last 2 measurements we are past the peak and need to go the other way
							if (fb_signal[-1] < fb_signal[-2]) and (fb_signal[-2] < fb_signal[-3]):
								search_positive = False
						elif search_negative:
							# if power has dropped for the last 2 measurements we are past the peak and need to go the other way
							if (fb_signal[-1] < fb_signal[-2]) and (fb_signal[-2] < fb_signal[-3]):
								search_negative = False
						else:
							break
					else:
						if search_positive:
							# if power has dropped for the last 2 measurements we are past the peak and need to go the other way
							if (fb_signal[-1] > fb_signal[-2]) and (fb_signal[-2] > fb_signal[-3]):
								search_positive = False
						elif search_negative:
							# if power has dropped for the last 2 measurements we are past the peak and need to go the other way
							if (fb_signal[-1] > fb_signal[-2]) and (fb_signal[-2] > fb_signal[-3]):
								search_negative = False
						else:
							break
				if len(positions) > 30:
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many tries on channel ' + polarization_controller_channels[channel] + "!") # add other devices!!!
					return 0
					
				i += 1
			#set the channel to the max (or min) polarization value found
			if mode == 'max':
				peak_position[channel] = positions[fb_signal.index(max(fb_signal))]
				if not polarization_controller.SetPolarization(peak_position[channel], polarization_controller_channels[channel]):
						if feedback_device == 'Powermeter':
							HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
						return False
			else:
				peak_position[channel] = positions[fb_signal.index(min(fb_signal))]
				if not polarization_controller.SetPolarization(peak_position[channel], polarization_controller_channels[channel]):
						if feedback_device == 'Powermeter':
							HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
						return False
		#sleep(0.2)
		if feedback_device=='Powermeter':
			if (feedback_channel == 1):
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1'))[1][0]
			elif (feedback_channel == 2):
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1'))[1][0]
			else:
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel))[1][0]
		elif feedback_device=='HexapodAnalogInput':
			current_optimum = HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel)
		elif feedback_device=='NanocubeAnalogInput':
			current_optimum = HardwareFactory.Instance.GetHardwareByName('Nanocube').ReadAnalogInput(feedback_channel)
		else:
			if feedback_device == 'Powermeter':
				HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
			return False
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.02f} dBm'.format(current_optimum)) # add other devices!!!
		if abs((current_optimum - last_optimum)/current_optimum) < convergence_band_percent/100.0:
			converged = True
		last_optimum = current_optimum
		step_size = step_size/2
		if step_size < 0.05:
			step_size = 0.05
	
	return True

#-------------------------------------------------------------------------------
# NanocubeSpiralScan50
# Helper function to do a quick nanocube spiral scan with canned settings
#-------------------------------------------------------------------------------
def NanocubeSpiralScan50(fb_channel, plot_output = False):
	if (not fb_channel == 1) and (not  fb_channel == 2):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube feedback channel must be integer 1 or 2.')
		return 0
	nanocube = HardwareFactory.Instance.GetHardwareByName('Nanocube')
	# get the hexapod alignment algorithm
	scan = nanocube.GetPIAreaScan(Motion.AreaScanType.SPIRAL_CV)
	scan.RoutineName = '1'
	scan.Axis1 = 'Y'
	scan.Axis2 = 'Z'
	scan.Range1 = 50.0
	scan.LineSpacing = 10 #line spacing
	scan.Velocity = 50
	scan.Frequency = 4
	scan.MidPosition1 = 50
	scan.MidPosition2 = 50
	scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
	SetScanChannel(scan, fb_channel, UseOpticalSwitch)
	scan.SaveRecordData = plot_output
	# scan.ExecuteOnce = SequenceObj.AutoStep

	# one scan to get initial power
	scan.ExecuteNoneModal()
	if scan.IsSuccess == False:
		return False

	# wait to settle
	Utility.DelayMS(500)
	#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'I made it to the end of NanocubeSpiralScan50()!')
	return True

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

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# clear the output data
	TestResults.ClearAllTestResult()
	Utility.ShowProcessTextOnMainUI() # clear message

	TestResults.AddTestResult('Start_Time', DateTime.Now)
	TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
	TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())
	
	# turn on coax lights on lenses and turn off side backlight
	HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('DownCamCoaxialLight', True)
	HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamCoaxialLight', True)
	HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamBacklight', False)
	
	#HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute(['X', 'Y', 'Z'], [50, 50, 50], Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
	
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
	
	HardwareFactory.Instance.GetHardwareByName('IOControl').GetHardwareStateTree().ActivateState(probeposition)
	
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

	if SequenceObj.Halt:
		return 0
	else:
		return 1
		
def SnapDieText(StepName, SequenceObj, TestMetrics, TestResults):
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
	
	def vision_FAU_top():
		sleep(0.5)
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUTopVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUTopVisionCameraExposure').DataItem #4
		#HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('DownCamCoaxialLight', True)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(exposure)
		HardwareFactory.Instance.GetHardwareByName('IOControl').GetHardwareStateTree().ActivateState('FAU_top')
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
		return HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(vision)
	 
	def vision_die_top():
		DieTopIOPreset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopIOPreset').DataItem 
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieTopVisionCameraExposure').DataItem #4
		#HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('DownCamCoaxialLight', False)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		HardwareFactory.Instance.GetHardwareByName('IOControl').GetHardwareStateTree().ActivateState('GF7_Die9_top')
		HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(exposure)
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
		return HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(vision)
		
	def vision_die_side():
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieSideVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DieSideVisionCameraExposure').DataItem #4
		HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamCoaxialLight', False)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(exposure)
		HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamBacklight', True)
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
		#HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamBacklight', False)
		return HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(vision)

	def vision_FAU_side():
		vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionTool').DataItem #"MPOTop_2_7"
		exposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUSideVisionCameraExposure').DataItem #4
		HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamCoaxialLight', False)
		ringlight_brightness = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'InitialPresetPosition').DataItem #'FAUToBoardInitial'
		HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(exposure)
		HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamBacklight', True)
		sleep(0.5)
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
		#HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamBacklight', False)
		#HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').GetHardwareStateTree().ActivateState(ringlight_brightness)
		return HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(vision)
	
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
	HardwareFactory.Instance.GetHardwareByName('Hexapod').EnableZeroCoordinateSystem()
	
	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
	
	## turn on coax lights on lenses and turn off side backlight
	HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('DownCamCoaxialLight', False)
	HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamCoaxialLight', True)
	HardwareFactory.Instance.GetHardwareByName('IOControl').SetOutputValue('SideCamBacklight', False)

	# move cameras to preset position
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(initialposition)
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(initialposition)

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
	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTop.jpg')
	HardwareFactory.Instance.GetHardwareByName('DownCamera').SaveToFile(dir)

	# run vision
	#####res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topdievision)
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
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', move_angle, Motion.AxisMotionSpeeds.Normal, True)

	# transform the coordinates so we know how to move
	dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# move Y first
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
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
	start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))
	end = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

	# calculate the distance between the first and last fiber channel in order to do pivot angle compensation
	TestResults.AddTestResult('Measured_Channel_Pitch', round(((end.Item1 - start.Item1)**2 + (end.Item2 - start.Item2)**2)**0.5, 5))
	

	if SequenceObj.Halt:
		return 0

	# resume the translational motion again
	""" if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0 """

	# move in x, but with wider gap remaining
	hexapod = HardwareFactory.Instance.GetHardwareByName('Hexapod')
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
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', move_angle, Motion.AxisMotionSpeeds.Normal, True)


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
	dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# start the translational motion again
	# first move in Y
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
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
	dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](diex, diey))
	start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](mpox, mpoy))

	# move the mpo height to match that of the die height, include the z-offset
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', dest.Item2 - start.Item2 + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightZOffsetFromVision').DataItem, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move MPO to match die height position.')
		return 0

	# adjust the yaw angle
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('V', mpoangle - dieangle, Motion.AxisMotionSpeeds.Normal, True)

	# now move x to put the mpo to process distance from die
	#if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
	#	 LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
	#	 return 0

	if SequenceObj.Halt:
		return 0

	# remember this postion as optical z zero
	# if False: #Don't move in multiple axes at once for now as pivot point is not well-defined. Not even sure why this was here... NK 2020-06-17
	#	  # now move x to put the mpo to process distance from die
	#	  if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
	#		  LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
	#		  return 0

	#	  if SequenceObj.Halt:
	#		  return 0

	#	  # remember this postion as optical z zero
	#	  TestResults.AddTestResult('Optical_Z_Zero_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	
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
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', move_angle, Motion.AxisMotionSpeeds.Normal, True)
	
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
	dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](inputx, inputy))
	start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))

	# start the translational motion again
	# move in Y
	y_offset_from_vision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightYOffsetFromVision').DataItem
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', y_offset_from_vision + dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	# move to a location far enough for side view vision to work better
	# the light causes the die to bleed into the MPO
	processdist = dest.Item1 - start.Item1 - TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionDryAlignGapX').DataItem

	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0
	
	TestResults.AddTestResult('vision_align_hexapod_final_X', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	TestResults.AddTestResult('vision_align_hexapod_final_Y', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y'))
	TestResults.AddTestResult('vision_align_hexapod_final_Z', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z'))
	TestResults.AddTestResult('vision_align_hexapod_final_U', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U'))
	TestResults.AddTestResult('vision_align_hexapod_final_V', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('V'))
	TestResults.AddTestResult('vision_align_hexapod_final_W', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('W'))
	
	HardwareFactory.Instance.GetHardwareByName('IOControl').GetHardwareStateTree().ActivateState('default')
	
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
	#HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute([50, 50, 50], Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
	
	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
	
	#Ask operator to fire the lasers
	if LogHelper.AskContinue('Fire the lasers! Click Yes when done, No to abort.') == False:
		return 0

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
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1
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
		return 0
	
	TestResults.AddTestResult('first_light_hexapod_final_X', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	TestResults.AddTestResult('first_light_hexapod_final_Y', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y'))
	TestResults.AddTestResult('first_light_hexapod_final_Z', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z'))
	TestResults.AddTestResult('first_light_hexapod_final_U', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U'))
	TestResults.AddTestResult('first_light_hexapod_final_V', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('V'))
	TestResults.AddTestResult('first_light_hexapod_final_W', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('W'))

	return 1

#-------------------------------------------------------------------------------
# FirstLightSearch
# First light alignment on the channels, no balance
# Note: This routine find power on top and bottom channels and does roll adjust

#-------------------------------------------------------------------------------
def FirstLightSearchDualChannels(StepName, SequenceObj, TestMetrics, TestResults):
	search_pos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
	   
	# remember this postion as optical z zero
	# in case we aligned manually, get the z position here instead of previous step
	#TestResults.AddTestResult('Optical_Z_Zero_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# declare variables we will use
	retries = 0
	limit = 5
	
	#Ask operator to fire the lasers
	if LogHelper.AskContinue('Fire the lasers! Click Yes when done, No to abort.') == False:
		return 0

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
	topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

	# now do channel 2
	#scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
	#scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
	#scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange1').DataItem
	#scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange2').DataItem
	#scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanVelocity').DataItem
	#scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanFrequency').DataItem
	#scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
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
		# # do a few scans to make sure we are in the closest range possible
		# while retries < limit:
			# scan.ExecuteNoneModal()
			# if scan.IsSuccess == False or SequenceObj.Halt:
				# return 0

			# # wait to settle
			# Utility.DelayMS(2000)

			# # check return condition
			# p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
			# if p > bottominitpower or abs(p - bottominitpower) / abs(p) < 0.2:
				# break	 # power close enough, good alignment
			# if p > bottominitpower:
				# bottominitpower = p

			# retries += 1
		
		# if retries >= limit:
			# LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many retries.')
			# return 0	  # error condition

		# if HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5) < minpower:
			# LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Minimum first light power for bottom channel not achieved.')
			# return 0

	# rescan smaller area
	#scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
	#scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
	#scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
	#scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
	# start the scan again
	#scan.ExecuteNoneModal()

	#if scan.IsSuccess == False or SequenceObj.Halt:
	#	 return 0

	# save bottom chan aligned position
	bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

	# adjust the roll - we will adjust the roll later as the area scan is a poor way to adjust roll
	if False:
		#NK 2020-03-31 Forcing User To input channel distance
		#ret = UserFormInputDialog.ShowDialog('Enter WG gap distance', 'Enter WG to WG distance in mm. Manually set initial first light position.', True)
		#if ret == True:
		#	 TestResults.AddTestResult('Outer_Channels_Width', float(UserFormInputDialog.ReturnValue))
		#else:
		#	 return 0
		width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLight_WG2WG_dist_mm').DataItem
		#ret = 0.25
		#width = TestResults.RetrieveTestResult('Outer_Channels_Width')
		h = Math.Atan(Math.Abs(topchanpos[2] - bottomchanpos[2]))

		if h < 0.001:
			return 1	# we achieved the roll angle when the optical Z difference is less than 1 um

		# calculate the roll angle
		r = Utility.RadianToDegree(Math.Atan(h / width))
		rollangle = r
		if topchanpos[2] > bottomchanpos[2]:
		   rollangle = -r

		# adjust the roll angle again
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		Utility.DelayMS(2000)
		# repeat adjustment if necessary
		retries = 0
		while retries < limit and not SequenceObj.Halt:

			# start the algorithms
			SetScanChannel(scan, 1, UseOpticalSwitch)
			# scan.Channel = 1
			scan.ExecuteNoneModal()
			# check scan status
			if scan.IsSuccess == False or SequenceObj.Halt:
				return 0

			# remember the final position
			topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

			# repeat scan for the second channel
			SetScanChannel(scan, 2, UseOpticalSwitch)
			# scan.Channel = 2
			scan.ExecuteNoneModal()
			# check scan status
			if scan.IsSuccess == False or SequenceObj.Halt:
				return 0

			# get the final position of second channel
			bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

			# double check and readjust roll if necessary
			# calculate the roll angle
			h = Math.Atan(Math.Abs(topchanpos[2] - bottomchanpos[2]))
			if h < 0.005:
			   break	# we achieved the roll angle when the optical Z difference is less than 1 um

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
	
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Y', (topchanpos[1] + bottomchanpos[1])/2, Motion.AxisMotionSpeeds.Normal, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0
		
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Z', (topchanpos[2] + bottomchanpos[2])/2, Motion.AxisMotionSpeeds.Normal, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Z direction.')
		return 0
	
	TestResults.AddTestResult('first_light_hexapod_final_X', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	TestResults.AddTestResult('first_light_hexapod_final_Y', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y'))
	TestResults.AddTestResult('first_light_hexapod_final_Z', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z'))
	TestResults.AddTestResult('first_light_hexapod_final_U', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U'))
	TestResults.AddTestResult('first_light_hexapod_final_V', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('V'))
	TestResults.AddTestResult('first_light_hexapod_final_W', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('W'))
	
	light_pos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
	
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Light found [{0:.03f}, {1:.03f}, {2:.03f}]'.format(light_pos[0] - search_pos[0],light_pos[1] - search_pos[1],light_pos[2] - search_pos[2]))

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
	
	SetScanChannel(hscan, 1, UseOpticalSwitch)
	# hscan.Channel = 1
	hscan.ExecuteOnce = SequenceObj.AutoStep

	# Load the simplex search parameter to optimize roll angle
	optimalrollsearch.NMax = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollNMax').DataItem
	optimalrollsearch.RTol = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollRTol').DataItem
	optimalrollsearch.MinRes = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMinRes').DataItem
	optimalrollsearch.Lambda = (str)(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollLambda').DataItem)
	optimalrollsearch.MaxRestarts = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxRestarts').DataItem
	optimalrollsearch.MaxTinyMoves = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxTinyMoves').DataItem
	optimalrollsearch.ExecuteOnce = SequenceObj.AutoStep

	startangle = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U')	  # get the starting pitch angle
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

		return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)	# we want to maximize the bottom channel power since doing so means we are aligned in roll

	# connect the call back function
	optimalrollsearch.EvalFunction = Func[Array[float],float](EvalRoll)
	# start roll optimization
	optimalrollsearch.ExecuteNoneModal()

	if optimalrollsearch.IsSuccess == False or	SequenceObj.Halt:
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
	SetScanChannel(nscan, 1, UseOpticalSwitch)
	# nscan.Channel = 1
	nscan.ExecuteOnce = SequenceObj.AutoStep

	# Load the simplex search parameter to optimize roll angle
	optimalrollsearch.NMax = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollNMax').DataItem
	optimalrollsearch.RTol = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollRTol').DataItem
	optimalrollsearch.MinRes = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMinRes').DataItem
	optimalrollsearch.Lambda = (str)(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollLambda').DataItem)
	optimalrollsearch.MaxRestarts = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxRestarts').DataItem
	optimalrollsearch.MaxTinyMoves = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxTinyMoves').DataItem
	optimalrollsearch.ExecuteOnce = SequenceObj.AutoStep

	startangle = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U')	  # get the starting pitch angle
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

		return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)	# we want to maximize the bottom channel power since doing so means we are aligned in roll

	# connect the call back function
	optimalrollsearch.EvalFunction = Func[Array[float],float](EvalRoll)
	# start roll optimization
	optimalrollsearch.ExecuteNoneModal()

	if optimalrollsearch.IsSuccess == False or	SequenceObj.Halt:
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
	startangle = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('V')	  # get the starting pitch angle

	# define the delegate for algo feedback
	def EvalPivot(a):
		HardwareFactory.Instance.GetHardwareByName('Hexapod').CreateKSDCoordinateSystem('PIVOT', pivotaxes, Array[float]([pitchoffsetX + a[0], pitchoffsetZ + a[1]]))
		# HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = pitchoffset + a[0]
		# HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')

		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', startangle + targetpitchangle, Motion.AxisMotionSpeeds.Normal, True)
		pow = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal')	  # since we are aligned to channel 8 from the previous step
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
# Balanced dry alignment using Nanocube and Hexapod only
#-------------------------------------------------------------------------------
def BalanceDryAlignmentNanocube2(StepName, SequenceObj, TestMetrics, TestResults):
	#assume we are "balance aligned" between channels 1 and 2
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
		SetScanChannel(hscan, 1, UseOpticalSwitch)
		# hscan.Channel = 1
		#hscan.ExecuteNoneModal() # use nanocube now
		if retries == 0:
			NanocubeSpiralScan50(1,plot_output = True)
		else: 
			NanocubeSpiralScan50(1,plot_output = False)
		# check scan status
		#if hscan.IsSuccess == False or SequenceObj.Halt:
		 #	 return 0

		# wait to settle
		#Utility.DelayMS(500)

		# remember the final position
		topchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

		# repeat scan for the second channel
		hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
		SetScanChannel(hscan, 2, UseOpticalSwitch)
		# hscan.Channel = 2

		# start the algorithms again
		hscan.ExecuteNoneModal()
		NanocubeSpiralScan50(2,plot_output = False)
		# check scan status
		#if hscan.IsSuccess == False or SequenceObj.Halt:
		 #	 return 0

		# wait to settle
		#Utility.DelayMS(500)

		# get the final position of second channel
		bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

		# double check and readjust roll if necessary
		# calculate the roll angle
		h = Math.Atan(Math.Abs(topchanpos[2] - bottomchanpos[2]))
		if h < 1:
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

		# calculate the roll angle
		r = Utility.RadianToDegree(Math.Atan((h/1000) / width))
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
	
	#hexpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', (50-ymiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', (50-zmiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)

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
	#zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
	# move back to zero position
	#HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Normal, True)

	# here we do channel balance with Nanocube 2D scan
	# # # scan = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeRasterScan')
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')

	# # # # get nanocube scan parameters
	# # # scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	# # # scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	# # # # we are working in um when dealing with Nanocube
	# # # scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Range1').DataItem * 1000
	# # # scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Range2').DataItem * 1000
	# # # # start at the middle position
	# # # scan.Axis1Position = 50
	# # # scan.Axis2Position = 50
	# # # scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Velocity').DataItem * 1000
	# # # scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Frequency').DataItem
	# # # scan.ExecuteOnce = SequenceObj.AutoStep
	
	# get the hexapod alignment algorithm
	scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
	# Reload parameters from recipe file
	minpower = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanMinPower').DataItem # this value will be in hexapod analog input unit. 
	scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
	scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
	scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
	scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
	scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
	scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
	scan.ExecuteOnce = SequenceObj.AutoStep

	climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	climb.ExecuteOnce = SequenceObj.AutoStep

	# set up a loop to zero in on the roll angle
	width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLight_WG2WG_dist_mm').DataItem
	#idth = TestResults.RetrieveTestResult('Outer_Channels_Width')
	topchanpos = [ 50.0, 50.0, 50.0 ]
	bottomchanpos = [ 50.0, 50.0, 50.0 ]
	retries = 0
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Start roll (U) adjust...')
	num_IFF_samples = 5
	while retries < 5 and not SequenceObj.Halt:
		HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')

		# start the algorithms
		scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
		SetScanChannel(scan, 1, UseOpticalSwitch)
		# scan.Channel = 1
		climb.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
		SetScanChannel(climb, 1, UseOpticalSwitch)
		# climb.Channel = 1
		#scan.ExecuteNoneModal()
		if retries == -1:
			if not NanocubeSpiralScan50(1,plot_output = True):
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1.')
				return 0
		else: 
			if not NanocubeSpiralScan50(1,plot_output = False):
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1.')
				return 0
				
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Nanocube spiral scan succeeded on channel 1!')
		# check scan status
		#if scan.IsSuccess == False or SequenceObj.Halt:
		#	 return 0
		#Utility.DelayMS(500)
		
		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Nanocube climb scan failed on channel 1!')
			return 0
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Nanocube climb scan succeeded on channel 1!')
		Utility.DelayMS(500)
		
		# remember the final position
		topchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
		top_chan_peak_V = 0 
		for i in range(num_IFF_samples):
			top_chan_peak_V = top_chan_peak_V + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
		top_chan_peak_V = top_chan_peak_V/num_IFF_samples
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(topchanpos[0],topchanpos[1],topchanpos[2],top_chan_peak_V))
		

		# repeat scan for the second channel
		scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
		SetScanChannel(scan, 2, UseOpticalSwitch)
		# scan.Channel = 2
		climb.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
		SetScanChannel(climb, 2, UseOpticalSwitch)
		# climb.Channel = 2

		# start the algorithms again
		#scan.ExecuteNoneModal()
		if not NanocubeSpiralScan50(2,plot_output = False):
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 2.')
			return 0
		# check scan status
		#if scan.IsSuccess == False or SequenceObj.Halt:
		#	 return 0
		#Utility.DelayMS(500)

		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			return 0
		Utility.DelayMS(500)
		
		# get the final position of second channel
		bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Bottom channel peak position ({0:.2f}, {1:.2f}, {2:.2f}) um'.format(bottomchanpos[0],bottomchanpos[1],bottomchanpos[2]))
		bottom_chan_peak_V = 0 
		for i in range(num_IFF_samples):
			bottom_chan_peak_V = bottom_chan_peak_V + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
		bottom_chan_peak_V = bottom_chan_peak_V/num_IFF_samples
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 2 peak: {3:.3f}V @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(bottomchanpos[0],bottomchanpos[1],bottomchanpos[2],bottom_chan_peak_V))
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Bottom channel peak position: ' + str(bottomchanpos))

		# double check and readjust roll if necessary
		# calculate the roll angle
		h = Math.Abs(topchanpos[2] - bottomchanpos[2])
		if h < 1:
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

		# calculate the roll angle
		r = Utility.RadianToDegree(Math.Asin(h / (width*1000)))
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
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)
	
	#hexpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', -(50-ymiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', -(50-zmiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)

	# log the aligned position 
	TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_X', topchanpos[0])
	TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_Y', topchanpos[1])
	TestResults.AddTestResult('Top_Channel_Dry_Align_Nanocube_Z', topchanpos[2])
	TestResults.AddTestResult('Top_Channel_Dry_Align_Peak_Power', top_chan_peak_V)
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_X', bottomchanpos[0])
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_Y', bottomchanpos[1])
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Nanocube_Z', bottomchanpos[2])
	TestResults.AddTestResult('Bottom_Channel_Dry_Align_Peak_Power', bottom_chan_peak_V)
	
	### balance the Z (side to side) distance
	##HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', middle, Motion.AxisMotionSpeeds.Normal, True)

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
	TestResults.AddTestResult('Dry_Align_Balanced_Power_Top_Chan', toppow)
	TestResults.AddTestResult('Dry_Align_Balanced_Power_Bottom_Chan', bottompow)

	if SequenceObj.Halt:
		return 0
	else:
		return 1
		
def NanocubeAlignLoop(StepName, SequenceObj, TestMetrics, TestResults):
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
	scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	# we are working in um when dealing with Nanocube
	scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Range1').DataItem * 1000
	scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Range2').DataItem * 1000
	# start at the middle position
	scan.Axis1Position = 50
	scan.Axis2Position = 50
	scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Velocity').DataItem * 1000
	scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Frequency').DataItem
	scan.ExecuteOnce = SequenceObj.AutoStep

	climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	climb.ExecuteOnce = SequenceObj.AutoStep

	# set up a loop to zero in on the roll angle
	width = TestResults.RetrieveTestResult('Outer_Channels_Width')
	topchanpos = [ 50.0, 50.0, 50.0 ]
	bottomchanpos = [ 50.0, 50.0, 50.0 ]
	
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Start scanning...')
	
	num_scans = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'number_of_scans').DataItem
	axis1_max_offset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'axis1_max_start_offset').DataItem
	axis1_sign = -1
	axis2_max_offset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'axis2_max_start_offset').DataItem
	axis2_sign = -1

	# set channel to align
	scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1
	climb.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
	SetScanChannel(climb, 1, UseOpticalSwitch)
	# climb.Channel = 1
	
	for n in range(num_scans):
		if SequenceObj.Halt:
			break
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing scan {0:d}/{1:d}'.format(n+1,num_scans))

		
		if (n%axis1_max_offset) == 0: 
			axis1_sign = -axis1_sign
			
		if (n%axis2_max_offset) == 0: 
			axis2_sign = -axis2_sign
		
		scan.Axis1Position = 50 + (n%axis1_max_offset) * axis1_sign
		scan.Axis2Position = 50 + (n%axis2_max_offset) * axis2_sign

		scan.ExecuteNoneModal()
		# check scan status
		if scan.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube area scan failed!')
			return 0
			
		Utility.DelayMS(500)
		#time.sleep(0.5)

		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube gradient climb scan failed!')
			return 0
		
		Utility.DelayMS(500)
		
		sum_IFF = 0
		num_IFF_samples = 5
		for i in range(num_IFF_samples):
			sum_IFF = sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
			
		# display peak aligned position
		peak_align_position = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Completed scan {0:d}/{1:d} | starting position |{2:.3f}|{3:.3f}| Final position |{4:.3f}|{5:.3f}|{6:.3f}| Peak singal |{7:.3f}'.format(n+1, num_scans,scan.Axis1Position, scan.Axis2Position, peak_align_position[0],peak_align_position[1],peak_align_position[2],sum_IFF/num_IFF_samples))
		
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Done scanning!')

	return 0


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
	#zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
	#HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Slow, True)
	
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
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1
	scan.ExecuteOnce = SequenceObj.AutoStep
	scan.ExecuteNoneModal()
	if scan.IsSuccess == False or SequenceObj.Halt:
		return 0
	

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
	hexapod_initial_x = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()[0]
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		Utility.DelayMS(5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	hexapod_distance_to_touch = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# found contact point, back off set amount
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	TestResults.AddTestResult('Optical_Z_UC_Cure_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_X', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_Y', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_Z', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_U', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_V', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('V'))
	TestResults.AddTestResult('apply_epoxy_hexapod_final_W', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('W'))
	
	
	
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

	if SequenceObj.Halt:
		return 0
	else:
		return 1

#-------------------------------------------------------------------------------
# BalanceWedAlignment
# Balance alignment of the channels in epoxy using Hexapod only
#-------------------------------------------------------------------------------
def BalanceWetAlignmentHexapod(StepName, SequenceObj, TestMetrics, TestResults):

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
		SetScanChannel(hscan, 1, UseOpticalSwitch)
		# hscan.Channel = 1
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
		SetScanChannel(hscan, 2, UseOpticalSwitch)
		# hscan.Channel = 2

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
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

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
def BalanceWetAlignmentNanoCube(StepName, SequenceObj, TestMetrics, TestResults):

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# here we do channel balance with Nanocube 2D scan
	scan = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeRasterScan')
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')

	# get nanocube scan parameters
	scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	# we are working in um when dealing with Nanocube
	scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Range1').DataItem * 1000
	scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Range2').DataItem * 1000
	# start at the middle position
	scan.Axis1Position = 50
	scan.Axis2Position = 50
	scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Velocity').DataItem * 1000
	scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Frequency').DataItem
	scan.ExecuteOnce = SequenceObj.AutoStep

	climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	climb.ExecuteOnce = SequenceObj.AutoStep
	
	
	# set up a loop to zero in on the roll angle
	width = TestResults.RetrieveTestResult('Outer_Channels_Width')
	topchanpos = [ 50.0, 50.0, 50.0 ]
	bottomchanpos = [ 50.0, 50.0, 50.0 ]
	retries = 0

	while retries < 5 and not SequenceObj.Halt:

		# start the algorithms
		SetScanChannel(scan, 1, UseOpticalSwitch)
		SetScanChannel(climb, 1, UseOpticalSwitch)
		# scan.Channel = 1
		# climb.Channel = 1
		scan.ExecuteNoneModal()
		# check scan status
		if scan.IsSuccess == False or SequenceObj.Halt:
			return 0

		#climb.ExecuteNoneModal()
		# check climb status
		#if scan.IsSuccess == False or SequenceObj.Halt:
		#	 return 0

		# remember the final position
		topchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

		# repeat scan for the second channel
		SetScanChannel(scan, 2, UseOpticalSwitch)
		SetScanChannel(climb, 2, UseOpticalSwitch)
		# scan.Channel = 2
		# climb.Channel = 2
		scan.ExecuteNoneModal()
		# check scan status
		if scan.IsSuccess == False or SequenceObj.Halt:
			return 0

		#climb.ExecuteNoneModal()
		# check climb status
		#if scan.IsSuccess == False or SequenceObj.Halt:
		#	 return 0

		# get the final position of second channel
		bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

		# double check and readjust roll if necessary
		# calculate the roll angle
		h = Math.Atan(Math.Abs(topchanpos[1] - bottomchanpos[1]))
		if h < 1:
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

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
# NanocubeGradientClimb
# Perform nanocube gradient scan
#-------------------------------------------------------------------------------
def NanocubeGradientClimb(StepName, SequenceObj, TestMetrics, TestResults):
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
	
	if LogHelper.AskContinue('Record optical return power from powermeter.') == False:
		return 0
	return 1


#-------------------------------------------------------------------------------
# OptimizePolarizationsMPC201
# Optimize polarizations on both channels sequentially
#-------------------------------------------------------------------------------
def OptimizePolarizationsMPC201(StepName, SequenceObj, TestMetrics, TestResults):
	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1):
		return 0
		
	if LogHelper.AskContinue('Channel 1 plarization is peaked!') == False:
		return 0

	if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=2):
		return 0
	if LogHelper.AskContinue('Channel 2 plarization is peaked!') == False:
		return 0
	return 1


#-------------------------------------------------------------------------------
# LoopbackAlignPowermeter
# "slow" align using the nanocube to move and powermeter for feedback
#-------------------------------------------------------------------------------
def LoopbackAlignPowermeter(StepName, SequenceObj, TestMetrics, TestResults):
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
		
	
	#HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisRelative('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	#HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)
	return 1
	

def LineScans(StepName, SequenceObj, TestMetrics, TestResults):
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

	return 1

#-------------------------------------------------------------------------------
# UVCure
# UV cure the epoxy bond
#-------------------------------------------------------------------------------
def UVCure(StepName, SequenceObj, TestMetrics, TestResults):

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
	# HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(unloadpos)

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
	scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
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



