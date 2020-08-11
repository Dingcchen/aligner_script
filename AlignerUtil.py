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
#import statistics
import os.path
import json

#UseOpticalSwitch = True

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
TopChanMonitorSignal = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
BottomChanMonitorSignal = ChannelsAnalogSignals.FindByName('BottomChanMonitorSignal')


#-------------------------------------------------------------------------------
# GetAndCheckUserInput
# Sanitize user input
#-------------------------------------------------------------------------------
def GetAndCheckUserInput(title, message):
	ret = False
	clear = True
	while ret == False:
		ret = UserFormInputDialog.ShowDialog(title, message, clear)
		if ret == True:
			m = re.search('[<>:\"\/\\\|?*]+', UserFormInputDialog.ReturnValue)
			if(m != None):
				if LogHelper.AskContinue('Cannot contain <>:\/\"|?* . Click Yes to continue, No to abort.'):
					clear = False
					ret = False
				else:
					return None
		else:
			return None
	return UserFormInputDialog.ReturnValue

#-------------------------------------------------------------------------------
# SetScanChannel
#
#-------------------------------------------------------------------------------
def SetScanChannel(scan, channel, useOpticalSwitch = False):
	if(useOpticalSwitch):
		if scan is not None:
			scan.Channel = 1
			scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
		output_ch = 1
		if(channel == 1):
			IOController.SetOutputValue('OpticalSwitch', False)
		else:
			IOController.SetOutputValue('OpticalSwitch', True)
	else:
		output_ch = channel
		if scan is not None:
			scan.Channel = channel
			if(channel == 1):
				scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
				#IOController.SetOutputValue('OpticalSwitch', False)
			else:
				scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('BottomChanMonitorSignal')
				#IOController.SetOutputValue('OpticalSwitch', True)
	
	return output_ch


def ReadMonitorSignal(channel, n_measurements = 10):
	#channel = SetScanChannel(None, channel, useOpticalSwitch = useOpticalSwitch)
	if channel == 1:
		ChannelsAnalogSignals.ReadValue(ChannelsAnalogSignals.FindByName('TopChanMonitorSignal'))
	else:
		ChannelsAnalogSignals.ReadValue(ChannelsAnalogSignals.FindByName('BottomChanMonitorSignal'))

	measurements = []
	for i in range(n_measurements):
		if channel == 1:
			measurements.append(ChannelsAnalogSignals.ReadValue(ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')))
		else:
			measurements.append(ChannelsAnalogSignals.ReadValue(ChannelsAnalogSignals.FindByName('BottomChanMonitorSignal')))
		sleep(.01)
	
	return (mean(measurements), stdev(measurements),min(measurements),max(measurements))

	
#-------------------------------------------------------------------------------
# FastOptimizePolarizationScan
# Helper function to optimize polarization
#-------------------------------------------------------------------------------
def FastOptimizePolarizationMPC201(SequenceObj,control_device_name = 'PolarizationControl',feedback_device = 'Powermeter', feedback_channel = 1, mode = 'max', convergence_band = 0.1, coarse_scan = False):
	step_size = .05	
	if coarse_scan:
		step_size = .1

	polarization_controller = HardwareFactory.Instance.GetHardwareByName(control_device_name)
	if feedback_device == 'Powermeter':
		HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(False)
	polarization_controller_channels = ['1','2','3','4']
	peak_position = [2,2,2,2]
	
	
	PolarizationControl.SetScrambleEnableState(False)
	if PolarizationControl.ReadScrambleEnableState():
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to disable polarization scramble!')
		return None

	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in range(len(polarization_controller_channels)):
		# if not polarization_controller.SetPolarization(1, channel):
			# return None
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
		current_optimum = Nanocube.ReadAnalogInput(feedback_channel)
	else:
		if feedback_device == 'Powermeter':
			HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
		return None
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
					return None
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
					fb_signal.append(Nanocube.ReadAnalogInput(feedback_channel))
				else:
					if feedback_device == 'Powermeter':
						HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
					return None
				if SequenceObj.Halt:
					if feedback_device == 'Powermeter':
						HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
					return None
				
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
					return None
					
				i += 1
			#set the channel to the max (or min) polarization value found
			if mode == 'max':
				peak_position[channel] = positions[fb_signal.index(max(fb_signal))]
				if not polarization_controller.SetPolarization(round(peak_position[channel],2), polarization_controller_channels[channel]):
						if feedback_device == 'Powermeter':
							HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
						return None
			else:
				peak_position[channel] = positions[fb_signal.index(min(fb_signal))]
				if not polarization_controller.SetPolarization(round(peak_position[channel],2), polarization_controller_channels[channel]):
						if feedback_device == 'Powermeter':
							HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
						return None
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
			current_optimum = Nanocube.ReadAnalogInput(feedback_channel)
		else:
			if feedback_device == 'Powermeter':
				HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(True)
			return None
		if feedback_device=='Powermeter':
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.02f} dBm'.format(current_optimum))
		else:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.03f} V'.format(current_optimum))
		#if abs((current_optimum - last_optimum)/current_optimum) < convergence_band_percent/100.0:
		if coarse_scan and (step_size <= 0.05):
			converged = True

		if (abs((current_optimum - last_optimum)) < convergence_band) and (step_size == 0.01):
		#if (abs((current_optimum - last_optimum)) < convergence_band):
			converged = True

		last_optimum = current_optimum
		step_size = round(step_size/2,2)
		if step_size < 0.01:
			step_size = 0.01
	
	return MPC201.ReadPolarization('1,2,3,4')

