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
# import statistics
import os.path
import re

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
SGRX8Switch = HardwareFactory.Instance.GetHardwareByName('JGRSwitch')

def loopback_test(channel):
	SGRX8Switch.SetClosePoints(1,channel)
	sleep(1)
	SGRX8Switch.SetClosePoints(2,channel)
	sleep(1)
	power1 = (Powermeter.ReadPowers('1:1'))[1][0]
	power2 = (Powermeter.ReadPowers('2:1'))[1][0]
	return (power1, power2)


def LoopbackCycleChn1to4(SequenceObj, csvwriter, loop=100):
	## cycle through channels 1,2,3,4,1,2,...
	csvwriter.writerow(["data line", "ch1_power80", "ch1_power20", "ch2_power80", "ch2_power20", "ch3_power80", "ch3_power20", "ch4_power80", "ch4_power20"])
	for i in range(loop):
		result_line = [i]
		for j in range(4):
			(power80, power20) = loopback_test(j+1)
			result_line.append(power80)
			result_line.append(power20)
		csvwriter.writerow(result_line)
		if SequenceObj.Halt:
			return 0

def LoopbackCycleRandom(SequenceObj, csvwriter):
	### cycle through random channels for a better test of repeatability on the switch
	csvwriter.writerow(['measurement timestamp', 'switch channel', "switch loopback", "laser tap 20pct"])
	last_switch_channel = 0
	number_samples = 500
	for i in range(number_samples):
		result_line = [datetime.now().strftime("%d/%m/%Y %H:%M:%S"), random.randint(1,4)]
		# while result_line[1] == last_switch_channel:
		# 	result_line[1] = [random.randint(1,4)]

		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Measuring switch channel {0}... {1}/{2}'.format(result_line[1],i,number_samples))
		(power80, power20) = loopback_test(result_line[1])
		result_line.append(power80)
		result_line.append(power20)
		
		csvwriter.writerow(result_line)

		#last_switch_channel = result_line[1]
		if SequenceObj.Halt:
				return 0



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
					return False
		else:
			return False
	return UserFormInputDialog.ReturnValue

#-------------------------------------------------------------------------------
# SetScanChannel
#
#-------------------------------------------------------------------------------
def SetScanChannel(scan, channel, UseOpticalSwitch = False, LaserSwitch='OpticalSwitch2X2'):
	if(UseOpticalSwitch):
		LogHelper.Log('SetScanChannel', LogEventSeverity.Alert, 'switch {0:s} to channel {1}.'.format(LaserSwitch, channel))
		if scan is not None:
			scan.Channel = 1
			scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
		output_ch = 1
		if(channel == 1):
			IOController.SetOutputValue(LaserSwitch, False)
		else:
			IOController.SetOutputValue(LaserSwitch, True)
	else:
		output_ch = channel
		if scan is not None:
			scan.Channel = channel
			if(channel == 1):
				scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('TopChanMonitorSignal')
				#IOController.SetOutputValue(LaserSwitch, False)
			else:
				scan.MonitorInstrument = ChannelsAnalogSignals.FindByName('BottomChanMonitorSignal')
				#IOController.SetOutputValue(LaserSwitch, True)
	
	return output_ch


def ReadMonitorSignal(channel, n_measurements = 10):
	sleep(0.2)
	if n_measurements < 1:
		return False
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
	
	mean = sum(measurements)/len(measurements)
	if n_measurements > 1:
		stdev = (sum(map(lambda x: (x-mean)**2, measurements))/(n_measurements-1))**0.5
	else:
		stdev = None
	return (mean, stdev, min(measurements), max(measurements))

	
