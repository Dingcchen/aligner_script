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

def OptimizePolarizationMPC201(control_device_name = 'PolarizationControl',feedback_device = 'PowerMeter', feedback_channel = 1, mode = 'max', step_size = 1/32), convergence_band_percent = 3:
	polarization_controller = HardwareFactory.Instance.GetHardwareByName(control_device_name)
	polarization_controller_channels = ['1','2','3','4']

	#set all polarization controller channels to a predefined value (because reasons???)
	for channel in polarization_controller_channels:
		if not polarization_controller.SetPolarization(0, channel):
			return False
	
	num_steps = round(1/step_size,0) + 1

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
				if feedback_device=='PowerMeter':
					if (feedback_channel == 1):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1'))
					elif (feedback_channel == 2):
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1'))
					else:
						fb_signal.append(HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel))
				elif feedback_device=='HexapodAnalogInput':
					fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel))
				elif feedback_device=='NanocubeAnalogInput':
					fb_signal.append(HardwareFactory.Instance.GetHardwareByName('Nanocube').ReadAnalogInput(feedback_channel))
				else:
					return False
			#set the channel to the max (or min) polarization value found
			if mode == 'max':
				if not polarization_controller.SetPolarization(step_size*fb_signal.index(max(fb_signal)), channel):
						return False
			else:
				if not polarization_controller.SetPolarization(step_size*fb_signal.index(min(fb_signal)), channel):
						return False

		if feedback_device=='PowerMeter':
			if (feedback_channel == 1):
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('1:1'))
			elif (feedback_channel == 2):
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers('2:1'))
			else:
				current_optimum = (HardwareFactory.Instance.GetHardwareByName(feedback_device).ReadPowers(feedback_channel))
		elif feedback_device=='HexapodAnalogInput':
			current_optimum = HardwareFactory.Instance.GetHardwareByName('Hexapod').ReadAnalogInput(feedback_channel)
		elif feedback_device=='NanocubeAnalogInput':
			current_optimum = HardwareFactory.Instance.GetHardwareByName('Nanocube').ReadAnalogInput(feedback_channel)
		else:
			return False

		if math.abs((current_optimum - last_optimum)/current_optimum) < convergence_band_percent/100:
			converged = True

	return True