def ScramblePolarizationMPC201(SequenceObj):
	PolarizationControl.SetScrambleMethod(ScrambleMethodType.Tornado)
	PolarizationControl.SetScrambleRate(2000) #Hz
	PolarizationControl.SetScrambleEnableState(True)
	if not PolarizationControl.ReadScrambleEnableState():
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to enable polarization scramble!')
		return False
	return True

def SetPolarizationsMPC201(SequenceObj, polarization):
	polarization_controller_channels = ['1','2','3','4']	
	
	PolarizationControl.SetScrambleEnableState(False)
	if PolarizationControl.ReadScrambleEnableState():
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to disable polarization scramble!')
		return None

	#set all polarization controller channels to a predefined value (because reasons???)
	for i in range(4):
		if not polarization_controller.SetPolarization(polarization[i], polarization_controller_channels[i]):
			return None
		if not polarization_controller.ReadPolarization(polarization_controller_channels[i])[0] != round(polarization[i],2):
			sleep(0.2)
			if not polarization_controller.SetPolarization(polarization[i], polarization_controller_channels[i]):
				return None
			if not polarization_controller.ReadPolarization(polarization_controller_channels[i])[0] != round(polarization[i],2):
				return False
		sleep(0.2)
	return True


#-------------------------------------------------------------------------------
# NanocubeGradientClimb
# set up and execute Nanocube gradient climb with standard parameters
#-------------------------------------------------------------------------------
def NanocubeGradientClimb(SequenceObj, fb_channel, threshold = 0, axis1 = 'Y', axis2 = 'Z', UseOpticalSwtich = False):
	starting_positions = Nanocube.GetAxesPositions()

	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = axis1
	climb.Axis2 = axis2
	SetScanChannel(climb, fb_channel, UseOpticalSwitch)
	#climb.MonitorInstrument = monitor
	#climb.Channel = channel
	#climb.ExecuteOnce = SequenceObj.AutoStep
	climb.ExecuteNoneModal()
	if not scan.IsSuccess:
		Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		#Nanocube.MoveAxesAbsolute(['X', 'Y', 'Z'], starting_positions, Motion.AxisMotionSpeeds.Normal, True)
		return False

	sleep(0.500) # wait to settle
	for i in range(20): # in case of scrambling polarization, check multiple times for power to exceed threshold
		if ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument) >= threshold:
			return True
		sleep(0.01)


	LogHelper.Log('AlignerUtil.NanocubeGradientClimb', LogEventSeverity.Warning, 'Nanocube gradient climb did not achieve minimum required power ({0:.03f} V < {1:.03f} V).'.format(ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument),threshold))
	Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
	#Nanocube.MoveAxesAbsolute(['X', 'Y', 'Z'], starting_positions, Motion.AxisMotionSpeeds.Normal, True)
	return False

	
	#chanpos = Nanocube.GetAxesPositions()
	#num_IFF_samples = 5
	#chan_peak_V = monitor.ReadPower()
	#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(chanpos[0],chanpos[1],chanpos[2],chan_peak_V))
	return True

