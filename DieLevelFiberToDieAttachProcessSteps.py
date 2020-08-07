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
from System import Math
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

UseOpticalSwitch = True

def Template(StepName, SequenceObj, TestMetrics, TestResults):
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
		return 1
#-------------------------------------------------------------------------------
# Load loopback type alignment
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def LoadLoopbackDie(StepName, SequenceObj, TestMetrics, TestResults):

	loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
	fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem
	dievac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'TargetVaccumPortName').DataItem

	# reset the positions
	HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

	#release vacuum
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)

	# Wait for load complete and get serial number
	# possibly using a barcode scanner later	
	ret = UserFormInputDialog.ShowDialog('Load GF die', 'Please load die (wave guides to the left) and enter serial number:', True)
	if ret == True:
		TestResults.AddTestResult('Die_SN', UserFormInputDialog.ReturnValue)
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, True)
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
		return 1


def GetAndCheckUserInput(title, message):
	ret = False
	clear = True
	while ret == False:
		ret = UserFormInputDialog.ShowDialog(title, message, clear)
		if ret == True:
			m = re.search('[ <>:\"\/\\\|?*]+', UserFormInputDialog.ReturnValue)
			if(m != None):
				if LogHelper.AskContinue('Cannot contain <>:\/\"|?* or space. Click Yes to continue, No to abort.'):
					clear = False
					ret = False
				else:
					return None
		else:
			return None
	return UserFormInputDialog.ReturnValue

# Load PD
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def LoadPDDie(StepName, SequenceObj, TestMetrics, TestResults):

	loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
	fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem
	dievac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'TargetVaccumPortName').DataItem
	# reset the positions
	HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('UVWandStages').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
	
	#release vacuum
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
	# HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)
	
	
	# Wait for load complete and get serial number
	# possibly using a barcode scanner later
	Die_SN = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Die_SN').DataItem
	if LogHelper.AskContinue('Please load die (wave guides to the left) and verify serial number:\n' + Die_SN + '\nClick Yes when done, No to update value.') == False:
		Die_SN = GetAndCheckUserInput('Load GF die', 'Please load die (wave guides to the left) and enter serial number:')
	if not Die_SN == None:
		if not Die_SN == TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Die_SN').DataItem:
			TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Die_SN').DataItem = Die_SN
			TestMetrics.UpdateTestMetricTables()
		TestResults.AddTestResult('Die_SN', Die_SN)
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, True)
	else:
		return 0
	
	FAU_SN = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAU_SN').DataItem
	if LogHelper.AskContinue('Please load FAU and verify serial number:\n' + FAU_SN + '\nClick Yes when done, No to update value.') == False:
		FAU_SN = GetAndCheckUserInput('Load FAU', 'Please load FAU and enter serial number:')
	if not FAU_SN == None:
		if not FAU_SN == TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAU_SN').DataItem:
			TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAU_SN').DataItem = FAU_SN
			TestMetrics.UpdateTestMetricTables()
		TestResults.AddTestResult('FAU_SN', FAU_SN)
		HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
	else:
		return 0

	msg = GetAndCheckUserInput('Enter assembly ID', 'Please enter assembly serial number:')
	if msg != None:
		TestResults.AddTestResult('Assembly_SN', msg)
	else:
		return 0

	# epoxy related information
	# persist some of the values for next run
	
	# if 'EpoxyTubeNumber' in SequenceObj.ProcessPersistentData:
		# UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyTubeNumber']
	# else:
		# UserFormInputDialog.ReturnValue = ''
	
	EpoxyTubeNumber = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTubeNumber').DataItem
	if LogHelper.AskContinue('Please verify epoxy tube number:\n' + EpoxyTubeNumber + '\nClick Yes to accept, No to update value.') == False:
		EpoxyTubeNumber = UserFormInputDialog.ShowDialog('Epoxy tube number', 'Please enter epoxy tube number:')
	if not EpoxyTubeNumber == False:
		if not EpoxyTubeNumber == TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTubeNumber').DataItem:
			TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyTubeNumber').DataItem = EpoxyTubeNumber
			TestMetrics.UpdateTestMetricTables()
		TestResults.AddTestResult('Epoxy_Tube_Number', UserFormInputDialog.ReturnValue)
	else:
		return 0
	# save back to persistent data
	# SequenceObj.ProcessPersistentData['EpoxyTubeNumber'] = UserFormInputDialog.ReturnValue
	# TestResults.AddTestResult('Epoxy_Tube_Number', UserFormInputDialog.ReturnValue)

	# if 'EpoxyExpirationDate' in SequenceObj.ProcessPersistentData:
		# UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyExpirationDate']
	# else:
		# UserFormInputDialog.ReturnValue = ''
	
	EpoxyExpirationDate = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyExpirationDate').DataItem
	if LogHelper.AskContinue('Please verify epoxy expiration date:\n' + EpoxyExpirationDate + '\nClick Yes to accept, No to update value.') == False:
		EpoxyExpirationDate = UserFormInputDialog.ShowDialog('Epoxy expiration date', 'Please enter epoxy expiration date (MM/DD/YYYY):')
	if not EpoxyExpirationDate == False:
		if not EpoxyExpirationDate == TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyExpirationDate').DataItem:
			TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyExpirationDate').DataItem = EpoxyExpirationDate
			TestMetrics.UpdateTestMetricTables()
		TestResults.AddTestResult('Epoxy_Expiration_Date', UserFormInputDialog.ReturnValue)
	else:
		return 0
	# save back to persistent data
	# SequenceObj.ProcessPersistentData['EpoxyExpirationDate'] = UserFormInputDialog.ReturnValue

	if SequenceObj.Halt:
		return 0
	else:
		dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
		Utility.CreateDirectory(dir)
		return 1

