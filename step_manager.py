import clr
clr.AddReferenceToFile('Utility.dll')
clr.AddReferenceToFile('Process.dll')
from Utility import *
import os.path
import json
import re
from time import sleep
from collections import *
# from AlignerUtil import GetAndCheckUserInput
from AlignerUtil import GetAssemblyParameterAndResults
import shutil
from System import DateTime
from System.Collections.Generic import List
from datetime import datetime

from HAL import Vision
from HAL import Motion
from HAL import HardwareFactory
from alignerCommon import *
from Process import *

def step_manager(SequenceObj, alignStep):
	# This method loads alignment_parameters and alignment_results files

	# load the alignment parameters file
	parameters_filename = os.path.join(SequenceObj.RootPath, 'Sequences', SequenceObj.ProcessSequenceName + '.cfg')
	if os.path.exists(parameters_filename):
		with open(parameters_filename, 'r') as f:
			alignment_parameters = json.load(f, object_pairs_hook=OrderedDict)
	else:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Could not find alignment config file at {}'.format(parameters_filename))
		return int(StepStatus.Fail)

	result = None
	procedure = alignStep(SequenceObj, alignment_parameters, result)
	run_status = procedure.run()
	
	# check (alignment_results is False):

	Assembly_SN = alignment_parameters['Assembly_SN'] 
	results_filename = "..\\Data\\" + Assembly_SN + "\\temp_alignment_results.json"
	alignment_results = LoadJsonFileOrderedDict(results_filename)
	alignment_results[SequenceObj.StepName] = procedure.results

	if save_pretty_json(alignment_results, results_filename):
		tfile = "..\\Data\\" + Assembly_SN + "\\test_result.json"
		shutil.copyfile(results_filename, tfile)

	return int(run_status)

def update_alignment_parameter(SequenceObj, key, value):
	# load the alignment parameters file
	parameters_filename = os.path.join(SequenceObj.RootPath, 'Sequences', SequenceObj.ProcessSequenceName + '.cfg')
	if os.path.exists(parameters_filename):
		with open(parameters_filename, 'r') as f:
			alignment_parameters = json.load(f, object_pairs_hook=OrderedDict)
	else:
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Could not find alignment config file at %s'.format(parameters_filename))
		return 0
	
	alignment_parameters[key] = value

	# save the alignment results
	# with open(parameters_filename, 'w') as outfile:
	# 	json.dump(output, alignment_results, indent=2 , sort_keys=True)

	if save_pretty_json(alignment_parameters, parameters_filename):
		return True
	else:
		return False

def save_pretty_json(variable, filename):
	#combines arrays into one line to make json files more human-readable and saves the variable to the filename

	#terrible fix for json floating point output not rounding correctly
	original_float_repr = json.encoder.FLOAT_REPR
	json.encoder.FLOAT_REPR = lambda o: format(o,'.4f')

	# create json string
	output_string = json.dumps(variable, indent=2 , sort_keys=False)

	#put the FLOAT_REPR back the way it was
	json.encoder.FLOAT_REPR = original_float_repr

	# find the arrays by splitting by square brackets
	split_output_string = re.split(r'\[|\]',output_string)
	output_string = ''
	# reassemble string, but removing whitepace and newline chars inside square brackets
	for i in range(len(split_output_string)):
		# odd numbered elements of the array will be between square brackets because that is how JSON files work
		if i % 2 == 0:
			output_string += split_output_string[i]
		else:
			output_string += '[' + re.sub(r'[\s\n]','',split_output_string[i]) + ']'

	with open(filename, 'w+') as f:
		f.write(output_string)

	f.close()
	# LogHelper.Log('save_pretty_json', LogEventSeverity.Warning, 'Save alignement_results to ' + output_string )
	return True


