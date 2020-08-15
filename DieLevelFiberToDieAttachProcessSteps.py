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

UseOpticalSwitch = True

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
	HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
	Hexapod.GetHardwareStateTree().ActivateState(loadposition)
	Nanocube.GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

	#release vacuum
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)

	# Wait for load complete and get serial number
	# possibly using a barcode scanner later
	ret = UserFormInputDialog.ShowDialog('Load GF die', 'Please load die (wave guides to the left) and enter serial number:', True)
	if ret == True:
		alignment_results['Die_SN'] = UserFormInputDialog.ReturnValue
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, True)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Load FAU/MPO', 'Please load FAU/MPO and enter serial number:', True)
	if ret == True:
		alignment_results['MPO_SN'] = UserFormInputDialog.ReturnValue
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
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
	HardwareFactory.Instance.GetHardwareByName('UVWandStages').GetHardwareStateTree().ActivateState(loadposition)
	Hexapod.GetHardwareStateTree().ActivateState(loadposition)
	Nanocube.GetHardwareStateTree().ActivateState(loadposition)

	#release vacuum
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)


	# Wait for load complete and get serial number
	# possibly using a barcode scanner later
	Die_SN = alignment_parameters['Die_SN']
	if LogHelper.AskContinue('Please load die (wave guides to the left) and verify serial number:\n' + Die_SN + '\nClick Yes when done, No to update value.') == False:
		Die_SN = GetAndCheckUserInput('Load GF die', 'Please load die (wave guides to the left) and enter serial number:')
	if not Die_SN == None:
		if not Die_SN == alignment_parameters['Die_SN']:
			alignment_parameters['Die_SN'] = Die_SN
			if not 	update_alignment_parameter(SequenceObj, 'Die_SN', Die_SN):
				LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Warning, 'Failed to update Die_SN in aligment_parameters!')
		alignment_results['Die_SN'] = Die_SN
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, True)
	else:
		return 0

	FAU_SN = alignment_parameters['FAU_SN']
	if LogHelper.AskContinue('Please load FAU and verify serial number:\n' + FAU_SN + '\nClick Yes when done, No to update value.') == False:
		FAU_SN = GetAndCheckUserInput('Load FAU', 'Please load FAU and enter serial number:')
	if not FAU_SN == None:
		if not FAU_SN == alignment_parameters['FAU_SN']:
			alignment_parameters['FAU_SN'] = FAU_SN
			if not update_alignment_parameter(SequenceObj, 'FAU_SN', FAU_SN):
				LogHelper.Log(SequenceObj.StepName, LogEventSeverity.Warning, 'Failed to update FAU_SN in aligment_parameters!')
		alignment_results['FAU_SN'] = FAU_SN
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
	else:
		return 0

	msg = GetAndCheckUserInput('Enter assembly ID', 'Please enter assembly serial number:')
	if msg != None:
		alignment_results['Assembly_SN'] = msg
	else:
		return 0

	# epoxy related information
	# persist some of the values for next run

	# if 'EpoxyTubeNumber' in SequenceObj.ProcessPersistentData:
		# UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyTubeNumber']
	# else:
		# UserFormInputDialog.ReturnValue = ''

	EpoxyTubeNumber = alignment_parameters['EpoxyTubeNumber']
	if LogHelper.AskContinue('Please verify epoxy tube number:\n' + EpoxyTubeNumber + '\nClick Yes to accept, No to update value.') == False:
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
	if LogHelper.AskContinue('Please verify epoxy expiration date:\n' + EpoxyExpirationDate + '\nClick Yes to accept, No to update value.') == False:
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
		dir = IO.Path.Combine(SequenceObj.TestResults.OutputDestinationConfiguration, alignment_results['Assembly_SN'])
		Utility.CreateDirectory(dir)
	return alignment_results