#-------------------------------------------------------------------------------
# AdjustPolarization
# Ask the user to manually adjust ploarization for the polarization-sensitive channels
#-------------------------------------------------------------------------------
def AdjustPolarization(StepName, SequenceObj, TestMetrics, TestResults):
	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	#Ask operator to adjust polarization
	if LogHelper.AskContinue('Adjust polarization on polarization-sensitive channels to maximize PD current. Click Yes when done, No to abort.') == False:
		return 0

	if SequenceObj.Halt:
		return 0
	else:
		return 1

#-------------------------------------------------------------------------------
# BalanceWedAlignment
# Balance alignment of the channels in epoxy with pitch sweep optimization
#-------------------------------------------------------------------------------
def SweepOptimizedBalanceWetAlignment(StepName, SequenceObj, TestMetrics, TestResults):

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

	# get the pitch sweep algo
	scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
	pitchsweep = Alignments.AlignmentFactory.Instance.SelectAlignment('PitchSweepOptimization')

	# reload sweep parameters
	scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange1').DataItem
	scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange2').DataItem
	scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanVelocity').DataItem
	scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanFrequency').DataItem
	SetScanChannel(scan, 1, UseOpticalSwitch)
	# scan.Channel = 1

	Axis = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationAxis').DataItem
	
	init_V = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()[4]
	
	pitchsweep.Axis = Axis
	pitchsweep.MotionStages = HardwareFactory.Instance.GetHardwareByName('Hexapod')
	pitchsweep.StartPosition = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleStart').DataItem
	pitchsweep.EndPosition = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleEnd').DataItem
	pitchsweep.StepSize = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationStepSize').DataItem
	pitchsweep.FeedbackUnit = 'V'
	pitchsweep.ExecuteOnce = scan.ExecuteOnce = SequenceObj.AutoStep

	# create the pitch feedback delegate function
	def EvalPitch(a):
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute(Axis, a, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		Utility.DelayMS(500)
		scan.ExecuteNoneModal()
		# wait to settle
		Utility.DelayMS(500)
		return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)

	pitchsweep.EvalFunction = Func[float,float](EvalPitch)

	# get the pitch search X pull back distance
	# first perform a pull back, we will need to re-do the contact point again afterwards
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationPullBack').DataItem, Motion.AxisMotionSpeeds.Normal, True)		  
	
	# readjust the pitch pivot point
	zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
	#zeropitch = TestResults.RetrieveTestResult('Pitch_Pivot_X')
	offset = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X') - zero
	# HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = zeropitch + offset
	# enable the new pivot point
	# HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')		 
	
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimizing hexapod pitch angle.')
	# start sweep
	
	if False:
		pitchsweep.ExecuteNoneModal()
		# check result
		if not pitchsweep.IsSuccess or SequenceObj.Halt:
			return 0
	else:
		next_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleStart').DataItem
		max_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleEnd').DataItem
		scan_angles = list()
		while next_V <= max_V:
			scan_angles.append(next_V)
			next_V = next_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationStepSize').DataItem
			
			if len(scan_angles) > 100:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Number of pitch angle scan points exceeds 100.')
				return 0
			
		peak_V_so_far = init_V
		peak_IFF_so_far = 0
		num_IFF_samples = 5 # average this many samples when checking for peak IFF found
	
		for current_V in scan_angles:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
			HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
			Utility.DelayMS(500)
			scan.ExecuteNoneModal()
			Utility.DelayMS(500)
			
			sum_IFF = 0
			for i in range(num_IFF_samples):
				sum_IFF = sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
				
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(sum_IFF/num_IFF_samples))
			if (sum_IFF/num_IFF_samples) > peak_IFF_so_far:
				peak_IFF_so_far = sum_IFF/num_IFF_samples
				peak_V_so_far = current_V
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')
			if SequenceObj.Halt:
				return 0
				
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', peak_V_so_far, Motion.AxisMotionSpeeds.Normal, True)
	Utility.DelayMS(500)
	scan.ExecuteNoneModal()
	Utility.DelayMS(500)

	# Re-establish the contact point again
	HardwareFactory.Instance.GetHardwareByName('Hexapod').ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
	backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
	bondgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyBondGap').DataItem
	# monitor force change
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

	scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
	scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
	scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
	scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem

	# set up a loop to zero in on the roll angle
	width = TestResults.RetrieveTestResult('Outer_Channels_Width')
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
		Utility.DelayMS(500)

		# remember the final position
		topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

		# repeat scan for the second channel
		SetScanChannel(scan, 2, UseOpticalSwitch)
		# scan.Channel = 2

		# start the algorithms again
		scan.ExecuteNoneModal()
		# check scan status
		if scan.IsSuccess == False or SequenceObj.Halt:
			return 0

		# wait to settle
		Utility.DelayMS(500)

		# get the final position of second channel
		bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

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
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		Utility.DelayMS(500)

		retries += 1
	
	# check stop conditions
	if retries >= 3 or SequenceObj.Halt:
	   return 0

	# balanced position
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

	# record final wet align hexapod position
	hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
	TestResults.AddTestResult('Wet_Align_Hexapod_X', hposition[0])
	TestResults.AddTestResult('Wet_Align_Hexapod_Y', hposition[1])
	TestResults.AddTestResult('Wet_Align_Hexapod_Z', hposition[2])
	TestResults.AddTestResult('Wet_Align_Hexapod_U', hposition[3])
	TestResults.AddTestResult('Wet_Align_Hexapod_V', hposition[4])
	TestResults.AddTestResult('Wet_Align_Hexapod_W', hposition[5])

	# get power based on instrument	   
	toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]

	# save process values
	TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan', toppower)
	TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan', bottompower)

	if SequenceObj.Halt:
		return 0
	else:
		return 1
		