#-------------------------------------------------------------------------------
# FastOptimizePolarizationScan
# Helper function to optimize polarization
#-------------------------------------------------------------------------------
def FastOptimizePolarizationMPC201(SequenceObj,control_device_name = 'PolarizationControl',feedback_device = 'Powermeter', feedback_channel = 1, mode = 'max', convergence_band = 0.1, coarse_scan = False):
	def ReadPower():
		if feedback_device=='Powermeter':
			if (feedback_channel == 1):
				power = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1'))[1][0]
			elif (feedback_channel == 2):
			    power = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1'))[1][0]
			else:
			    power = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel))[1][0]
		elif feedback_device=='HexapodAnalogInput':
		    power = HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel)
		elif feedback_device=='NanocubeAnalogInput':
		    power = Nanocube.ReadAnalogInput(feedback_channel)
		return power

	step_size = .05	
	if coarse_scan:
		step_size = .1

	polarization_controller = HardwareFactory.Instance.GetHardwareByName(control_device_name)
	if feedback_device == 'Powermeter':
		HardwareFactory.Instance.GetHardwareByName(feedback_device).AutoUpdates(False)
	polarization_controller_channels = ['1','2','3','4']
	peak_position = [2,2,2,2]
	
	
	PolarizationControl.SetScrambleEnableState(False)
	sleep(0.2)
	if PolarizationControl.ReadScrambleEnableState():
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to disable polarization scramble!')
		return False
	sleep(0.2)
	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in range(len(polarization_controller_channels)):
		peak_position[channel] = polarization_controller.ReadPolarization(polarization_controller_channels[channel])[0]
	
	num_steps = int(2*round(1/step_size,0)) + 1

	converged = False
	
	current_optimum = ReadPower()
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
				
				power = ReadPower()
				fb_signal.append(power)

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
					return False
					
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
		current_optimum = ReadPower()

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
	
	return (PolarizationControl.ReadPolarization('1,2,3,4'), last_optimum)


def ScramblePolarizationMPC201(SequenceObj):
	PolarizationControl.SetScrambleMethod(ScrambleMethodType.Tornado)
	sleep(0.2)
	#PolarizationControl.SetScrambleRate(2000) #Hz
	sleep(0.2)
	PolarizationControl.SetScrambleEnableState(True)
	sleep(0.2)
	if not PolarizationControl.ReadScrambleEnableState():
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to enable polarization scramble!')
		return False
	return True

def SetPolarizationsMPC201(SequenceObj, polarization):
	polarization_controller_channels = ['1','2','3','4']	
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Setting polarization to [{0:.2f}, {1:.2f}, {2:.2f}, {3:.2f}]...'.format(polarization[0],polarization[1],polarization[2],polarization[3]))

	PolarizationControl.SetScrambleEnableState(False)
	sleep(0.2)
	if PolarizationControl.ReadScrambleEnableState():
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to disable polarization scramble!')
		return False

	#set all polarization controller channels to a predefined value (because reasons???)
	for i in range(4):
		if not PolarizationControl.SetPolarization(polarization[i], polarization_controller_channels[i]):
			return False
		sleep(0.2)
		if not abs(PolarizationControl.ReadPolarization(polarization_controller_channels[i])[0] - round(polarization[i],2)) <= 0.02:
			sleep(0.2)
			if not PolarizationControl.SetPolarization(polarization[i], polarization_controller_channels[i]):
				# LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Attempted to set polarization to !')
				return False
			if not abs(PolarizationControl.ReadPolarization(polarization_controller_channels[i])[0] - round(polarization[i],2)) <= 0.02:
				return False
		sleep(0.2)
	return True