class StepBase(MethodBase):
	def __init__(self, SequenceObj, parameters, results=None):
		self.SequenceObj = SequenceObj
		# self.parameters = parameters
		# self.results = results
		msg = "Step : " +  type(self).__name__ + "\n" + self.__doc__
		Utility.ShowProcessTextOnMainUI(msg)    
		super(StepBase,self).__init__(parameters, results)

	def run(self):
		self.ConsoleLog(LogEventSeverity.Trace, self.__doc__)
		# Each step could have many different parameters which can be redefined in the sequence configuration.
		ret = StepStatus.Success
		typeName = type(self).__name__
		# Parameters can be updated using step method name or sequence step name.
		if typeName in self.parameters:
			typeParameters = self.parameters[typeName]
			self.ParameterUpdate(typeParameters)
		if self.SequenceObj.StepName in self.parameters:
			parameters = self.parameters[self.SequenceObj.StepName]
			self.ParameterUpdate(parameters)
		try:
			ret = self.runStep()
		except Exception as e:
			LogHelper.Log(typeName, LogEventSeverity.Warning, str(e))
			return StepStatus.Fail
		return ret

	def runStep(self):
		return StepStatus.Success
	
	def Confirm(self, msg):
		return LogHelper.AskContinue(msg)

	def VoiceConfirm(self, msg):
		return LogHelper.VoiceConfirmation(msg)

	@property
	def Results(self):
		return self.results


class StepInit(StepBase):
	"""Setup default."""
	def __init__(self, SequenceObj, parameters, results=None):
		""" Initialization"""
		super(StepInit,self).__init__(SequenceObj, parameters, results)
		self.switch = OpticalSwitchDevice('JGRSwitch')
		self.FAUstage = MotionDevice('Gantry')
		self.goni = MotionDevice('Goni')


	def runStep(self):
		self.logTrace = False
		self.parameters, self.results = GetAssemblyParameterAndResults(self.SequenceObj, self.parameters)
		self.results['Start_Time'] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
		self.results['Operator'] = UserManager.CurrentUser.Name
		self.results['Software_Version'] = Utility.GetApplicationVersion()

		self.goni.EnableAxis("U", True)
		self.goni.EnableAxis("V", True)
		self.goni.EnableAxis("W", True)
		self.FAUstage.EnableAxis("X", True)
		self.FAUstage.EnableAxis("Y", True)
		self.FAUstage.EnableAxis("Z", True)

		self.goni.ActivateState("scanInit")
		return StepStatus.Success

class StepLoadDie(StepBase):
	"""Load Die."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepLoadDie,self).__init__(SequenceObj, parameters, results)
		self.FAUstage = DeviceBase('Gantry')
		self.Diestage = DeviceBase('Goni')
		self.DieHolder = IODevice('VacuumControl', 'DieHolder')
		self.CameraStage = MotionDevice("CameraStages")
		self.Lighting = DeviceBase('IOControl')

	def runStep(self):
		self.ConsoleLog(LogEventSeverity.Trace, 'runStep')
		self.DieHolder.Off()
		self.FAUstage.ActivateState("Load")
		self.Diestage.ActivateState("scanInit")
		if VoiceConfirm("Please place tray on work holder? ") == False:
			return StepStatus.Stop
		if VoiceConfirm("Please place Die in holder? ") == False:
			return StepStatus.Stop
		self.Lighting.ActivateState("right_edge")
		self.FAUstage.ActivateState("scanInit")
		self.CameraStage.ActivateState("Die_edge")
		if VoiceConfirm("Check if Die in position?") == False:
			return StepStatus.Stop
		self.DieHolder.On()
		return StepStatus.Success

class StepLaserAndFauPower(StepBase):
	"""Laser power output at FAU"""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepLaserAndFauPower,self).__init__(SequenceObj, parameters, results)
		self.switch = OpticalSwitchDevice('JGRSwitch')

	def runStep(self):
		self.switch.SetClosePoints(1, 6)
		return StepStatus.Success

class StepLoadFAU(StepBase):
	"""Load FAU."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepLoadFAU,self).__init__(SequenceObj, parameters, results)
		self.FAUstage = DeviceBase('Gantry')
		self.FAUGripper = IODevice('PneumaticControl', 'FAUGripper')
		self.FAUHolder = IODevice('VacuumControl', 'FAUHolder')

	def runStep(self):
		self.ConsoleLog(LogEventSeverity.Trace, 'runStep')
		self.FAUHolder.Off()
		self.FAUGripper.Off()
		self.FAUstage.ActivateState("Load")
		if VoiceConfirm("Load F A U Ready?") == False:
			return StepStatus.Stop
		self.FAUHolder.On()
		if VoiceConfirm("F A U in place?") == False:
			return StepStatus.Stop
		self.FAUstage.ActivateState("FAU_holder")
		if VoiceConfirm("Load F A U Ready?") == False:
			return StepStatus.Stop
		self.FAUGripper.On()
		sleep(1)
		self.FAUHolder.Off()
		sleep(2)
		self.FAUstage.ActivateState("scanInit")
		return StepStatus.Success