def NanocubeSpiralScan(SequenceObj, fb_channel, scan_dia_um = 50, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = 50, plot_output = False, UseOpticalSwtich = False):
	starting_positions = Nanocube.GetAxesPositions()

	# get the alignment algorithm
	scan = Nanocube.GetPIAreaScan(Motion.AreaScanType.SPIRAL_CV)
	scan.RoutineName = '1'
	scan.Axis1 = axis1
	scan.Axis2 = axis2
	scan.Range1 = scan_dia_um
	scan.LineSpacing = 5 #line spacing
	scan.Velocity = speed
	#scan.Frequency = 10
	scan.UseCurrentPosition = False # use provided mid positions
	scan.MidPosition1 = 50
	scan.MidPosition2 = 50
	SetScanChannel(scan, fb_channel, UseOpticalSwitch)
	scan.SaveRecordData = plot_output
	# scan.ExecuteOnce = SequenceObj.AutoStep

	scan.ExecuteNoneModal()
	if not scan.IsSuccess:
		# Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
		# Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		# Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxesAbsolute(array(['X', 'Y', 'Z']), starting_positions, Motion.AxisMotionSpeeds.Normal, True)
		return False

	
	sleep(0.500) # wait to settle
	for i in range(20): # in case of scrambling polarization, check multiple times for power to exceed threshold
		if ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument) >= threshold:
			return True
		sleep(0.01)

	Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	LogHelper.Log('AlignerUtil.NanocubeSpiralScan', LogEventSeverity.Warning, 'Nanocube sprial scan did not achieve minimum required power ({0:.03f} < {1:.03f}).'.format(ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument),threshold))
	Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
	#Nanocube.MoveAxesAbsolute(['X', 'Y', 'Z'], starting_positions, Motion.AxisMotionSpeeds.Normal, True)
	return False

#-------------------------------------------------------------------------------
# HexapodSpiralScan
# set up and execute hexapod gradient climb with standard parameters
#-------------------------------------------------------------------------------
def HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .006, plot_output = False, UseOpticalSwtich = False):
	starting_positions = hexapod.GetAxesPositions()

	# get the hexapod alignment algorithm
	scan = Hexapod.GetPIAreaScan(Motion.AreaScanType.SPIRAL_CV)
	scan.RoutineName = '1'
	scan.Axis1 = axis1
	scan.Axis2 = axis2
	scan.Range1 = scan_dia_mm
	scan.LineSpacing = .010 #line spacing mm
	scan.Velocity = speed # mm/s
	#scan.Frequency = 4 # not used for cv spiral scan

	scan.UseCurrentPosition = True
	SetScanChannel(scan, fb_channel, UseOpticalSwitch)
	scan.SaveRecordData = plot_output
	# scan.ExecuteOnce = SequenceObj.AutoStep

	scan.ExecuteNoneModal()
	if not scan.IsSuccess:
		Hexapod.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
		Hexapod.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		Hexapod.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		#Hexapod.MoveAxesAbsolute(['X', 'Y', 'Z'], starting_positions, Motion.AxisMotionSpeeds.Normal, True)
		return False

	
	sleep(0.500) # wait to settle
	for i in range(20): # in case of scrambling polarization, check multiple times for power to exceed threshold
		if ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument) >= threshold:
			return True
		sleep(0.01)

	Hexapod.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	LogHelper.Log('AlignerUtil.NanocubeSpiralScan', LogEventSeverity.Warning, 'Nanocube sprial scan did not achieve minimum required power ({0:.03f} < {1:.03f}).'.format(ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument),threshold))
	Hexapod.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
	#Hexapod.MoveAxesAbsolute(['X', 'Y', 'Z'], starting_positions, Motion.AxisMotionSpeeds.Normal, True)
	return False