#-------------------------------------------------------------------------------
# NanocubeGradientClimb
# set up and execute Nanocube gradient climb with standard parameters
#-------------------------------------------------------------------------------
def NanocubeGradientClimb(SequenceObj, fb_channel, threshold = 0, axis1 = 'Y', axis2 = 'Z', UseOpticalSwitch = False):
	starting_positions = Nanocube.GetAxesPositions()

	LogHelper.Log('AlignerUtil.NanocubeGradientClimb', LogEventSeverity.Alert, 'Start gradient climb.')
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = axis1
	climb.Axis2 = axis2
	SetScanChannel(climb, fb_channel, UseOpticalSwitch)
	#climb.MonitorInstrument = monitor
	#climb.Channel = channel
	#climb.ExecuteOnce = SequenceObj.AutoStep
	climb.ExecuteNoneModal()
	if not climb.IsSuccess:
		# Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
		# Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		# Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z']), Array[float](starting_positions), Motion.AxisMotionSpeeds.Normal, True)
		LogHelper.Log('AlignerUtil.NanocubeGradientClimb', LogEventSeverity.Alert, 'Gradient climb fails.')
		return False

	sleep(0.500) # wait to settle
	for i in range(20): # in case of scrambling polarization, check multiple times for power to exceed threshold
		data = ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument) 
		if data >= threshold:
			LogHelper.Log('AlignerUtil.NanocubeGradientClimb', LogEventSeverity.Alert, 'Gradient climb success with power {0:.3f}.'.format(data))
			return True
		sleep(0.01)


	LogHelper.Log('AlignerUtil.NanocubeGradientClimb', LogEventSeverity.Warning, 'Nanocube gradient climb did not achieve minimum required power ({0:.03f} V < {1:.03f} V).'.format(ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument),threshold))
	# Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	# Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	# Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z']), Array[float](starting_positions), Motion.AxisMotionSpeeds.Normal, True)
	return False

	
	#chanpos = Nanocube.GetAxesPositions()
	#num_IFF_samples = 5
	#chan_peak_V = monitor.ReadPower()
	#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(chanpos[0],chanpos[1],chanpos[2],chan_peak_V))
	return True

def NanocubeSpiralScan(SequenceObj, fb_channel, scan_dia_um = 50, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = 10, plot_output = False, UseOpticalSwitch = False):
	starting_positions = Nanocube.GetAxesPositions()
	Nanocube.MoveAxisRelative('X', -30, Motion.AxisMotionSpeeds.Slow, True)
	# get the alignment algorithm
	scan = Nanocube.GetPIAreaScan(Motion.AreaScanType.SPIRAL_CV)
	scan.RoutineName = '1'
	scan.Axis1 = axis1
	scan.Axis2 = axis2
	scan.Range1 = scan_dia_um
	scan.LineSpacing = 5 #line spacing
	scan.Velocity = speed
	#scan.Frequency = 10
	scan.UseCurrentPosition = True # use provided mid positions
	scan.MidPosition1 = 50
	scan.MidPosition2 = 50
	SetScanChannel(scan, fb_channel, UseOpticalSwitch)
	scan.SaveRecordData = plot_output
	LogHelper.Log('NanocubeSpiralScan', LogEventSeverity.Alert, 'scan dia {0}'.format(scan_dia_um))
	# scan.ExecuteOnce = SequenceObj.AutoStep
	if not SequenceObj.Halt:
		scan.ExecuteNoneModal()
	else:
		Nanocube.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z']), Array[float](starting_positions), Motion.AxisMotionSpeeds.Normal, True)
		return False
	if not scan.IsSuccess:
		# Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
		# Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		# Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		Nanocube.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z']), Array[float](starting_positions), Motion.AxisMotionSpeeds.Normal, True)
		return False

	
	sleep(0.500) # wait to settle
	for i in range(20): # in case of scrambling polarization, check multiple times for power to exceed threshold
		if ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument) >= threshold:
			Nanocube.MoveAxisAbsolute('X',starting_positions[0], Motion.AxisMotionSpeeds.Slow,True)
			return True
		sleep(0.01)

	# Nanocube.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	LogHelper.Log('AlignerUtil.NanocubeSpiralScan', LogEventSeverity.Warning, 'Nanocube sprial scan did not achieve minimum required power ({0:.03f} < {1:.03f}).'.format(ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument),threshold))
	# Nanocube.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	# Nanocube.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z']), Array[float](starting_positions), Motion.AxisMotionSpeeds.Normal, True)
	return False