class StepCheckProbe(StepBase):
	"""Setup probe."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepCheckProbe,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		return StepStatus.Success

class StepSetFirstLight(StepBase):
	"""Move FAU to first light posuition."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepSetFirstLight,self).__init__(SequenceObj, parameters, results)
		self.FAUstage = MotionDevice('Gantry')
		self.goni = MotionDevice('Goni')
		self.Lighting = DeviceBase('IOControl')
		self.CameraStage = MotionDevice("CameraStages")
		self.InitEpoxyGap = 0.25
		self.right_to_left_shift = 10.375
		self.right_to_center_shift = 2.9454
		self.targetAxes = ["Y", "Z"]

	def runStep(self):
		self.FAUstage.speed = Motion.AxisMotionSpeeds.Slow
		if Confirm("Move FAU to epoxy position?") == False:
			return StepStatus.Stop
		self.FAUstage.MoveAxisRelative("X", -self.right_to_center_shift)
		self.Lighting.ActivateState("right_edge")
		self.CameraStage.ActivateState("Die_edge")
		# Right side vision adjustment
		parameters = self.parameters["FAU_Right_Edge_Vision_parameters"]
		fau_visiontask = MachineVisionTask(parameters)
		fau_visiontask.run()
		parameters = self.parameters["Die_Right_Edge_Vision_parameters"]
		die_visiontask = MachineVisionTask(parameters)
		die_visiontask.run()

		# Move FAU 250um from Die location. 
		x_dist = (die_visiontask.X - fau_visiontask.X) + self.InitEpoxyGap
		self.FAUstage.MoveAxisRelative(self.targetAxes[0], x_dist)

		dist = (die_visiontask.Y - fau_visiontask.Y)
		pitch_angle = (fau_visiontask.Angle - die_visiontask.Angle)
		self.FAUstage.MoveAxisRelative(self.targetAxes[1], dist)
		self.goni.MoveAxisRelative("V", pitch_angle)

		if Confirm("Does right edge look ok?") == False:
			return StepStatus.Stop
		self.FAUstage.MoveAxisRelative("X", self.right_to_left_shift)

		# Left side vision adjustment
		parameters = self.parameters["FAU_Left_Edge_Vision_parameters"]
		fau_visiontask = MachineVisionTask(parameters)
		fau_visiontask.run()
		parameters = self.parameters["Die_Left_Edge_Vision_parameters"]
		die_visiontask = MachineVisionTask(parameters)
		die_visiontask.run()

		x_diff = fau_visiontask.X - die_visiontask.X - self.InitEpoxyGap
		yaw_angle = Utility.RadianToDegree(x_diff/12.0) 
		self.goni.MoveAxisRelative("W", yaw_angle)

		dist = (die_visiontask.Y - fau_visiontask.Y)
		roll_angle = Utility.RadianToDegree(dist/12.0) 
		self.goni.MoveAxisRelative("U", roll_angle)

		if Confirm("Does left edge looks ok?") == False:
			return StepStatus.Stop
		shift = self.right_to_center_shift - self.right_to_left_shift
		self.FAUstage.MoveAxisRelative("X", shift)
		if Confirm("Does F A U at center?") == False:
			return StepStatus.Stop
		return StepStatus.Success

class StepSnapDieText(StepBase):
	"""Take snapshot of die text image."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepSnapDieText,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		return StepStatus.Success

class StepFindFirstLight(StepBase):
	"""Find first light."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepFindFirstLight,self).__init__(SequenceObj, parameters, results)
		self.AeroBasicTaskName = "SpiralFine"

	def runStep(self):
		task = AeroBasicTask(self.AeroBasicTaskName)
		task.run()
		return StepStatus.Success