"""
#-------------------------------------------------------------------------------
# BalanceWedAlignment
# Balance alignment of the channels in epoxy with pitch sweep optimization
#-------------------------------------------------------------------------------
def SweepOptimizedBalanceWetAlignment(SequenceObj, alignment_parameters, alignment_results):

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# get the pitch sweep algo
	scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
	pitchsweep = Alignments.AlignmentFactory.Instance.SelectAlignment('PitchSweepOptimization')

	# reload sweep parameters
	scan.Range1 = alignment_parameters['PitchOptimizationHexapodScanRange1']
	scan.Range2 = alignment_parameters['PitchOptimizationHexapodScanRange2']
	scan.Velocity = alignment_parameters['PitchOptimizationHexapodScanVelocity']
	scan.Frequency = alignment_parameters['PitchOptimizationHexapodScanFrequency']
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1

	Axis = alignment_parameters['PitchOptimizationAxis']

	init_V = Hexapod.GetAxesPositions()[4]

	pitchsweep.Axis = Axis
	pitchsweep.MotionStages = Hexapod
	pitchsweep.StartPosition = init_V + alignment_parameters['PitchOptimizationRelativeAngleStart']
	pitchsweep.EndPosition = init_V + alignment_parameters['PitchOptimizationRelativeAngleEnd']
	pitchsweep.StepSize = alignment_parameters['PitchOptimizationStepSize']
	pitchsweep.FeedbackUnit = 'V'
	pitchsweep.ExecuteOnce = scan.ExecuteOnce = SequenceObj.AutoStep

	# create the pitch feedback delegate function
	def EvalPitch(a):
		Hexapod.MoveAxisAbsolute(Axis, a, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		sleep(.001*500)
		scan.ExecuteNoneModal()
		# wait to settle
		sleep(.001*500)
		return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)

	pitchsweep.EvalFunction = Func[float,float](EvalPitch)

	# get the pitch search X pull back distance
	# first perform a pull back, we will need to re-do the contact point again afterwards
	Hexapod.MoveAxisRelative('X', alignment_parameters['PitchOptimizationPullBack'], Motion.AxisMotionSpeeds.Normal, True)

	# readjust the pitch pivot point
	zero = alignment_results['Optical_Z_Zero_Position']
	#zeropitch = alignment_results['Pitch_Pivot_X']
	offset = Hexapod.GetAxisPosition('X') - zero
	# Hexapod.PivotPoint['X'] = zeropitch + offset
	# enable the new pivot point
	# Hexapod.ApplyKSDCoordinateSystem('PIVOT')

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimizing hexapod pitch angle.')
	# start sweep

	if False:
		pitchsweep.ExecuteNoneModal()
		# check result
		if not pitchsweep.IsSuccess or SequenceObj.Halt:
			return 0
	else:
		next_V = init_V + alignment_parameters['PitchOptimizationRelativeAngleStart']
		max_V = init_V + alignment_parameters['PitchOptimizationRelativeAngleEnd']
		scan_angles = list()
		while next_V <= max_V:
			scan_angles.append(next_V)
			next_V = next_V + alignment_parameters['PitchOptimizationStepSize']

			if len(scan_angles) > 100:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Number of pitch angle scan points exceeds 100.')
				return 0

		peak_V_so_far = init_V
		peak_power_so_far = 0
		n_measurements = 5 # average this many samples when checking for peak IFF found

		for current_V in scan_angles:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
			Hexapod.MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
			sleep(.001*500)
			scan.ExecuteNoneModal()
			sleep(.001*500)

			sum_IFF = 0
			for i in range(n_measurements):
				sum_IFF = sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)

			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(sum_IFF/n_measurements))
			if (sum_IFF/n_measurements) > peak_power_so_far:
				peak_power_so_far = sum_IFF/n_measurements
				peak_V_so_far = current_V
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')
			if SequenceObj.Halt:
				return 0

	Hexapod.MoveAxisAbsolute('V', peak_V_so_far, Motion.AxisMotionSpeeds.Normal, True)
	sleep(.001*500)
	scan.ExecuteNoneModal()
	sleep(.001*500)

	# Re-establish the contact point again
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	threshold = alignment_parameters['ForceSensorContactThreshold']
	backoff = alignment_parameters['BackOffFromContactDetection']
	bondgap = alignment_parameters['EpoxyBondGap']
	# monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		sleep(.001*5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	# found contact point, back off set amount
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	Hexapod.MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	scan.Range1 = alignment_parameters['HexapodFineScanRange1']
	scan.Range2 = alignment_parameters['HexapodFineScanRange2']
	scan.Velocity = alignment_parameters['HexapodFineScanVelocity']
	scan.Frequency = alignment_parameters['HexapodFineScanFrequency']

	# set up a loop to zero in on the roll angle
	width = alignment_results['Outer_Channels_Width']
	retries = 0

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Balancing channels...')

	while retries < 5 and not SequenceObj.Halt:

		# start the algorithms
		SetScanChannel(scan, 1, UseOpticalSwitch)
		# scan.Channel = 1
		scan.ExecuteNoneModal()
		# check scan status
		if scan.IsSuccess == False or SequenceObj.Halt:
			return 0

		 # wait to settle
		sleep(.001*500)

		# remember the final position
		topchanpos = Hexapod.GetAxesPositions()

		# repeat scan for the second channel
		SetScanChannel(scan, 2, UseOpticalSwitch)
		# scan.Channel = 2

		# start the algorithms again
		scan.ExecuteNoneModal()
		# check scan status
		if scan.IsSuccess == False or SequenceObj.Halt:
			return 0

		# wait to settle
		sleep(.001*500)

		# get the final position of second channel
		bottomchanpos = Hexapod.GetAxesPositions()

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
		Hexapod.MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		sleep(.001*500)

		retries += 1

	# check stop conditions
	if retries >= 3 or SequenceObj.Halt:
	   return 0

	# balanced position
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	Hexapod.MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

	# record final wet align hexapod position
	hposition = Hexapod.GetAxesPositions()
	alignment_results['Wet_Align_Hexapod_X'] = hposition[0]
	alignment_results['Wet_Align_Hexapod_Y'] = hposition[1]
	alignment_results['Wet_Align_Hexapod_Z'] = hposition[2]
	alignment_results['Wet_Align_Hexapod_U'] = hposition[3]
	alignment_results['Wet_Align_Hexapod_V'] = hposition[4]
	alignment_results['Wet_Align_Hexapod_W'] = hposition[5]

	# get power based on instrument
	toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]

	# save process values
	alignment_results['Wet_Align_Power_Top_Outer_Chan'] = toppower
	alignment_results['Wet_Align_Power_Bottom_Outer_Chan'] = bottompower

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

def BalanceWetAlignNanocube(SequenceObj, alignment_parameters, alignment_results):

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	init_V = alignment_results['apply_epoxy_hexapod_final_V']

	##############################
	##### Hexapod scan setup #####
	##############################
	# get the pitch sweep algo
	hexapod_scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')

	# reload sweep parameters
	hexapod_scan.Range1 = alignment_parameters['PitchOptimizationHexapodScanRange1']
	hexapod_scan.Range2 = alignment_parameters['PitchOptimizationHexapodScanRange2']
	hexapod_scan.Velocity = alignment_parameters['PitchOptimizationHexapodScanVelocity']
	hexapod_scan.Frequency = alignment_parameters['PitchOptimizationHexapodScanFrequency']
	SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1

	###############################
	##### Nanocube scan setup #####
	###############################
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = alignment_parameters['Nanocube_Scan_Axis1']
	climb.Axis2 = alignment_parameters['Nanocube_Scan_Axis2']
	climb.ExecuteOnce = SequenceObj.AutoStep

	# set up a loop to zero in on the roll angle

	#width = alignment_results['Outer_Channels_Width']
	width = alignment_parameters['FirstLight_WG2WG_dist_mm']
	#topchanpos = [ 50.0, 50.0, 50.0 ]
	#bottomchanpos = [ 50.0, 50.0, 50.0 ]
	retries = 0

	###################################
	##### End Nanocube scan setup #####
	###################################


	# get the pitch search X pull back distance
	# first perform a pull back, we will need to re-do the contact point again afterwards
	Hexapod.MoveAxisAbsolute('X', alignment_results['apply_epoxy_hexapod_final_X') + alignment_parameters['PitchOptimizationPullBack'], Motion.AxisMotionSpeeds.Normal, True]
	Hexapod.MoveAxisAbsolute('Y', alignment_results['apply_epoxy_hexapod_final_Y'), Motion.AxisMotionSpeeds.Normal, True]
	Hexapod.MoveAxisAbsolute('Z', alignment_results['apply_epoxy_hexapod_final_Z'), Motion.AxisMotionSpeeds.Normal, True]
	Hexapod.MoveAxisAbsolute('U', alignment_results['apply_epoxy_hexapod_final_U'), Motion.AxisMotionSpeeds.Normal, True]
	Hexapod.MoveAxisAbsolute('V', alignment_results['apply_epoxy_hexapod_final_V'), Motion.AxisMotionSpeeds.Normal, True]
	Hexapod.MoveAxisAbsolute('W', alignment_results['apply_epoxy_hexapod_final_W'), Motion.AxisMotionSpeeds.Normal, True]

	Nanocube.GetHardwareStateTree().ActivateState('Center')
	sleep(.001*500)

	hexapod_scan.ExecuteNoneModal()
	if hexapod_scan.IsSuccess is False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
		return 0
	sleep(.001*500)

	# readjust the pitch pivot point
	zero = alignment_results['Optical_Z_Zero_Position']
	#zeropitch = alignment_results['Pitch_Pivot_X']
	offset = Hexapod.GetAxisPosition('X') - zero
	# Hexapod.PivotPoint['X'] = zeropitch + offset
	# enable the new pivot point
	# Hexapod.ApplyKSDCoordinateSystem('PIVOT')

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimizing hexapod pitch angle.')
	# start sweep
	if False:
		next_V = init_V + alignment_parameters['PitchOptimizationRelativeAngleStart']
		max_V = init_V + alignment_parameters['PitchOptimizationRelativeAngleEnd']
		scan_angles = list()
		while next_V <= max_V:
			scan_angles.append(next_V)
			next_V = next_V + alignment_parameters['PitchOptimizationStepSize']

			if len(scan_angles) > 100:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Number of pitch angle scan points exceeds 100.')
				return 0

		peak_V_so_far = init_V
		peak_power_so_far = 0
		n_measurements = 5 # average this many samples when checking for peak IFF found

		for current_V in scan_angles:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
			Hexapod.MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
			sleep(.001*500)
			scan.ExecuteNoneModal()
			sleep(.001*500)

			sum_IFF = 0
			for i in range(n_measurements):
				sum_IFF = sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)

			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(sum_IFF/n_measurements))
			if (sum_IFF/n_measurements) > peak_power_so_far:
				peak_power_so_far = sum_IFF/n_measurements
				peak_V_so_far = current_V
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')
			if SequenceObj.Halt:
				return 0
	if True:
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
		n_measurements = 5 # average this many samples when checking for peak IFF found

		for current_V in scan_angles:
			#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
			Hexapod.MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
			sleep(.001*500)

			# start the Nanocube algorithms
			SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
			SetScanChannel(climb, 1, UseOpticalSwitch)
			# hexapod_scan.Channel = 1
			# climb.Channel = 1

			# # Move hexapod to middle so that climb doesnt cause walk-off from center as the routine continues to run
			Nanocube.GetHardwareStateTree().ActivateState('Center')
			sleep(.001*500)

			hexapod_scan.ExecuteNoneModal()
			# check scan status
			if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed during pitch scan!')
				return 0
			sleep(.001*500)

			climb.ExecuteNoneModal()
			if climb.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during pitch scan!')
				return 0
			sleep(.001*500)

			top_sum_IFF = 0
			for i in range(n_measurements):
				top_sum_IFF = top_sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)

			SetScanChannel(climb, 2, UseOpticalSwitch)
			# climb.Channel = 2
			climb.ExecuteNoneModal()
			# check climb status
			if climb.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch2 gradient climb scan failed during pitch scan!')
				return 0

			sleep(.001*500)

			bottom_sum_IFF = 0
			for i in range(n_measurements):
				bottom_sum_IFF = bottom_sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)

			# display peak aligned position
			peak_align_position = Nanocube.GetAxesPositions()
			hexapod_current_position = Hexapod.GetAxesPositions()
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Completed scan {0:d}/{1:d} | Pitch angle (deg) |{2:2.4f}| Final nanocube position um |{4:.3f}|{5:.3f}|{6:.3f}| Peak singal ch1 and ch2 V |{7:.3f}|{8:.3f}'.format(scan_angles.index(current_V)+1, len(scan_angles), hexapod_current_position[4], hexapod_current_position[4], peak_align_position[0], peak_align_position[1], peak_align_position[2], top_sum_IFF/n_measurements, bottom_sum_IFF/n_measurements))

			#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(top_sum_IFF/n_measurements))
			if (top_sum_IFF/n_measurements) > peak_power_so_far:
				peak_power_so_far = top_sum_IFF/n_measurements
				peak_V_so_far = current_V
				#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')

			if SequenceObj.Halt:
				return 0


	Nanocube.GetHardwareStateTree().ActivateState('Center')
	sleep(.001*500)
	SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1
	SetScanChannel(climb, 1, UseOpticalSwitch)
	# climb.Channel = 1
	Hexapod.MoveAxisAbsolute('V', peak_V_so_far, Motion.AxisMotionSpeeds.Normal, True)
	sleep(.001*2000)
	hexapod_scan.ExecuteNoneModal()
	# check scan status
	if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
		return 0
	sleep(.001*500)

	climb.ExecuteNoneModal()
	# check climb status
	if climb.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed at pitch scan final!')
		return 0
	sleep(.001*500)

	# Re-establish the contact point again
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	threshold = alignment_parameters['ForceSensorContactThreshold']
	backoff = alignment_parameters['BackOffFromContactDetection']
	bondgap = alignment_parameters['EpoxyBondGap']

	hexapod_initial_x = Hexapod.GetAxesPositions()[0]
	# monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
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

	# set up a loop to zero in on the roll angle
	width = alignment_parameters['FirstLight_WG2WG_dist_mm']
	#width = alignment_results['Outer_Channels_Width']
	retries = 0

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Balancing channels...')

	while retries < 5 and not SequenceObj.Halt:

		# start the Nanocube algorithms
		SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
		SetScanChannel(climb, 1, UseOpticalSwitch)
		# hexapod_scan.Channel = 1
		# climb.Channel = 1

		Nanocube.GetHardwareStateTree().ActivateState('Center')
		sleep(.001*2000)

		# hexapod_scan.ExecuteNoneModal()
		# # check scan status
		# if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
			# LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
			# return 0
		# sleep(.001*500)

		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during channel balancing!')
			return 0

		 # wait to settle
		sleep(.001*500)

		# remember the final position
		topchanpos = Nanocube.GetAxesPositions()

		top_chan_peak_V = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)

		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Nanocube top channel peak position [{0:.2f}, {1:.2f}, {2:.2f}]um, Peak signal {3:.2f}V'.format(topchanpos[0],topchanpos[1],topchanpos[2],top_chan_peak_V))

		# repeat scan for the second channel
		# start the Nanocube climb algorithm
		SetScanChannel(climb, 2, UseOpticalSwitch)
		# climb.Channel = 2
		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during channel balancing!')
			return 0
		sleep(.001*500) # wait to settle

		# get the final position of second channel
		bottomchanpos = Nanocube.GetAxesPositions()
		bottom_chan_peak_V = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)

		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Nanocube bottom channel peak position [{0:.2f}, {1:.2f}, {2:.2f}]um Peak signal {3:.2f}V'.format(bottomchanpos[0],bottomchanpos[1],bottomchanpos[2],bottom_chan_peak_V))
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Bottom channel peak position ({0:.2f}, {1:.2f}, {2:.2f}) um'.format(bottomchanpos[0],bottomchanpos[1],bottomchanpos[2]))


		# double check and readjust roll if necessary
		# calculate the roll angle
		h = Math.Atan(Math.Abs(topchanpos[2] - bottomchanpos[2]))
		if h < 1:
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

		# calculate the roll angle
		r = Utility.RadianToDegree(Math.Atan(h / (width*1000)))
		rollangle = r
		if topchanpos[2] > bottomchanpos[2]:
		   rollangle = -rollangle

		# adjust the roll angle again
		Hexapod.MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		sleep(.001*500)

		retries += 1

	# check stop conditions
	if retries >= 3 or SequenceObj.Halt:
	   return 0

	# balanced position
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	Nanocube.MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

	# record final wet align hexapod position
	hposition = Hexapod.GetAxesPositions()
	alignment_results['Wet_Align_Hexapod_X'] = hposition[0]
	alignment_results['Wet_Align_Hexapod_Y'] = hposition[1]
	alignment_results['Wet_Align_Hexapod_Z'] = hposition[2]
	alignment_results['Wet_Align_Hexapod_U'] = hposition[3]
	alignment_results['Wet_Align_Hexapod_V'] = hposition[4]
	alignment_results['Wet_Align_Hexapod_W'] = hposition[5]

	# record final wet align nanocube position
	nposition = Nanocube.GetAxesPositions()
	alignment_results['Wet_Align_Nanocube_X'] = nposition[0]
	alignment_results['Wet_Align_Nanocube_Y'] = nposition[1]
	alignment_results['Wet_Align_Nanocube_Z'] = nposition[2]

	# get power based on instrument
	toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]

	# save process values
	alignment_results['Wet_Align_Peak_Power_Top_Chan'] = top_chan_peak_V
	alignment_results['Wet_Align_Peak_Power_Bottom_Chan'] = bottom_chan_peak_V
	alignment_results['Wet_Align_Balanced_Power_Top_Chan'] = toppower
	alignment_results['Wet_Align_Balanced_Power_Bottom_Chan'] = bottompower

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results
"""

