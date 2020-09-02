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

def Template(SequenceObj, alignment_parameters, alignment_results):
	# DO NOT DELETE THIS METHOD
	# This is the method pattern for all python script called by AutomationCore PythonScriptManager.
	# The method arguments must be exactly as shown. They are the following:
	# SequenceName: This is the name of the process sequence that owns this step. This is required for retrieving process recipe values.
	# StepName: This is the name of the step that invokes this step. Useful for log entry and alerts to user.
	# TestMetrics: The object that holds all the process recipe values. See the C# code for usage.
	# TestResults: The object that stores all process result values. See the C# code for usage.

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

	loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
	fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem

	# reset the positions
	HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

	#release vacuum
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)

	# Wait for load complete and get serial number
	# possibly using a barcode scanner later	
	ret = UserFormInputDialog.ShowDialog('Load board', 'Please load board (wave guides to the left) and enter serial number:', True)
	if ret == True:
		TestResults.AddTestResult('Board_SN', UserFormInputDialog.ReturnValue)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Load FAU/MPO', 'Please load FAU/MPO and enter serial number:', True)
	if ret == True:
		TestResults.AddTestResult('MPO_SN', UserFormInputDialog.ReturnValue)
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Enter assembly ID', 'Please enter assembly serial number:', True)
	if ret == True:
		TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
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
	TestResults.AddTestResult('Epoxy_Tube_Number', UserFormInputDialog.ReturnValue)

	if 'EpoxyExpirationDate' in SequenceObj.ProcessPersistentData:
		UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyExpirationDate']
	else:
		UserFormInputDialog.ReturnValue = ''
	
	ret = UserFormInputDialog.ShowDialog('Epoxy expiration date', 'Please enter epoxy expiration date (MM/DD/YYYY):')
	if ret == False:
		return 0
	# save back to persistent data
	SequenceObj.ProcessPersistentData['EpoxyExpirationDate'] = UserFormInputDialog.ReturnValue
	TestResults.AddTestResult('Epoxy_Expiration_Date', UserFormInputDialog.ReturnValue)

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
			TestResults.AddTestResult('Optical_Input_Power_Top_Outer_Chan', p)
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
			TestResults.AddTestResult('Optical_Input_Power_Bottom_Outer_Chan', p)
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

	loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
	fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem

	# reset the positions
	HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)

	#release vacuum
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)

	# Wait for load complete and get serial number
	# possibly using a barcode scanner later	
	ret = UserFormInputDialog.ShowDialog('Load board', 'Please board (wave guides to the left) and enter serial number:', True)
	if ret == True:
		TestResults.AddTestResult('Board_SN', UserFormInputDialog.ReturnValue)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Load FAU', 'Please load FAU and enter serial number:', True)
	if ret == True:
		TestResults.AddTestResult('MPO_SN', UserFormInputDialog.ReturnValue)
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Enter assembly ID', 'Please enter assembly serial number:', True)
	if ret == True:
		TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
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
	TestResults.AddTestResult('Epoxy_Tube_Number', UserFormInputDialog.ReturnValue)

	if 'EpoxyExpirationDate' in SequenceObj.ProcessPersistentData:
		UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyExpirationDate']
	else:
		UserFormInputDialog.ReturnValue = ''
	
	ret = UserFormInputDialog.ShowDialog('Epoxy expiration date', 'Please enter epoxy expiration date (MM/DD/YYYY):')
	if ret == False:
		return 0
	# save back to persistent data
	SequenceObj.ProcessPersistentData['EpoxyExpirationDate'] = UserFormInputDialog.ReturnValue
	TestResults.AddTestResult('Epoxy_Expiration_Date', UserFormInputDialog.ReturnValue)

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results


