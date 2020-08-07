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

UseOpticalSwitch = True

ChannelsAnalogSignals = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals')
Nanocube = HardwareFactory.Instance.GetHardwareByName('Nanocube')
Hexapod = HardwareFactory.Instance.GetHardwareByName('Hexapod')
Powermeter = HardwareFactory.Instance.GetHardwareByName('Powermeter')
PolarizationControl = HardwareFactory.Instance.GetHardwareByName('PolarizationControl')
DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
SideCamera = HardwareFactory.Instance.GetHardwareByName('SideCamera')
DownCamRingLightControl = HardwareFactory.Instance.GetHardwareByName('DownCamRingLightControl')
DownCameraStages = HardwareFactory.Instance.GetHardwareByName('DownCameraStages')
SideCamRingLightControl = HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl')
SideCameraStages = HardwareFactory.Instance.GetHardwareByName('SideCameraStages')
MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
IOController = HardwareFactory.Instance.GetHardwareByName('IOControl')

#-------------------------------------------------------------------------------
# SetScanChannel
#
#-------------------------------------------------------------------------------
def SetScanChannel(scan, channel, useOpticalSwitch = False):
	if(useOpticalSwitch):
		scan.Channel = 1;
		scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
		if(channel == 1):
			IOController.SetOutputValue('OpticalSwitch', False)
		else:
			IOController.SetOutputValue('OpticalSwitch', True)
	else:
		scan.Channel = channel
		if(channel == 1):
			scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
			IOController.SetOutputValue('OpticalSwitch', False)
		else:
			scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('BottomChanMonitorSignal')
			IOController.SetOutputValue('OpticalSwitch', True)

	
#-------------------------------------------------------------------------------
# FastOptimizePolarizationScan
# Helper function to optimize polarization
#-------------------------------------------------------------------------------
def FastOptimizePolarizationMPC201(SequenceObj,control_device_name = 'PolarizationControl',feedback_device = 'Powermeter', feedback_channel = 1, mode = 'max', step_size = .05, convergence_band = 0.1):
	polarization_controller = HardwareFactory.Instance.GetHardwareByName(control_device_name)
	if feedback_device == 'Powermeter':
		HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(False)
	polarization_controller_channels = ['1','2','3','4']
	peak_position = [2,2,2,2]
	
	
	PolarizationControl.SetScrambleEnableState(False)
	if PolarizationControl.ReadScrambleEnableState():
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to disable polarization scramble!')
		return False

	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in range(len(polarization_controller_channels)):
		# if not polarization_controller.SetPolarization(1, channel):
			# return False
		peak_position[channel] = polarization_controller.ReadPolarization(polarization_controller_channels[channel])[0]
	
	num_steps = int(2*round(1/step_size,0)) + 1

	converged = False
	# if mode == 'max':
		# last_optimum = -99
	# else:
		# last_optimum = 99
	
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
	last_optimum = current_optimum

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
				if not polarization_controller.SetPolarization(round(next_position,2), polarization_controller_channels[channel]):
					if feedback_device == 'Powermeter':
						HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
					return False
				positions.append(next_position)
				sleep(0.1)
				
				if feedback_device=='Powermeter':
					if (feedback_channel == 1):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1')[1][0])
					elif (feedback_channel == 2):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1')[1][0])
					else:
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel)[1][0])
				elif feedback_device=='HexapodAnalogInput':
					sleep(0.1)
					fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel))
				elif feedback_device=='NanocubeAnalogInput':
					sleep(0.1)
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
				if len(positions) > 200:
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many tries on channel ' + polarization_controller_channels[channel] + "!") # add other devices!!!
					return 0
					
				i += 1
			#set the channel to the max (or min) polarization value found
			if mode == 'max':
				peak_position[channel] = positions[fb_signal.index(max(fb_signal))]
				if not polarization_controller.SetPolarization(round(peak_position[channel],2), polarization_controller_channels[channel]):
						if feedback_device == 'Powermeter':
							HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
						return False
			else:
				peak_position[channel] = positions[fb_signal.index(min(fb_signal))]
				if not polarization_controller.SetPolarization(round(peak_position[channel],2), polarization_controller_channels[channel]):
						if feedback_device == 'Powermeter':
							HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
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
			if feedback_device == 'Powermeter':
				HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
			return False
		if feedback_device=='Powermeter':
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.02f} dBm'.format(current_optimum))
		else:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.03f} V'.format(current_optimum))
		#if abs((current_optimum - last_optimum)/current_optimum) < convergence_band_percent/100.0:
		if (abs((current_optimum - last_optimum)) < convergence_band) and (step_size == 0.01):
		#if (abs((current_optimum - last_optimum)) < convergence_band):
			converged = True
		last_optimum = current_optimum
		step_size = round(step_size/2,2)
		if step_size < 0.01:
			step_size = 0.01
	
	return True


#-------------------------------------------------------------------------------
# GradientSearch
#-------------------------------------------------------------------------------
TopChanMonitorSignal = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
BottomChanMonitorSignal = ChannelsAnalogSignals.FindByName('BottomChanMonitorSignal')

def NanocubeGradientScan(monitor = TopChanMonitorSignal, channel = 1, axis1 = 'Y', axis2 = 'Z'):
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = axis1
	climb.Axis2 = axis2
	climb.MonitorInstrument = monitor
	climb.Channel = channel
	climb.ExecuteOnce = SequenceObj.AutoStep
	climb.ExecuteNoneModal()
	Utility.DelayMS(500)
	chanpos = Nanocube.GetAxesPositions()
	num_IFF_samples = 5
	chan_peak_V = monitor.ReadPower()
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(chanpos[0],chanpos[1],chanpos[2],chan_peak_V))
	retrun (chanpos, chan_peak_V)

def NanocubeSpiralScan(fb_channel, scan_dia_um, threshold = 0, plot_output = False):
	starting_positions = Nanocube.GetAxesPositions()
	if (not fb_channel == 1) and (not  fb_channel == 2):
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube feedback channel must be integer 1 or 2.')
		return 0
	nanocube = HardwareFactory.Instance.GetHardwareByName('Nanocube')
	# get the hexapod alignment algorithm
	scan = nanocube.GetPIAreaScan(Motion.AreaScanType.SPIRAL_CV)
	scan.RoutineName = '1'
	scan.Axis1 = 'Y'
	scan.Axis2 = 'Z'
	scan.Range1 = scan_dia_um
	scan.LineSpacing = 5 #line spacing
	scan.Velocity = 50
	scan.Frequency = 10
	scan.MidPosition1 = 50
	scan.MidPosition2 = 50
	SetScanChannel(scan, fb_channel, UseOpticalSwitch)
	scan.SaveRecordData = plot_output
	# scan.ExecuteOnce = SequenceObj.AutoStep

	# one scan to get initial power
	scan.ExecuteNoneModal()
	if scan.IsSuccess == False:
		Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxesAbsolute(['X', 'Y', 'Z'], starting_positions, Motion.AxisMotionSpeeds.Normal, True)
		return False

	# wait to settle
	sleep(0.500)
	if ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument) < threshold:
		LogHelper.Log('AlignerUtil.NanocubeSpiralScan', LogEventSeverity.Warning, 'Nanocube sprial scan did not achieve minimum required power ({0:.03f} < {1:.03f}).'.format(ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument),threshold))
		Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxesAbsolute(['X', 'Y', 'Z'], starting_positions, Motion.AxisMotionSpeeds.Normal, True)
		return False
	#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'I made it to the end of NanocubeSpiralScan50()!')
	return True