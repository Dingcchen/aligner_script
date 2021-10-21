# Include all necessary assemblies from the C# side
# DO NOT REMOVE THESE REFERECES
import clr
import re
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
from AlignerUtil import *
from time import sleep
from step_manager import *

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

	SequenceObj.TestResults.ClearAllTestResult()

	sleep(.001*2000)
	if Stop:
		return 0

	pivot = TestMetrics.GetTestMetricItem(SequenceObj.SequenceName, 'InitialPivotPoint')
	alignment_results['Pivot'] = pivot

	sleep(.001*2000)
	if Stop:
		return 0

	alignment_results['Step2Result'] = 999
	LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Alert, 'Step1 done')

	# Must always return an integer. 0 = failure, everythingthing else = success
	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results
#-------------------------------------------------------------------------------
# Load loopback type alignment
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def LoadLoopbackDie(SequenceObj, alignment_parameters, alignment_results):

	loadposition = alignment_parameters['LoadPresetPosition'] #'BoardLoad'
	fauvac = alignment_parameters['FAUVaccumPortName']
	dievac = alignment_parameters['TargetVaccumPortName']

	# reset the positions
	# HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
	Hexapod.GetHardwareStateTree().ActivateState(loadposition)
	Nanocube.GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

	# Wait for load complete and get serial number
	# possibly using a barcode scanner later
	ret = UserFormInputDialog.ShowDialog('Load GF die', 'Please load die (wave guides to the left) and enter serial number:', True)
	if ret == True:
		alignment_results['Die_SN'] = UserFormInputDialog.ReturnValue
		VacuumController(dievac, True)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Load FAU/MPO', 'Please load FAU/MPO and enter serial number:', True)
	if ret == True:
		alignment_results['MPO_SN'] = UserFormInputDialog.ReturnValue
		VacuumController(fauvac, True)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Enter assembly ID', 'Please enter assembly serial number:', True)
	if ret == True:
		alignment_results['Assembly_SN'] = UserFormInputDialog.ReturnValue
	else:
		return 0

	# epoxy related information
	# persist some of the values for next run
	if 'EpoxyTubeNumber' in SequenceObj.ProcessPersistentData:
		UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyTubeNumber']
	else:
		UserFormInputDialog.ReturnValue = ''

	ret = UserFormInputDialog.ShowDialog('Epoxy tube number', 'Please enter epoxy tube number:')
	if ret == False:
		return 0
	# save back to persistent data
	SequenceObj.ProcessPersistentData['EpoxyTubeNumber'] = UserFormInputDialog.ReturnValue
	alignment_results['Epoxy_Tube_Number'] = UserFormInputDialog.ReturnValue

	if 'EpoxyExpirationDate' in SequenceObj.ProcessPersistentData:
		UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyExpirationDate']
	else:
		UserFormInputDialog.ReturnValue = ''

	ret = UserFormInputDialog.ShowDialog('Epoxy expiration date', 'Please enter epoxy expiration date (MM/DD/YYYY):')
	if ret == False:
		return 0
	# save back to persistent data
	SequenceObj.ProcessPersistentData['EpoxyExpirationDate'] = UserFormInputDialog.ReturnValue
	alignment_results['Epoxy_Expiration_Date'] = UserFormInputDialog.ReturnValue

	# enter chan 1 initial powers
	if 'Chan1InputPower' in SequenceObj.ProcessPersistentData:
		UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['ChanTopInputPower']
	else:
		UserFormInputDialog.ReturnValue = ''

	ret = UserFormInputDialog.ShowDialog('Top chan optical launch power', 'Please enter top channel launch power (dBm):', True)
	if ret == True:
		try:
			p = float(UserFormInputDialog.ReturnValue)
			SequenceObj.ProcessPersistentData['Chan1InputPower'] = UserFormInputDialog.ReturnValue
			alignment_results['Optical_Input_Power_Top_Outer_Chan'] = p
		except:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Invalid entry. Please enter a valid number.')
			return 0
	else:
		return 0

	# enter chan 8 initial powers
	if 'Chan8InputPower' in SequenceObj.ProcessPersistentData:
		UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['Chan8InputPower']
	else:
		UserFormInputDialog.ReturnValue = ''

	ret = UserFormInputDialog.ShowDialog('Bottom chan optical launch power', 'Please enter bottom channel launch power (dBm):', True)
	if ret == True:
		try:
			p = float(UserFormInputDialog.ReturnValue)
			SequenceObj.ProcessPersistentData['Chan8InputPower'] = UserFormInputDialog.ReturnValue
			alignment_results['Optical_Input_Power_Bottom_Outer_Chan'] = p
		except:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Invalid entry. Please enter a valid number.')
			return 0
	else:
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# Load PD
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def LoadPDDie(SequenceObj, alignment_parameters, alignment_results):

	# loadposition = alignment_parameters['LoadPresetPosition'] #'BoardLoad'
	loadposition = alignment_parameters['LoadPresetPosition'] #'BoardLoad'
	fauvac = alignment_parameters['FAUVaccumPortName']
	dievac = alignment_parameters['TargetVaccumPortName']
	# reset the positions
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)
	# HardwareFactory.Instance.GetHardwareByName('UVWandStages').GetHardwareStateTree().ActivateState(loadposition)
	Hexapod.GetHardwareStateTree().ActivateState(loadposition)
	Nanocube.GetHardwareStateTree().ActivateState(loadposition)

	# Wait for load complete and get serial number
	# possibly using a barcode scanner later
	Die_SN = alignment_parameters['Die_SN']
	if LogHelper.AskContinue('Please load die (wave guides to the left) and verify serial number:\n' + str(Die_SN) + '\nClick Yes when done, No to update value.') == False:
		Die_SN = GetAndCheckUserInput('Load GF die', 'Please load die (wave guides to the left) and enter serial number:')
	if not Die_SN == None:
		if not Die_SN == alignment_parameters['Die_SN']:
			alignment_parameters['Die_SN'] = Die_SN
			if not	update_alignment_parameter(SequenceObj, 'Die_SN', Die_SN):
				LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Warning, 'Failed to update Die_SN in aligment_parameters!')
		alignment_results['Die_SN'] = Die_SN
		VacuumController(dievac, True)
	else:
		return 0

	FAU_SN = alignment_parameters['FAU_SN']
	if LogHelper.AskContinue('Please load FAU and verify serial number:\n' + str(FAU_SN) + '\nClick Yes when done, No to update value.') == False:
		FAU_SN = GetAndCheckUserInput('Load FAU', 'Please load FAU and enter serial number:')
	if not FAU_SN == None:
		if not FAU_SN == alignment_parameters['FAU_SN']:
			alignment_parameters['FAU_SN'] = FAU_SN
			if not update_alignment_parameter(SequenceObj, 'FAU_SN', FAU_SN):
				LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Warning, 'Failed to update FAU_SN in aligment_parameters!')
		alignment_results['FAU_SN'] = FAU_SN
		VacuumController(fauvac, True)
	else:
		return 0

	Assembly_SN = alignment_parameters['Assembly_SN'] 
	if LogHelper.AskContinue('Correct assembly ID?\n' + str(Assembly_SN) + '\nClick Yes when done, No to update value.') == False:
		Assembly_SN = GetAndCheckUserInput('Enter assembly ID', 'Please enter assembly serial number:')
	if Assembly_SN != None:
		alignment_results['Assembly_SN'] = Assembly_SN
	else:
		return 0

	# epoxy related information
	# persist some of the values for next run

	# if 'EpoxyTubeNumber' in SequenceObj.ProcessPersistentData:
		# UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyTubeNumber']
	# else:
		# UserFormInputDialog.ReturnValue = ''

	EpoxyTubeNumber = alignment_parameters['EpoxyTubeNumber']
	if LogHelper.AskContinue('Please verify epoxy tube number:\n' + str(EpoxyTubeNumber) + '\nClick Yes to accept, No to update value.') == False:
		EpoxyTubeNumber = UserFormInputDialog.ShowDialog('Epoxy tube number', 'Please enter epoxy tube number:')
	if not EpoxyTubeNumber == False:
		if not EpoxyTubeNumber == alignment_parameters['EpoxyTubeNumber']:
			alignment_parameters['EpoxyTubeNumber'] = EpoxyTubeNumber
			if not update_alignment_parameter(SequenceObj, 'EpoxyTubeNumber', EpoxyTubeNumber):
				LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Warning, 'Failed to update EpoxyTubeNumber in aligment_parameters!')
		alignment_results['Epoxy_Tube_Number'] = UserFormInputDialog.ReturnValue
	else:
		return 0
	# save back to persistent data
	# SequenceObj.ProcessPersistentData['EpoxyTubeNumber'] = UserFormInputDialog.ReturnValue
	# alignment_results['Epoxy_Tube_Number'] = UserFormInputDialog.ReturnValue

	# if 'EpoxyExpirationDate' in SequenceObj.ProcessPersistentData:
		# UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyExpirationDate']
	# else:
		# UserFormInputDialog.ReturnValue = ''

	EpoxyExpirationDate = alignment_parameters['EpoxyExpirationDate']
	if LogHelper.AskContinue('Please verify epoxy expiration date:\n' + str(EpoxyExpirationDate) + '\nClick Yes to accept, No to update value.') == False:
		EpoxyExpirationDate = UserFormInputDialog.ShowDialog('Epoxy expiration date', 'Please enter epoxy expiration date (MM/DD/YYYY):')
	if not EpoxyExpirationDate == False:
		if not EpoxyExpirationDate == alignment_parameters['EpoxyExpirationDate']:
			alignment_parameters['EpoxyExpirationDate'] = EpoxyExpirationDate
			if not update_alignment_parameter(SequenceObj, 'EpoxyExpirationDate', EpoxyTubeNumber):
				LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Warning, 'Failed to update EpoxyExpirationDate in aligment_parameters!')
		alignment_results['Epoxy_Expiration_Date'] = UserFormInputDialog.ReturnValue
	else:
		return 0
	# save back to persistent data
	# SequenceObj.ProcessPersistentData['EpoxyExpirationDate'] = UserFormInputDialog.ReturnValue

	if SequenceObj.Halt:
		return 0
	else:
		alignment_results['data_path'] = IO.Path.Combine(SequenceObj.TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
		Utility.CreateDirectory(alignment_results['data_path'])
	return alignment_results

#-------------------------------------------------------------------------------
# WetPitchAlign
# Scan pitch (V) to maximize photodiode current
#-------------------------------------------------------------------------------
def WetPitchAlign(SequenceObj, alignment_parameters, alignment_results):

	use_polarization_controller = alignment_parameters['use_polarization_controller']
	# init_V = alignment_results['apply_epoxy_hexapod_final_V']
	init_V = 0.0
	use_hexapod_area_scan = False

	width = alignment_parameters['FirstLight_WG2WG_dist_mm']

	Nanocube.GetHardwareStateTree().ActivateState('Center')
	sleep(.001*500)
	current_scan_channel = 1 
	UseOpticalSwitch = alignment_parameters['UseOpticalSwitch']
	threshold = alignment_parameters['ScanMinPowerThreshold']

	(top_meter_channel, bottom_meter_channel) = GetMeterChannel(UseOpticalSwitch)

	meter_nanocube.ReadPowerWithStatistic(top_meter_channel, 100)
	if meter_nanocube.max < threshold: #check max signal found
		if use_hexapod_area_scan:
			# HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .006, plot_output = False, UseOpticalSwitch = False)
			if not HexapodSpiralScan(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
				if not HexapodSpiralScan(SequenceObj, current_scan_channel,scan_dia_mm=.090, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwitch = UseOpticalSwitch):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod spiral scan failed on channel 1!')
					return False
		else:
			if not NanocubeSpiralScan(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
				if not NanocubeSpiralScan(SequenceObj, current_scan_channel,scan_dia_um=90, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1!')
					return False

	if use_polarization_controller:
		(top_ch_polarization_position, optimized_power) = FastOptimizePolarizationMPC201(SequenceObj, feedback_device = 'NanocubeAnalogInput', feedback_channel = SetScanChannel(None, current_scan_channel, UseOpticalSwitch), coarse_scan = False)

	# Hexapod.PivotPoint['X'] = zeropitch + offset
	# enable the new pivot point
	# Hexapod.ApplyKSDCoordinateSystem('PIVOT')

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimizing pitch (V) angle...')
	# start sweep

	next_V = init_V + alignment_parameters['PitchOptimizationRelativeAngleStart']
	max_V = init_V + alignment_parameters['PitchOptimizationRelativeAngleEnd']
	scan_angles = list()
	while next_V <= max_V:
		scan_angles.append(next_V)
		next_V = next_V + alignment_parameters['PitchOptimizationStepSize']

		if len(scan_angles) > 100: #chech if someone made a bonehead mistake that resulted in way too many scan points and abort if necessary
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Number of pitch angle scan points exceeds 100, reduce number of scan points.')
			return 0

	peak_V_so_far = init_V
	peak_power_so_far = 0
	n_measurements = 10 # average this many samples when checking for peak IFF found

	for current_V in scan_angles:
		current_scan_channel = 1
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
		Hexapod.MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
		sleep(.001*500)

		# # Move hexapod to middle so that climb doesnt cause walk-off from center as the routine continues to run
		Nanocube.GetHardwareStateTree().ActivateState('Center')
		sleep(.001*500)

		meter_nanocube.ReadPowerWithStatistic(top_meter_channel, 100)
		if meter_nanocube.max < threshold: #check max signal found
			if use_hexapod_area_scan:
				# HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .006, plot_output = False, UseOpticalSwitch = False)
				if not HexapodSpiralScan(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
					if not HexapodSpiralScan(SequenceObj, current_scan_channel,scan_dia_mm=.090, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
						LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod spiral scan failed on channel 1!')
						return False
			else:
				if not NanocubeSpiralScan(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
					if not NanocubeSpiralScan(SequenceObj, current_scan_channel,scan_dia_um=90, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
						LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1!')
						return False

		if not NanocubeGradientClimb(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch) or SequenceObj.Halt:
			return False

		top_channel_power = meter_nanocube.ReadPowerWithStatistic(top_meter_channel, n_measurements)

		# display peak aligned position
		topchanpos = Nanocube.GetAxesPositions()
		hexapod_current_position = Hexapod.GetAxesPositions()
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Channel 1 nanocube peak: {3:.3f}V (STD {4:.3f}) @ [{0:.2f}, {1:.2f}, {2:.2f}]um'.format(topchanpos[0],topchanpos[1],topchanpos[2],top_channel_power[0],top_channel_power[1]))

		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(top_sum_IFF/n_measurements))
		if top_channel_power[0] > peak_power_so_far:
			peak_power_so_far = top_channel_power[0]
			peak_V_so_far = current_V
			#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')

		if SequenceObj.Halt:
			return 0


	Nanocube.GetHardwareStateTree().ActivateState('Center')
	sleep(.001*500)
	Hexapod.MoveAxisAbsolute('V', peak_V_so_far, Motion.AxisMotionSpeeds.Normal, True)
	sleep(.001*2000)
	# SetScanChannel(climb, 1, UseOpticalSwitch)
	# SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	meter_nanocube.ReadPowerWithStatistic(top_meter_channel, 100)
	if meter_nanocube.max < threshold: #check max signal found
		if use_hexapod_area_scan:
			# HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .006, plot_output = False, UseOpticalSwitch = False)
			if not HexapodSpiralScan(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
				if not HexapodSpiralScan(SequenceObj, current_scan_channel,scan_dia_mm=.090, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod spiral scan failed on channel 1!')
					return False
		else:
			if not NanocubeSpiralScan(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
				if not NanocubeSpiralScan(SequenceObj, current_scan_channel,scan_dia_um=90, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1!')
					return False
	# hexapod_scan.Channel = 1
	# climb.Channel = 1

	# hexapod_scan.ExecuteNoneModal()
	# check scan status
	# if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
	#	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
	#	return 0
	# sleep(.001*500)

	if not NanocubeGradientClimb(SequenceObj, current_scan_channel, threshold = threshold, UseOpticalSwitch = UseOpticalSwitch) or SequenceObj.Halt:
		return False
		
	middle = Nanocube.GetAxesPositions()
	Nanocube.MoveAxisAbsolute('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	Nanocube.MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)
	Hexapod.MoveAxisRelative('Y', -(50-middle[1])/1000, Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisRelative('Z', -(50-middle[2])/1000, Motion.AxisMotionSpeeds.Normal, True)
	"""
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	Nanocube.MoveAxisAbsolute('Y', 50, Motion.AxisMotionSpeeds.Fast, True)
	Nanocube.MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Fast, True)

	Hexapod.MoveAxisRelative('Y', -(50-ymiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisRelative('Z', -(50-zmiddle)/1000, Motion.AxisMotionSpeeds.Normal, True)
	"""
	# climb.ExecuteNoneModal()
	# # check climb status
	# if climb.IsSuccess == False or SequenceObj.Halt:
	#	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed at pitch scan final!')
	#	return 0
	# sleep(.001*500)
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

	roll_align_result = OptimizeRollAngle(SequenceObj, alignment_parameters['FirstLight_WG2WG_dist_mm'], use_polarization_controller, alignment_parameters["ScanMinPowerThreshold"], max_z_difference_um = 0.2, UseOpticalSwitch = UseOpticalSwitch, fau_flip=fau_flip)

	# Move back to original coordinate.
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	if roll_align_result is False :
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Roll optimize failed!')
		return 0

	alignment_results['Wet_Align_Results'] = roll_align_result

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# Finalize
# Save data to the file
#-------------------------------------------------------------------------------
def Finalize(SequenceObj, alignment_parameters, alignment_results):

	# # get process values
	# drytop = alignment_results['Dry_Align_Balanced_Power_Top_Chan']
	# drybottom = alignment_results['Dry_Align_Balanced_Power_Bottom_Chan']
	# wettop = alignment_results['Wet_Align_Balanced_Power_Top_Chan']
	# wetbottom = alignment_results['Wet_Align_Balanced_Power_Bottom_Chan']
	# uvtop = alignment_results['Post_UV_Cure_Power_Top_Outer_Chan']
	# uvbottom = alignment_results['Post_UV_Cure_Power_Bottom_Outer_Chan']
	# #releasetop = alignment_results['Post_Release_Power_Top_Outer_Chan']
	# #releasebottom = alignment_results['Post_Release_Power_Bottom_Outer_Chan']

	# # save process values
	# alignment_results['Wet_Align_Power_Top_Outer_Chan_Loss'] = round(drytop - wettop, 6)
	# alignment_results['Wet_Align_Power_Bottom_Outer_Chan_Loss'] = round(drybottom - wetbottom, 6)

	# alignment_results['Post_UV_Cure_Power_Top_Outer_Chan_Loss'] = round(wettop - uvtop, 6)
	# alignment_results['Post_UV_Cure_Power_Bottom_Outer_Chan_Loss'] = round(wetbottom - uvbottom, 6)

	# #alignment_results['Post_Release_Power_Top_Outer_Chan_Loss'] = round(uvtop - releasetop, 6)
	# #alignment_results['Post_Release_Power_Bottom_Outer_Chan_Loss'] = round(uvbottom - releasebottom, 6)

	#check user comment
	# if SequenceObj.TestResults.IsTestResultExists('Comment') == False:
		# if Station.Instance.UserComment:
			# alignment_results['Comment'] = Station.Instance.UserComment
	# else:
		# if Station.Instance.UserComment:
			# alignment_results['Comment'] = alignment_results['Comment' + ' ' + Station.Instance.UserComment]
		# else:
			# alignment_results['Comment'] = alignment_results['Comment']
	alignment_results['Comment'] = Station.Instance.UserComment
	###alignment_results['data_path'] = IO.Path.Combine(SequenceObj.TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
    
	#save the data file
	#TestResults.SaveTestResultsToStorage(alignment_results['Assembly_SN'])
	if save_pretty_json(alignment_results, IO.Path.Combine(alignment_results['data_path'], alignment_results['Assembly_SN'] + '_results.json')):
		return alignment_results
	else:
		return 0

#-------------------------------------------------------------------------------
# Reposition
# Allow operator to go back to previous saved position in alignment_results
#-------------------------------------------------------------------------------
def Reposition(SequenceObj, alignment_parameters, alignment_results):
	positions = GetAndCheckUserInput('Set position', 'Please ienter the name of previous saved position:')
	if positions != None:
		set_positions(SequenceObj, alignment_results[positions])
		LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Warning, 'Set positions ' + positions)
	return 0