#-------------------------------------------------------------------------------
# InitializeRepeatability
# Clears up test data and other prep work before process starts
# For repeatablity test use only
#-------------------------------------------------------------------------------
def InitializeRepeatability(SequenceObj, alignment_parameters, alignment_results):
	
	totalruns = 30
	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# clear the output data
	Utility.ShowProcessTextOnMainUI() # clear message

	TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
	TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())
	TestResults.AddTestResult('Assembly_SN','RepeatabilityTest')

	# inject the required fields, if not there already
	try:
		runnum = TestResults.RetrieveTestResult('CurrentRunNumber')
		runnum = runnum + 1
		TestResults.AddTestResult('CurrentRunNumber', runnum)
		if runnum > totalruns:
			if LogHelper.AskContinue('Repeatability test done.'):
				return 0
			else:
				TestResults.AddTestResult('CurrentRunNumber', 1)
				return alignment_results
	except:
		TestResults.AddTestResult('CurrentRunNumber', 1)

	return alignment_results

#-------------------------------------------------------------------------------
# Load
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def Load(SequenceObj, alignment_parameters, alignment_results):

	loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
	fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem

	# reset the positions
	HardwareFactory.Instance.GetHardwareByName('UVWandStages').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

	# Wait for load complete and get serial number
	# possibly using a barcode scanner later
	ret = UserFormInputDialog.ShowDialog('Load board', 'Please load board and then enter serial number:', True)
	if ret == True:
		TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
	else:
		return 0

	ret = UserFormInputDialog.ShowDialog('Load FAU', 'Please load FAU and enter serial number:', True)
	if ret == True:
		TestResults.AddTestResult('FAU_SN', UserFormInputDialog.ReturnValue)
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
	else:
		return 0
		
	ret = UserFormInputDialog.ShowDialog('Enter assembly ID', 'Please enter assembly serial number:', True)
	if ret == True:
		TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
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
	TestResults.AddTestResult('Epoxy_Tube_Number', UserFormInputDialog.ReturnValue)

	if 'EpoxyExpirationDate' in SequenceObj.ProcessPersistentData:
		UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyExpirationDate']
	else:
		UserFormInputDialog.ReturnValue = ''
	
	ret = UserFormInputDialog.ShowDialog('Epoxy expiration date', 'Please enter epoxy expiration date (MM/DD/YYYY):')
	if ret == False:
		return 0
	# save back to persistent data
	SequenceObj.ProcessPersistentData['EpoxyExpirationDate'] = UserFormInputDialog.ReturnValue
	TestResults.AddTestResult('Epoxy_Expiration_Date', UserFormInputDialog.ReturnValue)

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# OptimizeRollAngle
# Find the optimal roll angle for loop back on both channels
# NOTE: This routine is designed for loop back, not PD signal
#-------------------------------------------------------------------------------
def OptimizeRollAngle(SequenceObj, alignment_parameters, alignment_results):
	
	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# declare variables we will use
	retries = 0
	limit = 3

	# get the alignment algorithms
	hscan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
	nscan = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeRasterScan')
	optimalrollsearch = Alignments.AlignmentFactory.Instance.SelectAlignment('SimplexMaximumSearch')

	# get hexapod search parameters from recipe file
	hscan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
	hscan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
	hscan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
	hscan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
	hscan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
	hscan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
	hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
	
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
	hscan.Channel = nscan.Channel = 1
	hscan.ExecuteOnce = nscan.ExecuteOnce = SequenceObj.AutoStep

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
		'''
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
			hscan.ExecuteNoneModal()

			# wait to settle
			Utility.DelayMS(500)
		'''

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

	return alignment_results