#-------------------------------------------------------------------------------
# HexapodSpiralScan
# set up and execute hexapod gradient climb with standard parameters
#-------------------------------------------------------------------------------
def HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .010, plot_output = False, UseOpticalSwitch = False):
	starting_positions = Hexapod.GetAxesPositions()

	# get the hexapod alignment algorithm
	scan = Hexapod.GetPIAreaScan(Motion.AreaScanType.SPIRAL_CV)
	scan.RoutineName = '1'
	scan.Axis1 = axis1
	scan.Axis2 = axis2
	scan.Range1 = scan_dia_mm
	scan.LineSpacing = 0.010 #line spacing mm
	scan.Velocity = speed # mm/s
	scan.Threshold = threshold
	#scan.Frequency = 4 # not used for cv spiral scan

	scan.UseCurrentPosition = True
	SetScanChannel(scan, fb_channel, UseOpticalSwitch)
	# in hexepod the analog channel channel 1 and 2 is actually channel 5 and 6 of the C877 controller
	scan.Channel = scan.Channel + 4
	scan.SaveRecordData = plot_output
	# scan.ExecuteOnce = SequenceObj.AutoStep

	scan.ExecuteNoneModal()
	if not scan.IsSuccess:
		# Hexapod.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
		# Hexapod.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
		# Hexapod.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
		Hexapod.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z', 'U', 'V', 'W']), Array[float](starting_positions), Motion.AxisMotionSpeeds.Normal, True)
		return False

	
	sleep(0.500) # wait to settle
	for i in range(20): # in case of scrambling polarization, check multiple times for power to exceed threshold
		if ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument) >= threshold:
			return True
		sleep(0.01)

	# Hexapod.MoveAxisAbsolute('X', starting_positions[0], Motion.AxisMotionSpeeds.Normal, True)
	LogHelper.Log('AlignerUtil.HexapodSpiralScan', LogEventSeverity.Warning, 'Hexapod sprial scan did not achieve minimum required power ({0:.03f} < {1:.03f}).'.format(ChannelsAnalogSignals.ReadValue(scan.MonitorInstrument),threshold))
	# Hexapod.MoveAxisAbsolute('Y', starting_positions[1], Motion.AxisMotionSpeeds.Normal, True)
	# Hexapod.MoveAxisAbsolute('Z', starting_positions[2], Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z', 'U', 'V', 'W']), Array[float](starting_positions), Motion.AxisMotionSpeeds.Normal, True)
	return False