def BalanceWetAlignNanocube(StepName, SequenceObj, TestMetrics, TestResults):

	# turn on the cameras
	HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
	HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)
	
	init_V = TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_V')
	
	##############################
	##### Hexapod scan setup #####
	##############################
	# get the pitch sweep algo
	hexapod_scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')

	# reload sweep parameters
	hexapod_scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange1').DataItem
	hexapod_scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange2').DataItem
	hexapod_scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanVelocity').DataItem
	hexapod_scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanFrequency').DataItem
	SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1

	###############################
	##### Nanocube scan setup #####
	###############################
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	climb.ExecuteOnce = SequenceObj.AutoStep
	
	# set up a loop to zero in on the roll angle
	
	#width = TestResults.RetrieveTestResult('Outer_Channels_Width')
	width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLight_WG2WG_dist_mm').DataItem
	#topchanpos = [ 50.0, 50.0, 50.0 ]
	#bottomchanpos = [ 50.0, 50.0, 50.0 ]
	retries = 0
	
	###################################
	##### End Nanocube scan setup #####
	###################################
	

	# get the pitch search X pull back distance
	# first perform a pull back, we will need to re-do the contact point again afterwards
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_X') + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationPullBack').DataItem, Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Y', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_Y'), Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Z', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_Z'), Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('U', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_U'), Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_V'), Motion.AxisMotionSpeeds.Normal, True)	
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('W', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_W'), Motion.AxisMotionSpeeds.Normal, True)
		
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
	Utility.DelayMS(500)
	
	hexapod_scan.ExecuteNoneModal()
	if hexapod_scan.IsSuccess is False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
		return 0
	Utility.DelayMS(500)
	
	# readjust the pitch pivot point
	zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
	#zeropitch = TestResults.RetrieveTestResult('Pitch_Pivot_X')
	offset = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X') - zero
	# HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = zeropitch + offset
	# enable the new pivot point
	# HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')		 
	
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimizing hexapod pitch angle.')
	# start sweep
	if False:
		next_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleStart').DataItem
		max_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleEnd').DataItem
		scan_angles = list()
		while next_V <= max_V:
			scan_angles.append(next_V)
			next_V = next_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationStepSize').DataItem
			
			if len(scan_angles) > 100:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Number of pitch angle scan points exceeds 100.')
				return 0
			
		peak_V_so_far = init_V
		peak_IFF_so_far = 0
		num_IFF_samples = 5 # average this many samples when checking for peak IFF found
	
		for current_V in scan_angles:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
			HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
			Utility.DelayMS(500)
			scan.ExecuteNoneModal()
			Utility.DelayMS(500)
			
			sum_IFF = 0
			for i in range(num_IFF_samples):
				sum_IFF = sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
				
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(sum_IFF/num_IFF_samples))
			if (sum_IFF/num_IFF_samples) > peak_IFF_so_far:
				peak_IFF_so_far = sum_IFF/num_IFF_samples
				peak_V_so_far = current_V
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')
			if SequenceObj.Halt:
				return 0
	if True:
		next_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleStart').DataItem
		max_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleEnd').DataItem
		scan_angles = list()
		while next_V <= max_V:
			scan_angles.append(next_V)
			next_V = next_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationStepSize').DataItem
			
			if len(scan_angles) > 100: #chech if someone made a bonehead mistake that resulted in way too many scan points and abort if necessary
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Number of pitch angle scan points exceeds 100, reduce number of scan points.')
				return 0
			
		peak_V_so_far = init_V
		peak_IFF_so_far = 0
		num_IFF_samples = 5 # average this many samples when checking for peak IFF found
	
		for current_V in scan_angles:
			#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
			HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
			Utility.DelayMS(500)
			
			# start the Nanocube algorithms
			SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
			SetScanChannel(climb, 1, UseOpticalSwitch)
			# hexapod_scan.Channel = 1
			# climb.Channel = 1
			
			# # Move hexapod to middle so that climb doesnt cause walk-off from center as the routine continues to run
			HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
			Utility.DelayMS(500)
			
			hexapod_scan.ExecuteNoneModal()
			# check scan status
			if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed during pitch scan!')
				return 0
			Utility.DelayMS(500)
			
			climb.ExecuteNoneModal()
			if climb.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during pitch scan!')
				return 0
			Utility.DelayMS(500)
			
			top_sum_IFF = 0
			for i in range(num_IFF_samples):
				top_sum_IFF = top_sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
				
			SetScanChannel(climb, 2, UseOpticalSwitch)
			# climb.Channel = 2
			climb.ExecuteNoneModal()
			# check climb status
			if climb.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch2 gradient climb scan failed during pitch scan!')
				return 0
			
			Utility.DelayMS(500)
			
			bottom_sum_IFF = 0
			for i in range(num_IFF_samples):
				bottom_sum_IFF = bottom_sum_IFF + HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
			
			# display peak aligned position
			peak_align_position = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
			hexapod_current_position = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Completed scan {0:d}/{1:d} | Pitch angle (deg) |{2:2.4f}| Final nanocube position um |{4:.3f}|{5:.3f}|{6:.3f}| Peak singal ch1 and ch2 V |{7:.3f}|{8:.3f}'.format(scan_angles.index(current_V)+1, len(scan_angles), hexapod_current_position[4], hexapod_current_position[4], peak_align_position[0], peak_align_position[1], peak_align_position[2], top_sum_IFF/num_IFF_samples, bottom_sum_IFF/num_IFF_samples))
				
			#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(top_sum_IFF/num_IFF_samples))
			if (top_sum_IFF/num_IFF_samples) > peak_IFF_so_far:
				peak_IFF_so_far = top_sum_IFF/num_IFF_samples
				peak_V_so_far = current_V
				#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')
				
			if SequenceObj.Halt:
				return 0
	
	
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
	Utility.DelayMS(500)
	SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1
	SetScanChannel(climb, 1, UseOpticalSwitch)
	# climb.Channel = 1			   
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', peak_V_so_far, Motion.AxisMotionSpeeds.Normal, True)
	Utility.DelayMS(2000)
	hexapod_scan.ExecuteNoneModal()
	# check scan status
	if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
		return 0
	Utility.DelayMS(500)
	
	climb.ExecuteNoneModal()
	# check climb status
	if climb.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed at pitch scan final!')
		return 0
	Utility.DelayMS(500)

	# Re-establish the contact point again
	HardwareFactory.Instance.GetHardwareByName('Hexapod').ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
	backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
	bondgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyBondGap').DataItem
	
	hexapod_initial_x = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()[0]
	# monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		Utility.DelayMS(5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0
	
	hexapod_distance_to_touch = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# found contact point, back off set amount
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	# set up a loop to zero in on the roll angle
	width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLight_WG2WG_dist_mm').DataItem
	#width = TestResults.RetrieveTestResult('Outer_Channels_Width')
	retries = 0

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Balancing channels...')

	while retries < 5 and not SequenceObj.Halt:

		# start the Nanocube algorithms
		SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
		SetScanChannel(climb, 1, UseOpticalSwitch)
		# hexapod_scan.Channel = 1
		# climb.Channel = 1

		HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
		Utility.DelayMS(2000)
		
		# hexapod_scan.ExecuteNoneModal()
		# # check scan status
		# if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
			# LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
			# return 0
		# Utility.DelayMS(500)
		
		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during channel balancing!')
			return 0
		
		 # wait to settle
		Utility.DelayMS(500)

		# remember the final position
		topchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

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
		Utility.DelayMS(500) # wait to settle

		# get the final position of second channel
		bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
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
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		Utility.DelayMS(500)

		retries += 1
	
	# check stop conditions
	if retries >= 3 or SequenceObj.Halt:
	   return 0

	# balanced position
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

	# record final wet align hexapod position
	hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
	TestResults.AddTestResult('Wet_Align_Hexapod_X', hposition[0])
	TestResults.AddTestResult('Wet_Align_Hexapod_Y', hposition[1])
	TestResults.AddTestResult('Wet_Align_Hexapod_Z', hposition[2])
	TestResults.AddTestResult('Wet_Align_Hexapod_U', hposition[3])
	TestResults.AddTestResult('Wet_Align_Hexapod_V', hposition[4])
	TestResults.AddTestResult('Wet_Align_Hexapod_W', hposition[5])
	
	# record final wet align nanocube position
	nposition = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
	TestResults.AddTestResult('Wet_Align_Nanocube_X', nposition[0])
	TestResults.AddTestResult('Wet_Align_Nanocube_Y', nposition[1])
	TestResults.AddTestResult('Wet_Align_Nanocube_Z', nposition[2])

	# get power based on instrument	   
	toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
	bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]

	# save process values
	TestResults.AddTestResult('Wet_Align_Peak_Power_Top_Chan', top_chan_peak_V)
	TestResults.AddTestResult('Wet_Align_Peak_Power_Bottom_Chan', bottom_chan_peak_V)
	TestResults.AddTestResult('Wet_Align_Balanced_Power_Top_Chan', toppower)
	TestResults.AddTestResult('Wet_Align_Balanced_Power_Bottom_Chan', bottompower)

	if SequenceObj.Halt:
		return 0
	else:
		return 1
		