def SetFirstLightPositionToBoard(SequenceObj, alignment_parameters, alignment_results):
	TestResults = SequenceObj.TestResults
	# define vision tool to use for easier editing
	initialposition = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
	#'FAUToBoardInitial'
	safe_approach = alignment_parameters['vision_align_safe_approach'] #'FAUToBoardInitial'
	die_side_position = alignment_parameters['DieFocusedPresetPosition'] #'FAUToBoardInitial'

	#vision_interim_gap_X = alignment_parameters['VisionInterimGapX'] #'FAUToBoardInitial'

	# Move hexapod to root coordinate system
	Hexapod.EnableZeroCoordinateSystem()

	# turn on the cameras
	DownCamera.Live(True)
	SideCamera.Live(True)
	
	IOController.GetHardwareStateTree().ActivateState('Default')
	
	
	# move cameras to preset position
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)
	SideCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	# Get hexapod and camera stage preset positions from recipe and go there
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)
	Hexapod.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0

	# set the hexapod pivot point for this process
	initpivot = alignment_parameters['InitialPivotPoint']
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	#turn off all lights and then set to recipe level
	#HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
	SideCamRingLightControl.GetHardwareStateTree().ActivateState('Default')
	DownCamRingLightControl.GetHardwareStateTree().ActivateState('Default')

	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	sn = alignment_results['Assembly_SN']
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration,  sn)
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTop.jpg')
	DownCamera.SaveToFile(dir)

	# run vision
	#####res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topdievision)
	res = vision_die_top()
	if res['Result'] != 'Success': # check result
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		return 0

	inputx = res['X']
	inputy = res['Y']
	inputangle = Utility.RadianToDegree(res['Angle'])

	# one more time for the MPO side
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	outputx = res['X']
	outputy = res['Y']
	outputangle = Utility.RadianToDegree(res['Angle'])

	# adjust the yaw angle
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)

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

	# retreive vision results
	outputx = res['X']
	outputy = res['Y']
	outputx2 = res['X2']
	outputy2 = res['Y2']

	# adjust the translation
	start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx, outputy))
	end = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('DownCameraTransform', ValueTuple[float,float](outputx2, outputy2))

	# calculate the distance between the first and last fiber channel in order to do pivot angle compensation
	TestResults.AddTestResult('Outer_Channels_Width', Math.Round(Math.Sqrt(Math.Pow(end.Item1 - start.Item1, 2) + pow(end.Item2 - start.Item2, 2)), 5))

	if SequenceObj.Halt:
		return 0

	# resume the translational motion again
	""" if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Y', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0 """

	# move in x, but with 200um gap remain
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', dest.Item1 - start.Item1 - TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionDryAlignGapX').DataItem, Motion.AxisMotionSpeeds.Slow, True):
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0
	
	if SequenceObj.Halt:
		return 0

	# re-do vision one more time at close proximity to achieve better initial alignment
	res = vision_die_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		return 0

	inputangle = Utility.RadianToDegree(res['Angle'])

	# one more time for the FAU side   
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	outputangle = Utility.RadianToDegree(res['Angle'])

	# do angle adjustment one more time
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)

	# re-do vision one more time at close proximity to achieve better initial alignment	   
	res = vision_die_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		return 0

	inputx = res['X']
	inputy = res['Y']
	inputangle = Utility.RadianToDegree(res['Angle'])

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
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
		return 0

	if SequenceObj.Halt:
		return 0

	# Start imaging from the side
	#######################################################################################################################
	#######################################################################################################################
	
	# find the die from side camera
	HardwareFactory.Instance.GetHardwareByName('SideCameraStages').GetHardwareStateTree().ActivateState(focusedposition)

	res = vision_die_side()
	if res['Result'] != 'Success':
		# if unsuccessful try again - workaround for backlight delay not working
		HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
		res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(sidedievision)
		if res['Result'] != 'Success':
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die side position.')
			return 0

	diex = res['X']
	diey = res['Y']
	dieangle = Utility.RadianToDegree(res['Angle'])

	# find the FAU side
	res = vision_FAU_side()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the MPO side position.')
		return 0

	mpox = res['WGX']
	mpoy = res['WGY']
	mpoangle = Utility.RadianToDegree(res['Angle'])

	# transform the coordinates so we know how to move
	dest = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](diex, diey))
	start = HardwareFactory.Instance.GetHardwareByName('MachineVision').ApplyTransform('SideCameraTransform', ValueTuple[float,float](mpox, mpoy))

	# move the mpo height to match that of the die height
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', dest.Item2 - start.Item2, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move MPO to match die height position.')
		return 0

	# adjust the yaw angle
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('V', mpoangle - dieangle, Motion.AxisMotionSpeeds.Normal, True)

	# now move x to put the mpo to process distance from die
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0

	if SequenceObj.Halt:
		return 0

	# remember this postion as optical z zero
	TestResults.AddTestResult('Optical_Z_Zero_Position', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))

	# adjust the starting Z position base on the recipe value
	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('Z', TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLightZOffsetFromVision').DataItem, Motion.AxisMotionSpeeds.Normal, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in Z direction during initial height offset adjustment.')
		return 0
	
	# Back to imaging the top
	#######################################################################################################################
	#######################################################################################################################
	res = vision_die_top()
	# check result
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		return 0

	inputangle = Utility.RadianToDegree(res['Angle'])

	# one more time for the FAU side
	HardwareFactory.Instance.GetHardwareByName('DownCamera').SetExposureTime(mpotopexposure)
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(topmpovision)

	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
		return 0

	outputangle = Utility.RadianToDegree(res['Angle'])
	
	# done vision, back to live view
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	# do angle adjustment one more time
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('W', outputangle - inputangle, Motion.AxisMotionSpeeds.Normal, True)
	
	###############################################################################################
	### NK Correct Y Position after all other motion because it is consistently off 01-Apr-2020
	if SequenceObj.Halt:
		return 0
	
	# re-do vision one more time at close proximity to achieve better initial alignment	   
	res = vision_die_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the die top position.')
		return 0

	inputx = res['X']
	inputy = res['Y']
	inputangle = Utility.RadianToDegree(res['Angle'])

	# one more time for the FAU top
	res = vision_FAU_top()
	if res['Result'] != 'Success':
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the FAU top position.')
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
	processdist = dest.Item1 - start.Item1 - TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'VisionDryAlignFinalGapX').DataItem

	if not HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', processdist, Motion.AxisMotionSpeeds.Slow, True):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
		return 0
	
	TestResults.AddTestResult('vision_align_hexapod_final_X', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X'))
	TestResults.AddTestResult('vision_align_hexapod_final_Y', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Y'))
	TestResults.AddTestResult('vision_align_hexapod_final_Z', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('Z'))
	TestResults.AddTestResult('vision_align_hexapod_final_U', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U'))
	TestResults.AddTestResult('vision_align_hexapod_final_V', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('V'))
	TestResults.AddTestResult('vision_align_hexapod_final_W', HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('W'))
	
	
	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results
		
		
def ManualSetFirstLightPositionToBoard(SequenceObj, alignment_parameters, alignment_results):
	TestResults = SequenceObj.TestResults
	# define vision tool to use for easier editing
	initialposition = alignment_parameters['InitialPresetPosition'] #'FAUToBoardInitial'
	#'FAUToBoardInitial'
	safe_approach = alignment_parameters['vision_align_safe_approach'] #'FAUToBoardInitial'
	die_side_position = alignment_parameters['DieFocusedPresetPosition'] #'FAUToBoardInitial'

	#vision_interim_gap_X = alignment_parameters['VisionInterimGapX'] #'FAUToBoardInitial'

	# Move hexapod to root coordinate system
	Hexapod.EnableZeroCoordinateSystem()

	# turn on the cameras
	DownCamera.Live(True)
	SideCamera.Live(True)
	
	IOController.GetHardwareStateTree().ActivateState('Default')
	
	
	# move cameras to preset position
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)
	SideCameraStages.GetHardwareStateTree().ActivateState(initialposition)

	# Get hexapod and camera stage preset positions from recipe and go there
	DownCameraStages.GetHardwareStateTree().ActivateState(initialposition)
	Hexapod.GetHardwareStateTree().ActivateState(initialposition)

	if SequenceObj.Halt:
		return 0

	# set the hexapod pivot point for this process
	initpivot = alignment_parameters['InitialPivotPoint']
	Hexapod.CreateKSDCoordinateSystem('PIVOT', Array[String](['X', 'Y', 'Z' ]), Array[float](initpivot) )

	#turn off all lights and then set to recipe level
	#HardwareFactory.Instance.GetHardwareByName('SideCamRingLightControl').SetIlluminationOff()
	SideCamRingLightControl.GetHardwareStateTree().ActivateState('default')
	DownCamRingLightControl.GetHardwareStateTree().ActivateState('default')

	# acquire image for vision
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Snap()
	# save to file
	sn = alignment_results['Assembly_SN']
	dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration,  sn)
	Utility.CreateDirectory(dir)
	dir = IO.Path.Combine(dir, 'DieTop.jpg')
	DownCamera.SaveToFile(dir)
	
	#Ask operator to set the first light position
	if LogHelper.AskContinue('Adjust hexapod to set first light position. Click Yes when done, No to abort.') == False:
		return 0
	
	alignment_results['vision_align_position'] = get_positions(SequenceObj)

	#IOController.GetHardwareStateTree().ActivateState('default')
	
	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# ApplyEpoxyRepeatability
# Manually apply epoxy and establish contact point
# For repeatability test use only. Will not actually dispense epoxy
#-------------------------------------------------------------------------------
def ApplyEpoxyRepeatability(SequenceObj, alignment_parameters, alignment_results):

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# Ask operator to apply epoxy. Use automation later
	# if not LogHelper.AskContinue('Apply epoxy. Click Yes when done.'):
	#	 return 0

	# open to whet epoxy
	whetgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetGap').DataItem
	# move to epoxy whet position
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -whetgap, Motion.AxisMotionSpeeds.Slow, True)
	# wait a few seconds
	Utility.DelayMS(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetTime').DataItem)
	# back to zero position
	zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Slow, True)

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
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		Utility.DelayMS(5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0

	# found contact point, back off set amount
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	if SequenceObj.Halt:
		return 0
	else:
		return alignment_results

#-------------------------------------------------------------------------------
# DriftMonitor
# Save drift data to the file
# For repeatability test use only. Save results to file
#-------------------------------------------------------------------------------
def DriftMonitor(SequenceObj, alignment_parameters, alignment_results):

	# Set up feedback variable
	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	chan1 = 0.0
	chan2 = 0.0
	# Set up file name
	run =  TestResults.RetrieveTestResult('CurrentRunNumber')
	filename = 'C:\Aligner\Data\DryAlignDriftMonitor_%d.csv.' % run
	f = open(filename, 'a')	   
	# set up timer
	start = DateTime.Now
	while (DateTime.Now - start).Seconds < 600:
		hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()		
		# check for feedback source
		if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
			power = pm. ReadPowers()
			chan1 = power.Item2[0]
			chan2 = power.Item2[1]
		else:
			chan1 = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
			chan2 = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
			
		f.write('%d,%f,%f,%f,%f,%f,%f,%f,%f\r\n' % ((DateTime.Now - start).Seconds,chan1,chan2,hposition[0],hposition[1],hposition[2],hposition[3],hposition[4],hposition[5]))
		# wait 5 seconds
		Utility.DelayMS(5000)
		Utility.ShowProcessTextOnMainUI(str((DateTime.Now - start).Seconds) + ' seconds elapsed.')
	f.close()

	Utility.ShowProcessTextOnMainUI()

	return alignment_results

#-------------------------------------------------------------------------------
# FinalizeRepeatability
# Save data to the file
# For repeatability test use only. Save results to file
#-------------------------------------------------------------------------------
def FinalizeRepeatability(SequenceObj, alignment_parameters, alignment_results):

	# get the relevant values first
	x = TestResults.RetrieveTestResult('Wet_Align_Hexapod_X')
	y = TestResults.RetrieveTestResult('Wet_Align_Hexapod_Y')
	z = TestResults.RetrieveTestResult('Wet_Align_Hexapod_Z')
	u = TestResults.RetrieveTestResult('Wet_Align_Hexapod_U')
	v = TestResults.RetrieveTestResult('Wet_Align_Hexapod_V')
	w = TestResults.RetrieveTestResult('Wet_Align_Hexapod_W')

	chan1 = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')
	chan2 = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')

	# construct the file name
	filename = 'C:\Aligner\Data\DryAlignRepeatabilityTest.csv.'
	try:
		# append new field if file already exists
		f = open(filename, 'a')		   
		f.write('%f,%f,%f,%f,%f,%f,%f,%f\r\n' % (chan1,chan2,x,y,z,u,v,w))
		f.close()
	except:
		# create the file and write the header
		f = open(filename, 'w')
		f.write('Chan1,Chan2,X,Y,Z,U,V,W\r\n')
		f.close()	 
		f = open(filename, 'a')
		f.write('%f,%f,%f,%f,%f,%f,%f,%f\r\n' % (chan1,chan2,x,y,z,u,v,w))
		f.close()	  

	return alignment_results