def OptimizeRollAngle(SequenceObj, WG2WG_dist_mm, use_polarization_controller,  threshold,max_z_difference_um = 1, UseOpticalSwitch = False, speed = 50):

	# set up a loop to zero in on the roll angle
	top_chan_position = []
	bottom_chan_position = []
	top_chan_peak_power = ()
	bottom_chan_peak_power = ()

	retries = 0
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Begin roll (U) adjust...')

	n_measurements = 5
	

	if use_polarization_controller:
		if not ScramblePolarizationMPC201(SequenceObj):
			return False
		top_ch_polarization_position = []
		bottom_ch_polarizttion_position = []

	while retries < 5 and not SequenceObj.Halt:
		Nanocube.GetHardwareStateTree().ActivateState('Center')
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V (STD {4:.3f}) @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(top_chan_position[0],top_chan_position[1],top_chan_position[2],top_channel_power[0],top_channel_power[1]))
		#SetScanChannel(scan, 1, UseOpticalSwitch)
		#scan_ch = SetScanChannel(climb, 1, UseOpticalSwitch)

		if ReadMonitorSignal(SetScanChannel(None, 1, UseOpticalSwitch))[3] < threshold: #check max signal found when using scrambler
			if not NanocubeSpiralScan(SequenceObj, 1, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
				if not NanocubeSpiralScan(SequenceObj, 1,scan_dia_um=90, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1.')
					return False
		
		if use_polarization_controller and retries == 0:
			(top_ch_polarization_position, optimized_power) = FastOptimizePolarizationMPC201(SequenceObj, feedback_device = 'NanocubeAnalogInput', feedback_channel = 1, coarse_scan = False)
		elif use_polarization_controller:
			if not SetPolarizationsMPC201(SequenceObj, top_ch_polarization_position):
				if not SetPolarizationsMPC201(SequenceObj, top_ch_polarization_position):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to set the top channel polarization!')
					return False

		sleep(0.5)
		if not NanocubeGradientClimb(SequenceObj, 1, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch) or SequenceObj.Halt:
			return False
		
		# remember the peak top channel position
		top_chan_position = Nanocube.GetAxesPositions()
		top_chan_peak_power = ReadMonitorSignal(SetScanChannel(None, 1, UseOpticalSwitch))
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 peak: {3:.3f}V (STD {4:.3f}) @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(top_chan_position[0],top_chan_position[1],top_chan_position[2], top_chan_peak_power[0], top_chan_peak_power[1]))
		

		# repeat scan for the second channel
		#SetScanChannel(scan, 2, UseOpticalSwitch)
		#scan_ch = SetScanChannel(climb, 2, UseOpticalSwitch)

		if use_polarization_controller and retries == 0:
			if not ScramblePolarizationMPC201(SequenceObj):
				return False
		sleep(0.2)
		if ReadMonitorSignal(SetScanChannel(None, 2, UseOpticalSwitch))[3] < threshold: #check max signal found when using scrambler
			if not NanocubeSpiralScan(SequenceObj, 2, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
				if not NanocubeSpiralScan(SequenceObj, 2,scan_dia_um=90, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 2.')
					return False
		
		if use_polarization_controller and retries == 0:
			(bottom_ch_polarization_position, optimized_power) = FastOptimizePolarizationMPC201(SequenceObj, feedback_device = 'NanocubeAnalogInput', feedback_channel = 1, coarse_scan = False)
		elif use_polarization_controller:
			if not SetPolarizationsMPC201(SequenceObj, bottom_ch_polarization_position):
				if not SetPolarizationsMPC201(SequenceObj, bottom_ch_polarization_position):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to set the bottom channel polarization!')
					return False
		sleep(0.5)
		if not NanocubeGradientClimb(SequenceObj, 2, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch) or SequenceObj.Halt:
			return False
		
		# get the final position of second channel
		bottom_chan_position = Nanocube.GetAxesPositions()
		bottom_chan_peak_power = ReadMonitorSignal(SetScanChannel(None, 2, UseOpticalSwitch))
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 2 peak: {3:.3f}V (STD {4:.3f}) @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(bottom_chan_position[0],bottom_chan_position[1],bottom_chan_position[2],bottom_chan_peak_power[0],bottom_chan_peak_power[1]))

		# double check and readjust roll if necessary
		# calculate the roll angle
		h = top_chan_position[2] - bottom_chan_position[2]
		if Math.Abs(h) < max_z_difference_um:
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

		# calculate the roll angle
		r = Utility.RadianToDegree(Math.Asin(h / (WG2WG_dist_mm*1000)))
		# Reverse the roll angle. 
		rollangle = 0.5 * r
		# if top_chan_position[2] > bottom_chan_position[2]:
		#	rollangle = -rollangle
		if rollangle > 0.5:
			rollangle = 0.5
		elif rollangle < -0.5:
			rollangle = -0.5

		# balanced position
		ymiddle = (top_chan_position[1] + bottom_chan_position[1]) / 2
		zmiddle = (top_chan_position[2] + bottom_chan_position[2]) / 2
		Nanocube.MoveAxisAbsolute('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
		Nanocube.MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)

		Hexapod.MoveAxisRelative('Y', -(50-ymiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)
		Hexapod.MoveAxisRelative('Z', -(50-zmiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)

		# adjust the roll angle 
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)

		retries += 1

	if retries >= 5:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Exceeded allowed number of retries!')
		return False

	# balanced position
	ymiddle = (top_chan_position[1] + bottom_chan_position[1]) / 2
	zmiddle = (top_chan_position[2] + bottom_chan_position[2]) / 2
	Nanocube.MoveAxisAbsolute('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	Nanocube.MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)

	Hexapod.MoveAxisRelative('Y', -(50-ymiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisRelative('Z', -(50-zmiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)

	sleep(0.5)

	output = {'top_chan_balanced_power':ReadMonitorSignal(SetScanChannel(None, 1, UseOpticalSwitch)),
				'bottom_chan_balanced_power':ReadMonitorSignal(SetScanChannel(None, 2, UseOpticalSwitch)),
				'balanced_position':get_positions(SequenceObj),
				'top_chan_peak_power':top_chan_peak_power,
				'top_chan_nanocube_peak_position':list(top_chan_position),
				'bottom_chan_nanocube_peak_position':list(bottom_chan_position),
				'bottom_chan_peak_power':bottom_chan_peak_power}

	return output

def get_positions(SequenceObj):
    output = {}
    if Hexapod is not None:
        output['Hexapod'] = map(lambda x: round(x,4), list(Hexapod.GetAxesPositions()))
    if Nanocube is not None:
        output['Nanocube'] = map(lambda x: round(x,3), list(Nanocube.GetAxesPositions()))
    return output

def set_positions(SequenceObj, positions):
	if 'Hexapod' in positions.keys():
		if not Hexapod.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z', 'U', 'V', 'W']), Array[float](positions['Hexapod']), Motion.AxisMotionSpeeds.Normal, True):
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move Hexapod to {0:s}.'.format(str(positions['Hexapod'])))
			return False
	if 'Nanocube' in positions.keys():
		if not Nanocube.MoveAxesAbsolute(Array[String](['X', 'Y', 'Z']), Array[float](positions['Nanocube']), Motion.AxisMotionSpeeds.Normal, True):
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move Nanocube to {0:s}.'.format(str(positions['Nanocube'])))
			return False
	return True


LoopbackFAU1to4 = (False, 2, 3, '1 loopback to 4')
LoopbackFAU4to1 = (True,  2, 3, '4 loopback to 1')
LoopbackFAU2to3 = (False, 3, 2, '2 loopback to 3')
LoopbackFAU3to2 = (True , 3, 2, '3 loopback to 2')

CrossTalkFAU1to3 = (False, 2, 2, '1 cross talk to 3')
CrossTalkFAU4to2 = (True,  3, 3, '4 cross talk to 2')
CrossTalkFAU2to4 = (False, 3, 3, '2 cross talk to 4')
CrossTalkFAU3to1 = (True,  2, 2, '3 cross talk to 1')

testcases = (LoopbackFAU1to4, LoopbackFAU4to1, LoopbackFAU2to3, LoopbackFAU3to2)

def SwitchLaserAndLoopbackChannel(swlist, LaserSwitch='OpticalSwitch2X2', comment='FAU channel '):
	IOController.SetOutputValue(LaserSwitch, swlist[0])
	LogHelper.Log('SwitchLaserAndLoopbackChannel', LogEventSeverity.Alert, 'switch {0:s} to channel {1}.'.format(LaserSwitch, swlist[0]))
	SGRX8Switch.SetClosePoints(1,swlist[1])
	LogHelper.Log('SwitchLaserAndLoopbackChannel', LogEventSeverity.Alert, 'switch SGR X8 module 1 to channel {0}.'.format( swlist[1]))
	sleep(1)
	SGRX8Switch.SetClosePoints(2,swlist[2])
	LogHelper.Log('SwitchLaserAndLoopbackChannel', LogEventSeverity.Alert, 'switch SGR X8 module 2 to channel {0}.'.format( swlist[2]))
	LogHelper.Log('SwitchLaserAndLoopbackChannel', LogEventSeverity.Alert, comment + swlist[3])
	sleep(1)

def MCF_RunAllScenario(SequenceObj, cvswriter=None):
	for test in testcases:
		SwitchLaserAndLoopbackChannel(test)
		(polarizations, power) = FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1)
		tap_power = Powermeter.ReadPowers('2:1')[1][0]
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'power {0:.3f} 20% tap power {1:.3f}.'.format(power, tap_power))

