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
import random
from HAL.SourceController import ScrambleMethodType
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
# Initialize
# Clears up test data and other prep work before process starts
#-------------------------------------------------------------------------------
def Initialize(SequenceObj, alignment_parameters, alignment_results):
	# for quick test.
	# IOController.SetOutputValue('OpticalSwitch', False)
	# AreaScan('NanocubeSpiralCVScan', SequenceObj, TestMetrics, TestResults)
	# return alignment_results
	filename = "..\\Data\\sw2x2_switch8_loopback_charisterization2.csv"

	csvfile = open(filename, 'wb')
	csvfile.write("Loopback laser input to SGR8X module 1 to SGR8X module 2 output to power meter.\r\n")
	csvwriter = csv.writer(csvfile)
	IOController.SetOutputValue('OpticalSwitch2X2', False)
	LoopbackCycleChn1to4(SequenceObj, csvwriter, loop=5)
	IOController.SetOutputValue('OpticalSwitch2X2', True)
	LoopbackCycleChn1to4(SequenceObj, csvwriter, loop=5)
	
	return alignment_results

#-------------------------------------------------------------------------------
# Finalize
# Save data to the file
#-------------------------------------------------------------------------------
def Finalize(SequenceObj, alignment_parameters, alignment_results):

	#save the data file
	#TestResults.SaveTestResultsToStorage(alignment_results['Assembly_SN'])
	if save_pretty_json(alignment_results, IO.Path.Combine(alignment_results['data_path'], alignment_results['Assembly_SN'] + '_results.json')):
		return alignment_results
	else:
		return 0

