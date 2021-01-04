'''
Created on Dec 10, 2020

@author: dingchen
'''
import clr
import re
clr.AddReference('System.Core')
from System import IO
from System import Func
from System import DateTime
from System import Array
from System import String
from System import ValueTuple
import math as math
from System.Collections.Generic import List
clr.AddReferenceToFile('HAL.dll')
from HAL import Motion
from HAL import HardwareFactory
from HAL import HardwareInitializeState
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoAligner.exe')
from CiscoAligner import Station
from CiscoAligner import Alignments
from AlignerUtil import *
from time import sleep
from step_manager import *
from Alignment import *

def FauTouchAndBackOff(SequenceObj, contactThreshold, backoff, bondgap):
	# Re-establish the contact point again
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	hexapod_initial_x = Hexapod.GetAxesPositions()[0]
	# monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < contactThreshold:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		sleep(0.01)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	# Hexapod.CreateKSFCoordinateSystem('WORK', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )
	# sleep(0.5)
	# found contact point, back off set amount
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)

	hexapod_distance_to_touch = Hexapod.GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# put the required bondgap
	Hexapod.MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)
	
#-------------------------------------------------------------------------------
# RollBalanceAlign
# Roll balanced align, but wet
# Touches the die with the force sensor and moves to bond gap
# Uses much tighter spec for roll align
#-------------------------------------------------------------------------------
def RollBalanceAlign4Channels(SequenceObj, alignment_parameters, alignment_results):

	fau_flip = alignment_parameters["FAUFlipped"]
	WG2WG_dist_mm = alignment_parameters['FirstLight_WG2WG_dist_mm']
	powerThresdhold = alignment_parameters["ScanMinPowerThreshold"]
	max_z_difference_um = 0.2  # um
	
	opticalSwitchChn1To4 = OpticalSwitch(SGRX8Switch, 2, 3, "Loopback chn 1 to 4")
	opticalSwitchChn5To8 = OpticalSwitch(SGRX8Switch, 4, 5, "Loopback chn 5 to 8")

	laserAtChn1 = LaserSwitch('OpticalSwitch2X2', 1)
	laserAtChn2 = LaserSwitch('OpticalSwitch2X2', 2)
	meter1 = Meter_nanocube(1)
	meter2 = Meter_nanocube(2)
	top1Alignment = SearchMaxPosition('channel 5', laserAtChn1, meter2, opticalSwitchChn5To8, powerThresdhold)
	top2Alignment = SearchMaxPosition('channel 8', laserAtChn2, meter2, opticalSwitchChn5To8, powerThresdhold)
	bottom1Alignment = SearchMaxPosition('channel 1', laserAtChn1, meter1, opticalSwitchChn1To4, powerThresdhold)
	bottom2Alignment = SearchMaxPosition('channel 4', laserAtChn2, meter1, opticalSwitchChn1To4, powerThresdhold)

	scan_channels = (top1Alignment, top2Alignment, bottom1Alignment, bottom2Alignment)

	testRollAlign = FourChannelRollAlignment(scan_channels, WG2WG_dist_mm, max_z_difference_um)

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

	testRollAlign = RollBalanceAlign4Channels(SequenceObj, alignment_parameters, alignment_results)

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
# Roll balanced align, but wet
# Touches the die with the force sensor and moves to bond gap
# Uses much tighter spec for roll align
#-------------------------------------------------------------------------------
def WetBalanceAlign(SequenceObj, alignment_parameters, alignment_results):

	#Ask operator to check both channels are connected
	if LogHelper.AskContinue('Connect both channels from optical switch! Click Yes when done, No to abort.') == False:
		return 0

	backoff = alignment_parameters['BackOffFromContactDetection']
	bondgap = alignment_parameters['EpoxyBondGap']
	contactThreshold = alignment_parameters['ForceSensorContactThreshold']
	FauTouchAndBackOff(SequenceObj, contactThreshold, backoff, bondgap)

	testRollAlign = RollBalanceAlign4Channels(SequenceObj, alignment_parameters, alignment_results)

	if(testRollAlign is False):
		return 0
	else:
		alignment_results['Wet_Align_Results'] = testRollAlign.Results

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results
	