def WetPitchAlign(StepName, SequenceObj, TestMetrics, TestResults):
   
	init_V = TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_V')
	
	##############################
	##### Hexapod scan setup #####
	##############################
	# get the pitch sweep algo
	hexapod_scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')

	# reload sweep parameters
	minpower = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanMinPower').DataItem # this value will be in hexapod analog input unit. 
	hexapod_scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange1').DataItem
	hexapod_scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange2').DataItem
	hexapod_scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanVelocity').DataItem
	hexapod_scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanFrequency').DataItem
	SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1

	###############################
	##### Nanocube scan setup #####
	###############################
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	climb.ExecuteOnce = SequenceObj.AutoStep
	
	# set up a loop to zero in on the roll angle
	
	#width = TestResults.RetrieveTestResult('Outer_Channels_Width')
	width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLight_WG2WG_dist_mm').DataItem
	#topchanpos = [ 50.0, 50.0, 50.0 ]
	#bottomchanpos = [ 50.0, 50.0, 50.0 ]
	retries = 0
	
	###################################
	##### End Nanocube scan setup #####
	###################################
	

	# get the pitch search X pull back distance
	# first perform a pull back, we will need to re-do the contact point again afterwards
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_X') + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationPullBack').DataItem, Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Y', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_Y'), Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Z', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_Z'), Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('U', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_U'), Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_V'), Motion.AxisMotionSpeeds.Normal, True)	
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('W', TestResults.RetrieveTestResult('apply_epoxy_hexapod_final_W'), Motion.AxisMotionSpeeds.Normal, True)
		
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
	Utility.DelayMS(500)
	
	if ChannelsAnalogSignals.ReadValue(hexapod_scan.MonitorInstrument) < minpower:
		hexapod_scan.ExecuteNoneModal()
		if hexapod_scan.IsSuccess is False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
			return 0
		Utility.DelayMS(500)
	
	# HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = zeropitch + offset
	# enable the new pivot point
	# HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')		 
	
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimizing hexapod pitch angle.')
	# start sweep
	if True:
		next_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleStart').DataItem
		max_V = init_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationRelativeAngleEnd').DataItem
		scan_angles = list()
		while next_V <= max_V:
			scan_angles.append(next_V)
			next_V = next_V + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationStepSize').DataItem
			
			if len(scan_angles) > 100: #chech if someone made a bonehead mistake that resulted in way too many scan points and abort if necessary
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Number of pitch angle scan points exceeds 100, reduce number of scan points.')
				return 0
			
		peak_V_so_far = init_V
		peak_IFF_so_far = 0
		num_IFF_samples = 5 # average this many samples when checking for peak IFF found
	
		for current_V in scan_angles:
			#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Executing pitch scan {0:d}/{1:d}'.format(scan_angles.index(current_V)+1,len(scan_angles)))
			HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', current_V, Motion.AxisMotionSpeeds.Normal, True)
			Utility.DelayMS(500)
			
			# start the Nanocube algorithms
			SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
			SetScanChannel(climb, 1, UseOpticalSwitch)
			# hexapod_scan.Channel = 1
			# climb.Channel = 1
			
			# # Move hexapod to middle so that climb doesnt cause walk-off from center as the routine continues to run
			HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
			Utility.DelayMS(500)
			if ChannelsAnalogSignals.ReadValue(hexapod_scan.MonitorInstrument) < minpower:
				hexapod_scan.ExecuteNoneModal()
				# check scan status
				if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
					LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed during pitch scan!')
					return 0
				Utility.DelayMS(500)
			
			climb.ExecuteNoneModal()
			if climb.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during pitch scan!')
				return 0
			Utility.DelayMS(500)
			
			top_sum_IFF = 0
			for i in range(num_IFF_samples):
				top_sum_IFF = top_sum_IFF + ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument)
				
			SetScanChannel(climb, 2, UseOpticalSwitch)
			# climb.Channel = 2
			climb.ExecuteNoneModal()
			# check climb status
			if climb.IsSuccess == False or SequenceObj.Halt:
				LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch2 gradient climb scan failed during pitch scan!')
				return 0
			
			Utility.DelayMS(500)
			
			bottom_sum_IFF = 0
			for i in range(num_IFF_samples):
				bottom_sum_IFF = bottom_sum_IFF + ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument)
			
			# display peak aligned position
			peak_align_position = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
			hexapod_current_position = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Completed scan {0:d}/{1:d} | Pitch angle (deg) |{2:2.4f}| Final nanocube position um |{4:.3f}|{5:.3f}|{6:.3f}| Peak singal ch1 and ch2 V |{7:.3f}|{8:.3f}'.format(scan_angles.index(current_V)+1, len(scan_angles), hexapod_current_position[4], hexapod_current_position[4], peak_align_position[0], peak_align_position[1], peak_align_position[2], top_sum_IFF/num_IFF_samples, bottom_sum_IFF/num_IFF_samples))
				
			#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Peak signal found: {0:0.3f}'.format(top_sum_IFF/num_IFF_samples))
			if (top_sum_IFF/num_IFF_samples) > peak_IFF_so_far:
				peak_IFF_so_far = top_sum_IFF/num_IFF_samples
				peak_V_so_far = current_V
				#LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'New peak V found!')
				
			if SequenceObj.Halt:
				return 0
	
	
	HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
	Utility.DelayMS(500)
	SetScanChannel(climb, 1, UseOpticalSwitch)
	SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1
	# climb.Channel = 1			   
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('V', peak_V_so_far, Motion.AxisMotionSpeeds.Normal, True)
	Utility.DelayMS(2000)
	hexapod_scan.ExecuteNoneModal()
	# check scan status
	if hexapod_scan.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Hexapod area scan failed!')
		return 0
	Utility.DelayMS(500)
	
	climb.ExecuteNoneModal()
	# check climb status
	if climb.IsSuccess == False or SequenceObj.Halt:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed at pitch scan final!')
		return 0
	Utility.DelayMS(500)

	return 1