def OptimizeRollAngle(SequenceObj, WG2WG_dist_mm, use_polarization_controller, max_z_difference_um = 1, UseOpticalSwtich = False, threshold = 0, speed = 50):

	# set up a loop to zero in on the roll angle
	topchanpos = []
	bottomchanpos = []
	retries = 0
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Begin roll (U) adjust...')

	n_measurements = 5

	if use_polarization_controller:
		if not ScramblePolarizationMPC201(SequenceObj):
			return False
		top_ch_polarization_position = []
		bottom_ch_polarization_position = []

	while retries < 5 and not SequenceObj.Halt:
		Nanocube.GetHardwareStateTree().ActivateState('Center')
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V (STD {4:.3f}) @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(topchanpos[0],topchanpos[1],topchanpos[2],top_channel_power[0],top_channel_power[1]))
		#SetScanChannel(scan, 1, UseOpticalSwitch)
		#scan_ch = SetScanChannel(climb, 1, UseOpticalSwitch)

		if ReadMonitorSignal(SetScanChannel(None, 1, UseOpticalSwtich))[3] < minpower: #check max signal found when using scrambler
			if not NanocubeSpiralScan(SequenceObj, 1, threshold = threshold, UseOpticalSwtich = UseOpticalSwtich):
				if not NanocubeSpiralScan(SequenceObj, 1,scan_dia_um=90, threshold = threshold, UseOpticalSwtich = UseOpticalSwtich):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1.')
					return False
		
		if use_polarization_controller and retries == 0:
			top_ch_polarization_position = FastOptimizePolarizationMPC201(SequenceObj, feedback_device = 'NanocubeAnalogInput', feedback_channel = 1, coarse_scan = True)
		elif use_polarization_controller:
			if not SetPolarizationsMPC201(SequenceObj, top_ch_polarization_position):
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to set the polarization!')
				return False


		if not NanocubeGradientClimb(SequenceObj, 1, threshold = threshold, UseOpticalSwtich = UseOpticalSwtich) or SequenceObj.Halt:
			return False
		
		# remember the peak top channel position
		topchanpos = Nanocube.GetAxesPositions()
		top_chan_peak_V = ReadMonitorSignal(SetScanChannel(None, 1, UseOpticalSwtich))
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V (STD {4:.3f}) @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(topchanpos[0],topchanpos[1],topchanpos[2],top_channel_power[0],top_channel_power[1]))
		

		# repeat scan for the second channel
		#SetScanChannel(scan, 2, UseOpticalSwitch)
		#scan_ch = SetScanChannel(climb, 2, UseOpticalSwitch)

		if use_polarization_controller and retries == 0:
			if not ScramblePolarizationMPC201(SequenceObj):
				return False

		if ReadMonitorSignal(SetScanChannel(None, 2, UseOpticalSwtich))[3] < minpower: #check max signal found when using scrambler
			if not NanocubeSpiralScan(SequenceObj, 2, threshold = threshold, UseOpticalSwtich = UseOpticalSwtich):
				if not NanocubeSpiralScan(SequenceObj, 2,scan_dia_um=90, threshold = threshold, UseOpticalSwtich = UseOpticalSwtich):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 2.')
					return False
		
		if use_polarization_controller and retries == 0:
			bottom_ch_polarization_position = FastOptimizePolarizationMPC201(SequenceObj, feedback_device = 'NanocubeAnalogInput', feedback_channel = 1, coarse_scan = True)
		elif use_polarization_controller:
			if not SetPolarizationsMPC201(SequenceObj, bottom_ch_polarization_position):
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to set the polarization!')
				return False

		if not NanocubeGradientClimb(SequenceObj, 2, threshold = threshold, UseOpticalSwtich = UseOpticalSwtich) or SequenceObj.Halt:
			return False
		
		# get the final position of second channel
		bottomchanpos = Nanocube.GetAxesPositions()
		bottom_chan_peak_V = ReadMonitorSignal(SetScanChannel(None, 2, UseOpticalSwtich))
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 2 peak: {3:.3f}V (STD {4:.3f}) @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(bottomchanpos[0],bottomchanpos[1],bottomchanpos[2],bottom_chan_peak_V[0],bottom_chan_peak_V[1]))

		# double check and readjust roll if necessary
		# calculate the roll angle
		h = Math.Abs(topchanpos[2] - bottomchanpos[2])
		if h < max_z_difference_um:
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

		# calculate the roll angle
		r = Utility.RadianToDegree(Math.Asin(h / (WG2WG_dist_mm*1000)))
		rollangle = -r
		if topchanpos[2] > bottomchanpos[2]:
		   rollangle = -rollangle

		# adjust the roll angle again
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		Utility.DelayMS(500)

		retries += 1

	if retries >= 5:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Exceeded allowed number of retries!')
		return False

	# balanced position
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	Nanocube.MoveAxisAbsolute('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	Nanocube.MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)

	Hexapod.MoveAxisRelative('Y', -(50-ymiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisRelative('Z', -(50-zmiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)

	return True

def load_alignment_results(SequenceObj):
	#filename = os.path.join(SequenceObj.TestResults.OutputDestinationConfiguration, 'temp_alignment_results.json')
	filename = '..\\Data\\temp_alignment_results.json'
	with open(filename, 'r') as outfile:
		return json.load(outfile)
	
def save_alignment_results(SequenceObj, alignment_results):
	filename = '..\\Data\\temp_alignment_results.json'
	with open(filename, 'w') as outfile:
		json.dump(alignment_results, outfile, indent=2 , sort_keys=True)
	return True