def TestResultsStep(SequenceObj, alignment_parameters, alignment_results):

	laserAtChn1 = LaserSwitch('OpticalSwitch2X2', 1)
	laserAtChn2 = LaserSwitch('OpticalSwitch2X2', 2)
	meter1 = Meter_nanocube(1)
	meter2 = Meter_nanocube(2)
	power_meter = Meter_powermeter(1)

	loopbackChn1To4 = OpticalSwitch(SGRX8Switch, 2, 3, "Loopback chn 1 to 4")
	loopbackChn2To3 = OpticalSwitch(SGRX8Switch, 3, 2, "Loopback chn 2 to 3")
	loopbackChn5To8 = OpticalSwitch(SGRX8Switch, 4, 5, "Loopback chn 5 to 8")
	loopbackChn6To7 = OpticalSwitch(SGRX8Switch, 5, 4, "Loopback chn 6 to 7")

	crossChn1To3 = OpticalSwitch(SGRX8Switch, 2, 2, "cross chn 1 to 3")
	crossChn2To4 = OpticalSwitch(SGRX8Switch, 3, 3, "cross chn 2 to 4")
	crossChn5To7 = OpticalSwitch(SGRX8Switch, 4, 4, "cross chn 5 to 7")
	crossChn6To8 = OpticalSwitch(SGRX8Switch, 5, 5, "cross chn 6 to 8")

	testResultloop1to4 = TestResult("Loopback 1 to 4", laserAtChn1, power_meter, loopbackChn1To4)
	testResultloop4to1 = TestResult("Loopback 4 to 1", laserAtChn2, power_meter, loopbackChn1To4)
	testResultloop2to3 = TestResult("Loopback 2 to 3", laserAtChn1, power_meter, loopbackChn2To3)
	testResultloop3to2 = TestResult("Loopback 3 to 2", laserAtChn2, power_meter, loopbackChn2To3)
	testResultloop5to8 = TestResult("Loopback 5 to 8", laserAtChn1, power_meter, loopbackChn5To8)
	testResultloop8to5 = TestResult("Loopback 8 to 5", laserAtChn2, power_meter, loopbackChn5To8)
	testResultloop6to7 = TestResult("Loopback 6 to 7", laserAtChn1, power_meter, loopbackChn6To7)
	testResultloop7to6 = TestResult("Loopback 7 to 6", laserAtChn2, power_meter, loopbackChn6To7)

	testResultCross1to3 = TestResult("Cross 1 to 3", laserAtChn1, power_meter, crossChn1To3)
	testResultCross3to1 = TestResult("Cross 3 to 1", laserAtChn2, power_meter, crossChn1To3)
	testResultCross2to4 = TestResult("Cross 2 to 4", laserAtChn1, power_meter, crossChn2To4)
	testResultCross4to2 = TestResult("Cross 4 to 2", laserAtChn2, power_meter, crossChn2To4)
	testResultCross5to7 = TestResult("Cross 5 to 7", laserAtChn1, power_meter, crossChn5To7)
	testResultCross7to5 = TestResult("Cross 7 to 5", laserAtChn2, power_meter, crossChn5To7)
	testResultCross6to8 = TestResult("Cross 6 to 8", laserAtChn1, power_meter, crossChn6To8)
	testResultCross8to6 = TestResult("Cross 8 to 6", laserAtChn2, power_meter, crossChn6To8)

	testcases =  (
            testResultloop1to4,
            testResultloop4to1,
            testResultloop2to3,
            testResultloop3to2,
            testResultloop5to8,
            testResultloop8to5,
            testResultloop6to7,
            testResultloop7to6
		)
	"""
            testResultCross1to3,
            testResultCross3to1,
            testResultCross2to4,
            testResultCross4to2,
            testResultCross5to7,
            testResultCross7to5,
            testResultCross6to8,
            testResultCross8to6
	"""
	testResults = TestResults(testcases)
	testResults.run(SequenceObj)

	alignment_results['Test Cases Results'] = testResults.Results

	filename = "..\\Data\\Dual_MCF_loopback_test_result.csv"
	csvfile = open(filename, 'wb')
	csvfile.write("Loopback test result.\r\n")
	writeCSV(csvfile, alignment_results)
	csvfile.close()

	return alignment_results


if __name__ == '__main__':
	pass