def WetBalanceAlign(StepName, SequenceObj, TestMetrics, TestResults):
	##############################
	##### Hexapod scan setup #####
	##############################
	# get the pitch sweep algo
	hexapod_scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')

	# reload sweep parameters
	minpower = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanMinPower').DataItem # this value will be in hexapod analog input unit. 
	hexapod_scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange1').DataItem
	hexapod_scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange2').DataItem
	hexapod_scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanVelocity').DataItem
	hexapod_scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanFrequency').DataItem
	SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
	# hexapod_scan.Channel = 1

	###############################
	##### Nanocube scan setup #####
	###############################
	climb = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeGradientScan')
	climb.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis1').DataItem
	climb.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'Nanocube_Scan_Axis2').DataItem
	climb.ExecuteOnce = SequenceObj.AutoStep
	
	# set up a loop to zero in on the roll angle
	
	#width = TestResults.RetrieveTestResult('Outer_Channels_Width')
	width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLight_WG2WG_dist_mm').DataItem
	#topchanpos = [ 50.0, 50.0, 50.0 ]
	#bottomchanpos = [ 50.0, 50.0, 50.0 ]
	retries = 0
	
	###################################
	##### End Nanocube scan setup #####
	###################################

	# Re-establish the contact point again
	HardwareFactory.Instance.GetHardwareByName('Hexapod').ZeroForceSensor()
	# get initial force
	forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
	startforce = forcesensor.ReadValueImmediate()
	# start force monitor
	threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
	backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
	bondgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyBondGap').DataItem
	
	hexapod_initial_x = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()[0]
	# monitor force change
	while (forcesensor.ReadValueImmediate() - startforce) < threshold:
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
		Utility.DelayMS(5)
		# check for user interrupt
		if SequenceObj.Halt:
			return 0
	
	hexapod_distance_to_touch = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()[0] - hexapod_initial_x
	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Hexapod moved {0:.3f} mm in X before force sensor threshold reached.'.format(hexapod_distance_to_touch))

	# found contact point, back off set amount
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
	# put the required bondgap
	HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

	
	# set up a loop to zero in on the roll angle
	width = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FirstLight_WG2WG_dist_mm').DataItem
	#width = TestResults.RetrieveTestResult('Outer_Channels_Width')
	retries = 0

	LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Balancing channels...')

	while retries < 5 and not SequenceObj.Halt:

		# start the Nanocube algorithms
		SetScanChannel(hexapod_scan, 1, UseOpticalSwitch)
		SetScanChannel(climb, 1, UseOpticalSwitch)
		# hexapod_scan.Channel = 1
		# climb.Channel = 1

		HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState('Center')
		Utility.DelayMS(2000)
		
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
		# Utility.DelayMS(500)
		
		climb.ExecuteNoneModal()
		# check climb status
		if climb.IsSuccess == False or SequenceObj.Halt:
			LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Nanocube ch1 gradient climb scan failed during channel balancing!')
			return 0
		
		 # wait to settle
		Utility.DelayMS(500)

		# remember the final position
		topchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()

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
		Utility.DelayMS(500) # wait to settle

		# get the final position of second channel
		bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
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
		HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
		# wait to settle
		Utility.DelayMS(500)

		retries += 1
	
	# check stop conditions
	if retries >= 3 or SequenceObj.Halt:
	   return 0

	# balanced position
	ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
	zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
	HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

	# record final wet align hexapod position
	hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
	TestResults.AddTestResult('Wet_Align_Hexapod_X', hposition[0])
	TestResults.AddTestResult('Wet_Align_Hexapod_Y', hposition[1])
	TestResults.AddTestResult('Wet_Align_Hexapod_Z', hposition[2])
	TestResults.AddTestResult('Wet_Align_Hexapod_U', hposition[3])
	TestResults.AddTestResult('Wet_Align_Hexapod_V', hposition[4])
	TestResults.AddTestResult('Wet_Align_Hexapod_W', hposition[5])
	
	# record final wet align nanocube position
	nposition = HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxesPositions()
	TestResults.AddTestResult('Wet_Align_Nanocube_X', nposition[0])
	TestResults.AddTestResult('Wet_Align_Nanocube_Y', nposition[1])
	TestResults.AddTestResult('Wet_Align_Nanocube_Z', nposition[2])

	# get power based on instrument
	SetScanChannel(climb, 1, UseOpticalSwitch)
	toppower = round(ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument),6)
	SetScanChannel(climb, 2, UseOpticalSwitch)
	bottompower = round(ChannelsAnalogSignals.ReadValue(climb.MonitorInstrument), 6)

	pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
	if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
		toppower = pm.ReadPowers().Item2[0]
		bottompower = pm.ReadPowers().Item2[1]

	# save process values
	TestResults.AddTestResult('Wet_Align_Peak_Power_Top_Chan', top_chan_peak_V)
	TestResults.AddTestResult('Wet_Align_Peak_Power_Bottom_Chan', bottom_chan_peak_V)
	TestResults.AddTestResult('Wet_Align_Balanced_Power_Top_Chan', toppower)
	TestResults.AddTestResult('Wet_Align_Balanced_Power_Bottom_Chan', bottompower)

	if SequenceObj.Halt:
		return 0
	else:
		return 1