class StepDryBalanceAlign(StepBase):
	"""Dry balance alignment."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepDryBalanceAlign,self).__init__(SequenceObj, parameters, results)
		self.FAUstage = DeviceBase('Gantry')
		self.Lighting = DeviceBase('IOControl')
		self.CameraStage = MotionDevice("CameraStages")

	def runStep(self):
		self.FAUstage.ActivateState("right_edge", SafeSequence=False)
		self.Lighting.ActivateState("right_edge")
		self.CameraStage.ActivateState("Die_edge")
		if Confirm("Does right edge look ok?") == False:
			return StepStatus.Stop
		self.FAUstage.ActivateState("left_edge", SafeSequence=False)
		self.Lighting.ActivateState("left_edge")
		if Confirm("Does left edge looks ok?") == False:
			return StepStatus.Stop
		self.FAUstage.ActivateState("scanInit", SafeSequence=False)
		if Confirm("Does F A U at center?") == False:
			return StepStatus.Stop
		return StepStatus.Success

class StepApplyEpoxy(StepBase):
	"""Apply epoxy."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepApplyEpoxy,self).__init__(SequenceObj, parameters, results)
		self.bondgap = 0.02
		self.FAUstage = MotionDevice('Gantry')
		self.EpoxyArm = IODevice('PneumaticControl', 'EpoxyWand')
		self.UVArm = IODevice('PneumaticControl', 'MUVWand')
		self.FAUHolder = IODevice('VacuumControl', 'FAUHolder')
		self.UVEpoxy = DeviceBase('UVEpoxyStages')
		self.cameraStage = MotionDevice("CameraStages")
		self.Lighting = DeviceBase('IOControl')

	def runStep(self):
		self.EpoxyArm.Off();
		self.UVEpoxy.ActivateState("Epoxy_up")
		self.EpoxyArm.On();
		if Confirm("Does epoxy at center?") == False:
			return StepStatus.Stop
		self.Lighting.ActivateState("right_edge")
		self.cameraStage.ActivateState("FAU_edge")
		sleep(1)
		self.UVEpoxy.ActivateState("Epoxy")
		if Confirm("Finish apply epoxy?") == False:
			return StepStatus.Stop
		sleep(1)
		self.UVEpoxy.ActivateState("Epoxy_up")
		sleep(1)
		self.EpoxyArm.Off();
		self.UVEpoxy.ActivateState("Home")
		self.FAUstage.MoveAxisRelative('Y', -0.1)
		sleep(1)
		self.FAUstage.MoveAxisRelative('Y', 0.05)
		sleep(1)
		self.FAUstage.MoveAxisRelative('Y', -0.05)
		sleep(1)
		self.FAUstage.MoveAxisRelative('Y', 0.05)
		sleep(1)
		self.FAUstage.MoveAxisRelative('Y', -0.05)
		sleep(1)
		self.FAUstage.MoveAxisRelative('Z', 0.5)
		sleep(1)
		self.FAUstage.MoveAxisRelative('Y', 0.05)
		sleep(1)
		self.FAUstage.MoveAxisRelative('Y', -0.05)
		sleep(1)
		bondgap_pos = self.bondgap - 0.15
		self.FAUstage.MoveAxisRelative('Y', bondgap_pos)

		if Confirm("Move F A U to bond gap position?") == False:
			return StepStatus.Stop
		return StepStatus.Success

class StepWetBalanceAlign(StepBase):
	"""Wet balance alignment."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepWetBalanceAlign,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		return StepStatus.Success

class StepUVCure(StepBase):
	"""UV cure."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepUVCure,self).__init__(SequenceObj, parameters, results)
		self.UVArm = IODevice('PneumaticControl', 'MUVWand')
		self.UVEpoxy = DeviceBase('UVEpoxyStages')
		self.UVSource = UVSourceDevice('UVSource')

	def runStep(self):
		self.UVArm.Off();
		self.UVEpoxy.ActivateState("UVCure")
		self.UVArm.On();
		sleep(5)
		self.UVSource.Start()
		sleep(5)
		self.UVArm.Off();
		sleep(2)
		self.UVEpoxy.ActivateState("Home")
		return StepStatus.Success

class StepTestResults(StepBase):
	"""Measure result."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepTestResults,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		return StepStatus.Success

class StepUnloadBoard(StepBase):
	"""Unload compamnet."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepUnloadBoard,self).__init__(SequenceObj, parameters, results)
		self.FAUGripper = IODevice('PneumaticControl', 'FAUGripper')
		self.FAUstage = DeviceBase('Gantry')
		self.DieHolder = IODevice('VacuumControl', 'DieHolder')

	def runStep(self):
		self.FAUGripper.Off()
		self.DieHolder.Off()
		sleep(2)
		self.FAUstage.ActivateState("Load")
		return StepStatus.Success

