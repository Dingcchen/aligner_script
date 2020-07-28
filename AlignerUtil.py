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
# OptimizePolarizationScan
# Helper function to optimize polarization
# Very slow, use FastOptimizePolarizationScan instead
#-------------------------------------------------------------------------------
def OptimizePolarizationScan(SequenceObj, controller, feedback_device, feedback_channel = 1, mode = 'max', step_size = .1, convergence_band_percent = 10):
	controller_channels = ['1','2','3','4']

	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in controller_channels:
		if not controller.SetPolarization(1, channel):
			return False
	
	num_steps = int(2*round(1/step_size,0)) + 1

	converged = False
	if mode == 'max':
		last_optimum = -99
	else:
		last_optimum = 99

	while not converged:
		for channel in controller_channels:
			#loop through the polarization states on this channel and record the feedback signal
			fb_signal = []
			for i in range(num_steps):
				if not controller.SetPolarization(i*step_size, channel):
					return False
				sleep(0.15)
				fb_signal.append(feedback_device.ReadPower(feedback_channel))
				if SequenceObj.Halt:
					return False
			#set the channel to the max (or min) polarization value found
			if mode == 'max':
				if not controller.SetPolarization(step_size*fb_signal.index(max(fb_signal)), channel):
						return False
			else:
				if not controller.SetPolarization(step_size*fb_signal.index(min(fb_signal)), channel):
						return False
		sleep(0.2)
		current_optimum = feedback_device.ReadPower(feedback_channel)

		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.02f} dBm'.format(current_optimum)) # add other devices!!!
		if abs((current_optimum - last_optimum)/current_optimum) < convergence_band_percent/100.0:
			converged = True
		last_optimum = current_optimum

	return True
	
#-------------------------------------------------------------------------------
# FastOptimizePolarizationScan
# Helper function to optimize polarization
#-------------------------------------------------------------------------------
def FastOptimizePolarizationScan(SequenceObj, controller, feedback_device, feedback_channel = 1, mode = 'max', step_size = .1, convergence_band_percent = 10):
	controller_channels = ['1','2','3','4']
	peak_position = [2,2,2,2]

	feedback_device.AutoUpdates(False)

	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in range(len(controller_channels)):
		# if not controller.SetPolarization(1, channel):
			# return False
		peak_position[channel] = controller.ReadPolarization(controller_channels[channel])[0]
	
	num_steps = int(2*round(1/step_size,0)) + 1

	converged = False
	if mode == 'max':
		last_optimum = -99
	else:
		last_optimum = 99

	while not converged:
		for channel in range(len(controller_channels)):
			#loop through the polarization states on this channel and record the feedback signal
			fb_signal = []
			positions = []
			i=0
			search_positive = True
			search_negative = True
			next_position = peak_position[channel]
			while True:
				if not controller.SetPolarization(next_position, controller_channels[channel]):
					feedback_device.AutoUpdates(True)
					return False
				positions.append(next_position)
				#sleep(0.15)
				
				fb_signal.append(feedback_device.ReadPower(feedback_channel))
				if SequenceObj.Halt:
					feedback_device.AutoUpdates(True)
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
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Too many tries on channel ' + controller_channels[channel] + "!") # add other devices!!!
					return 0
					
				i += 1
			#set the channel to the max (or min) polarization value found
			if mode == 'max':
				peak_position[channel] = positions[fb_signal.index(max(fb_signal))]
				if not controller.SetPolarization(peak_position[channel], controller_channels[channel]):
						feedback_device.AutoUpdates(True)
						return False
			else:
				peak_position[channel] = positions[fb_signal.index(min(fb_signal))]
				if not controller.SetPolarization(peak_position[channel], controller_channels[channel]):
						feedback_device.AutoUpdates(True)
						return False
		#sleep(0.2)
		current_optimum = feedback_device.ReadPower(feedback_channel)

		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimum polarization found so far: {0:.02f} dBm'.format(current_optimum)) # add other devices!!!
		if abs((current_optimum - last_optimum)/current_optimum) < convergence_band_percent/100.0:
			converged = True
		last_optimum = current_optimum
		step_size = step_size/2
		if step_size < 0.05:
			step_size = 0.05
	
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