#-------------------------------------------------------------------------------
# Finalize
# Save data to the file
#-------------------------------------------------------------------------------
def Finalize(StepName, SequenceObj, TestMetrics, TestResults):

	# # get process values
	# drytop = TestResults.RetrieveTestResult('Dry_Align_Balanced_Power_Top_Chan')
	# drybottom = TestResults.RetrieveTestResult('Dry_Align_Balanced_Power_Bottom_Chan')
	# wettop = TestResults.RetrieveTestResult('Wet_Align_Balanced_Power_Top_Chan')
	# wetbottom = TestResults.RetrieveTestResult('Wet_Align_Balanced_Power_Bottom_Chan')
	# uvtop = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Top_Outer_Chan')
	# uvbottom = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan')
	# #releasetop = TestResults.RetrieveTestResult('Post_Release_Power_Top_Outer_Chan')
	# #releasebottom = TestResults.RetrieveTestResult('Post_Release_Power_Bottom_Outer_Chan')

	# # save process values
	# TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan_Loss', round(drytop - wettop, 6))
	# TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan_Loss', round(drybottom - wetbottom, 6))

	# TestResults.AddTestResult('Post_UV_Cure_Power_Top_Outer_Chan_Loss', round(wettop - uvtop, 6))
	# TestResults.AddTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan_Loss', round(wetbottom - uvbottom, 6))

	# #TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan_Loss', round(uvtop - releasetop, 6))
	# #TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan_Loss', round(uvbottom - releasebottom, 6))

	#check user comment
	if TestResults.IsTestResultExists('Comment') == False:
		if Station.Instance.UserComment:
			TestResults.AddTestResult('Comment', Station.Instance.UserComment)
	else:
		if Station.Instance.UserComment:
			TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult('Comment') + ' ' + Station.Instance.UserComment)
		else:
			TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult('Comment'))

	#save the data file
	TestResults.SaveTestResultsToStorage(TestResults.RetrieveTestResult('Assembly_SN'))

	return 1