class StepFinalize(StepBase):
	"""Save data."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepFinalize,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		return StepStatus.Success

class StepPark(StepBase):
	"""Park Gantry and turn off light."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepPark,self).__init__(SequenceObj, parameters, results)
		self.FAUstage = MotionDevice('Gantry')
		self.goni = MotionDevice('Goni')
		self.Lighting = DeviceBase('IOControl')
		self.right_camera = DeviceBase("RightSideCamera")
		self.left_camera = DeviceBase("LeftSideCamera")
		self.down_camera = DeviceBase("DownCamera")

	def runStep(self):
		self.right_camera.Live(False)
		self.left_camera.Live(False)
		self.down_camera.Live(False)
		self.FAUstage.ActivateState("Park")
		self.Lighting.ActivateState("off")
		self.goni.EnableAxis("U", False)
		sleep(1)
		self.goni.EnableAxis("V", False)
		sleep(1)
		self.goni.EnableAxis("W", False)
		sleep(1)
		self.FAUstage.EnableAxis("X", False)
		sleep(1)
		self.FAUstage.EnableAxis("Y", False)
		sleep(1)
		self.FAUstage.EnableAxis("Z", False)
		return StepStatus.Success


class StepCarmeaCalibration(StepBase):
	"""Save data."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepCarmeaCalibration,self).__init__(SequenceObj, parameters, results)
		self.logTrace = True
		self.width = 0.1
		self.height = 0.1
		self.visionToolFolder = "..\Vision\\GF10\\right_side\\" 
		self.visionTool = 'GF10_FAU_right_side_TB'
		self.targetAxes = ['Y', 'Z']
		self.transformMatrix= "RightSideCameraTransform"

		self.camera = DeviceBase("RightSideCamera")
		self.cameraStage = MotionDevice("CameraStages")
		self.targetStage = MotionDevice('Gantry')
		self.lightControl = DeviceBase("IOControl")
		self.machineVision = DeviceBase("MachineVision")

		self.cameraInitPoistion = "CameraCalibration"
		self.targetInitPoistion = "CameraCalibration"
		self.lightingState = "CameraCalibration"

		self.pointCollection = List[Vision.CalibratePointPair]()

	def RunVisionToolAddPair(self):
		self.camera.Snap()
		tool = os.path.join(self.visionToolFolder, self.visionTool)
		result = self.machineVision.RunVisionTool(tool)
		if result['Result'] != 'Success':
			LogHelper.Log('RunVisionToolAddPair',  LogEventSeverity.Warning, 'Vision tool fail {0}'.format(tool))
			raise Exception('Vision tool error')

		positions = self.targetStage.GetPositions(self.targetAxes)
		pointPair = Vision.CalibratePointPair(result['X'], result['Y'], positions[0], positions[1])
		self.pointCollection.Add(pointPair)

	def MoveTargetRelative(self, rx, ry):
		self.targetStage.MoveAxesRelative(self.targetAxes, [rx, ry])

	def RunCalibrateAtPositionRelative(self, rx, ry):
		self.targetStage.MoveAxesRelative(self.targetAxes, [rx, ry])
		sleep(1)
		self.RunVisionTool()
		self.targetStage.MoveAxesRelative(self.targetAxes, [-rx, -ry])
		sleep(1)
		
	def runStep(self):
		self.camera.Live(True)
		self.cameraStage.ActivateState(self.cameraInitPoistion)
		self.targetStage.ActivateState(self.targetInitPoistion, SafeSequence=False)
		self.lightControl.ActivateState(self.lightingState)

		self.RunVisionToolAddPair()
		self.MoveTargetRelative(self.width, 0)
		self.RunVisionToolAddPair()
		self.MoveTargetRelative(0, self.height)
		self.RunVisionToolAddPair()
		self.MoveTargetRelative(-self.width, 0)
		self.RunVisionToolAddPair()

		self.machineVision.LoadAllTransforms()
		self.machineVision.AddTransform(self.transformMatrix, self.pointCollection)
		self.machineVision.SaveAllTransforms()
		self.camera.Live(False)
		return StepStatus.Success