#-------------------------------------------------------------------------------
# WetPitchAlign
# Scan pitch (V) to maximize photodiode current
#-------------------------------------------------------------------------------
def WetPitchAlign(SequenceObj, alignment_parameters, alignment_results):

	use_polarization_controller = alignment_parameters['use_polarization_controller']
	init_V = alignment_results['apply_epoxy_hexapod_final_V']
	use_hexapod_area_scan = False

	##############################
	##### Hexapod scan setup #####
	##############################
	# get the pitch sweep algo
	# hexapod_scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')

	# reload sweep parameters
	# minpower = alignment_parameters['HexapodRoughScanMinPower'] # this value will be in hexapod analog input unit.
	# hexapod_scan.Range1 = alignment_parameters['PitchOptimizationHexapodScanRange1']
	# hexapod_scan.Range2 = alignment_parameters['PitchOptimizationHexapodScanRange2']
	# hexapod_scan.Velocity = alignment_parameters['PitchOptimizationHexapodScanVelocity']
	# hexapod_scan.Frequency = alignment_parameters['PitchOptimizationHexapodScanFrequency']
	# SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1

	###############################
	##### Nanocube scan setup #####
	###############################
	# climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	# climb.Axis1 = alignment_parameters['Nanocube_Scan_Axis1']
	# climb.Axis2 = alignment_parameters['Nanocube_Scan_Axis2']
	# climb.ExecuteOnce = SequenceObj.AutoStep

	# set up a loop to zero in on the roll angle

	#width = alignment_results['Outer_Channels_Width']
	width = alignment_parameters['FirstLight_WG2WG_dist_mm']

	###################################
	##### End Nanocube scan setup #####
	###################################


	# get the pitch search X pull back distance
	# first perform a pull back, we will need to re-do the contact point again afterwards
	Hexapod.MoveAxisAbsolute('X', alignment_results['apply_epoxy_hexapod_final_X'] + alignment_parameters['PitchOptimizationPullBack'], Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisAbsolute('Y', alignment_results['apply_epoxy_hexapod_final_Y'], Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisAbsolute('Z', alignment_results['apply_epoxy_hexapod_final_Z'], Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisAbsolute('U', alignment_results['apply_epoxy_hexapod_final_U'], Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisAbsolute('V', alignment_results['apply_epoxy_hexapod_final_V'], Motion.AxisMotionSpeeds.Normal, True)
	Hexapod.MoveAxisAbsolute('W', alignment_results['apply_epoxy_hexapod_final_W'], Motion.AxisMotionSpeeds.Normal, True)

	Nanocube.GetHardwareStateTree().ActivateState('Center')
	sleep(.001*500)
	current_scan_channel = 1
	UseOpticalSwtich = alignment_parameters['UseOpticalSwitch']
	if ReadMonitorSignal(SetScanChannel(None, current_scan_channel, UseOpticalSwtich))[0] < alignment_parameters['ScanMinPowerThreshold']:
		if use_hexapod_area_scan:
			# HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .006, plot_output = False, UseOpticalSwtich = False)
			if not HexapodSpiralScan(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
				if not HexapodSpiralScan(SequenceObj, current_scan_channel,scan_dia_mm=.090, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod spiral scan failed on channel 1!')
					return False
		else:
			if not NanocubeSpiralScan(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
				if not NanocubeSpiralScan(SequenceObj, current_scan_channel,scan_dia_um=90, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1!')
					return False
		# hexapod_scan.ExecuteNoneModal()
		# if hexapod_scan.IsSuccess is False or SequenceObj.Halt:
		# 	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
		# 	return 0
		# sleep(.001*500)

	if use_polarization_controller:
		top_ch_polarization_position = FastOptimizePolarizationMPC201(SequenceObj, feedback_device = 'NanocubeAnalogInput', feedback_channel = SetScanChannel(None, current_scan_channel, UseOpticalSwtich), coarse_scan = False)

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

		if ReadMonitorSignal(SetScanChannel(None, current_scan_channel, UseOpticalSwtich))[0] < alignment_parameters['ScanMinPowerThreshold']:
			if use_hexapod_area_scan:
				# HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .006, plot_output = False, UseOpticalSwtich = False)
				if not HexapodSpiralScan(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
					if not HexapodSpiralScan(SequenceObj, current_scan_channel,scan_dia_mm=.090, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
						LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod spiral scan failed on channel 1!')
						return False
			else:
				if not NanocubeSpiralScan(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
					if not NanocubeSpiralScan(SequenceObj, current_scan_channel,scan_dia_um=90, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
						LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1!')
						return False

		if not NanocubeGradientClimb(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich) or SequenceObj.Halt:
			return False

		top_channel_power = ReadMonitorSignal(SetScanChannel(None, current_scan_channel, UseOpticalSwtich),n_measurements)



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
	if ReadMonitorSignal(SetScanChannel(None, current_scan_channel, UseOpticalSwtich),1)[0] < alignment_parameters['ScanMinPowerThreshold']:
		if use_hexapod_area_scan:
			# HexapodSpiralScan(SequenceObj, fb_channel, scan_dia_mm = .05, threshold = 0, axis1 = 'Y', axis2 = 'Z', speed = .006, plot_output = False, UseOpticalSwtich = False)
			if not HexapodSpiralScan(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
				if not HexapodSpiralScan(SequenceObj, current_scan_channel,scan_dia_mm=.090, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod spiral scan failed on channel 1!')
					return False
		else:
			if not NanocubeSpiralScan(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
				if not NanocubeSpiralScan(SequenceObj, current_scan_channel,scan_dia_um=90, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich):
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral scan failed on channel 1!')
					return False
	# hexapod_scan.Channel = 1
	# climb.Channel = 1

	# hexapod_scan.ExecuteNoneModal()
	# check scan status
	# if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
	# 	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
	# 	return 0
	# sleep(.001*500)

	if not NanocubeGradientClimb(SequenceObj, current_scan_channel, threshold = alignment_parameters['ScanMinPowerThreshold'], UseOpticalSwtich = UseOpticalSwtich) or SequenceObj.Halt:
			return False
	# climb.ExecuteNoneModal()
	# # check climb status
	# if climb.IsSuccess == False or SequenceObj.Halt:
	# 	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed at pitch scan final!')
	# 	return 0
	# sleep(.001*500)
	return alignment_results


#-------------------------------------------------------------------------------
# WetBalanceAlign
# Dry balanced align, but wet
# Touches the die with the force sensor and moves to bond gap
# Uses much tighter spec for roll align
#-------------------------------------------------------------------------------
def WetBalanceAlign(SequenceObj, alignment_parameters, alignment_results):

	##############################
	##### Hexapod scan setup #####
	##############################
	use_polarization_controller = alignment_parameters['use_polarization_controller']
	# minpower = alignment_parameters['HexapodRoughScanMinPower'] # this value will be in hexapod analog input unit.

	# hexapod_scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan') # get the pitch sweep algo
	# hexapod_scan.Range1 = alignment_parameters['PitchOptimizationHexapodScanRange1']
	# hexapod_scan.Range2 = alignment_parameters['PitchOptimizationHexapodScanRange2']
	# hexapod_scan.Velocity = alignment_parameters['PitchOptimizationHexapodScanVelocity']
	# hexapod_scan.Frequency = alignment_parameters['PitchOptimizationHexapodScanFrequency']
	# SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)


	###############################
	##### Nanocube scan setup #####
	###############################
	# climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	# climb.Axis1 = alignment_parameters['Nanocube_Scan_Axis1']
	# climb.Axis2 = alignment_parameters['Nanocube_Scan_Axis2']
	# climb.ExecuteOnce = SequenceObj.AutoStep

	###################################
	##### End Nanocube scan setup #####
	###################################

	# Re-establish the contact point again
	Hexapod.ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	# threshold = alignment_parameters['ForceSensorContactThreshold']
	backoff = alignment_parameters['BackOffFromContactDetection']
	bondgap = alignment_parameters['EpoxyBondGap']

	hexapod_initial_x = Hexapod.GetAxesPositions()[0]
	# monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < alignment_parameters['ForceSensorContactThreshold']:
		Hexapod.MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		sleep(0.01)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	# found contact point, back off set amount
	Hexapod.MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)

	hexapod_distance_to_touch = Hexapod.GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# put the required bondgap
	Hexapod.MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)



	if not OptimizeRollAngle(SequenceObj, alignment_parameters['FirstLight_WG2WG_dist_mm'], use_polarization_controller, max_z_difference_um = 0.2, speed = 5, UseOpticalSwtich = UseOpticalSwitch):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Roll optimize failed!')
		return 0

	"""
	retries = 0

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Balancing channels...')

	while retries < 5 and not SequenceObj.Halt:

		# start the Nanocube algorithms
		SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
		SetScanChannel(climb, 1, UseOpticalSwitch)
		# hexapod_scan.Channel = 1
		# climb.Channel = 1

		Nanocube.GetHardwareStateTree().ActivateState('Center')
		sleep(.001*2000)

		if ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument) < minpower:
			if not NanocubeSpiralScan(climb.Channel, 90, threshold = minpower):
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube spiral failed!')
				return 0

		if retries == 0:
			if not FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1,feedback_device='NanocubeAnalogInput'):
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Folarization scan failed!')
				return 0

		# hexapod_scan.ExecuteNoneModal()
		# # check scan status
		# if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
			# LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
			# return 0
		# sleep(.001*500)

		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during channel balancing!')
			return 0

		 # wait to settle
		sleep(.001*500)

		# remember the final position
		topchanpos = Nanocube.GetAxesPositions()

		top_chan_peak_V = ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument)

		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Nanocube top channel peak position [{0:.2f}, {1:.2f}, {2:.2f}]um, Peak signal {3:.2f}V'.format(topchanpos[0],topchanpos[1],topchanpos[2],top_chan_peak_V))

		# repeat scan for the second channel
		# start the Nanocube climb algorithm
		SetScanChannel(climb, 2, UseOpticalSwitch)
		# climb.Channel = 2
		if ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument) < minpower:
			if not NanocubeSpiralScan(climb.Channel, 90, threshold = minpower):
				return 0
		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during channel balancing!')
			return 0
		sleep(.001*500) # wait to settle

		# get the final position of second channel
		bottomchanpos = Nanocube.GetAxesPositions()
		bottom_chan_peak_V = ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument)

		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Nanocube bottom channel peak position [{0:.2f}, {1:.2f}, {2:.2f}]um Peak signal {3:.2f}V'.format(bottomchanpos[0],bottomchanpos[1],bottomchanpos[2],bottom_chan_peak_V))
		#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Bottom channel peak position ({0:.2f}, {1:.2f}, {2:.2f}) um'.format(bottomchanpos[0],bottomchanpos[1],bottomchanpos[2]))


		# double check and readjust roll if necessary
		# calculate the roll angle
		h = Math.Atan(Math.Abs(topchanpos[2] - bottomchanpos[2]))
		if h < 0.2:
		   break	# we achieved the roll angle when the optical Z difference is less than 1 um

		# calculate the roll angle
		r = Utility.RadianToDegree(Math.Asin(h / (width*1000)))
		rollangle = -r
		if topchanpos[2] > bottomchanpos[2]:
		   rollangle = -rollangle

		# adjust the roll angle again
		Hexapod.MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		sleep(.001*500)

		retries += 1

	# check stop conditions
	if retries >= 3 or SequenceObj.Halt:
	   return 0


	# balanced position
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	Nanocube.MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
	Nanocube.MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)
	"""

	# record final wet align hexapod position
	hposition = Hexapod.GetAxesPositions()
	alignment_results['Wet_Align_Hexapod'] = map(lambda a: round(a,4),hposition)
	# alignment_results['Wet_Align_Hexapod_X'] = hposition[0]
	# alignment_results['Wet_Align_Hexapod_Y'] = hposition[1]
	# alignment_results['Wet_Align_Hexapod_Z'] = hposition[2]
	# alignment_results['Wet_Align_Hexapod_U'] = hposition[3]
	# alignment_results['Wet_Align_Hexapod_V'] = hposition[4]
	# alignment_results['Wet_Align_Hexapod_W'] = hposition[5]

	# record final wet align nanocube position
	nposition = Nanocube.GetAxesPositions()
	alignment_results['Wet_Align_Nanocube'] = map(lambda a: round(a,2), nposition)
	# alignment_results['Wet_Align_Nanocube_X'] = nposition[0]
	# alignment_results['Wet_Align_Nanocube_Y'] = nposition[1]
	# alignment_results['Wet_Align_Nanocube_Z'] = nposition[2]

	# get power based on instrument
	SetScanChannel(climb, 1, UseOpticalSwitch)
	toppower = ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument)
	SetScanChannel(climb, 2, UseOpticalSwitch)
	bottompower = ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument)

	"""
	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]
	"""
	# save process values
	alignment_results['Wet_Align_Peak_Power_Top_Chan'] = round(top_chan_peak_V,3)
	alignment_results['Wet_Align_Peak_Power_Bottom_Chan'] = round(bottom_chan_peak_V,3)
	alignment_results['Wet_Align_Balanced_Power_Top_Chan'] = round(toppower,3)
	alignment_results['Wet_Align_Balanced_Power_Bottom_Chan'] = round(bottompower,3)

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
