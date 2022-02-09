import clr
clr.AddReferenceToFile('Utility.dll')
from Utility import *
import os.path
import json
import re
from time import sleep
from collections import *
from AlignerUtil import GetAndCheckUserInput
from AlignerUtil import GetAssemblyParameterAndResults
import shutil
from System import DateTime
from System.Collections.Generic import List
from datetime import datetime

from HAL import Vision
from HAL import Motion
from HAL import HardwareFactory
from alignerCommon import *

def step_manager(SequenceObj, alignStep):
	# This method loads alignment_parameters and alignment_results files

	# load the alignment parameters file
	parameters_filename = os.path.join(SequenceObj.RootPath, 'Sequences', SequenceObj.ProcessSequenceName + '.cfg')
	if os.path.exists(parameters_filename):
		with open(parameters_filename, 'r') as f:
			alignment_parameters = json.load(f, object_pairs_hook=OrderedDict)
	else:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Could not find alignment config file at {}'.format(parameters_filename))
		return 0

	result = None
	procedure = alignStep(SequenceObj, alignment_parameters, result)
	procedure.run()
	
	# check (alignment_results is False):

	Assembly_SN = alignment_parameters['Assembly_SN'] 
	results_filename = "..\\Data\\" + Assembly_SN + "\\temp_alignment_results.json"
	alignment_results = LoadJsonFileOrderedDict(results_filename)
	alignment_results[SequenceObj.StepName] = procedure.results

	if save_pretty_json(alignment_results, results_filename):
		tfile = "..\\Data\\" + Assembly_SN + "\\test_result.json"
		shutil.copyfile(results_filename, tfile)
		return 1
	else:
		return 0

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
		typeName = type(self).__name__
		# Parameters can be updated using step method name or sequence step name.
		if typeName in self.parameters:
			typeParameters = self.parameters[typeName]
			self.ParameterUpdate(typeParameters)
		if self.SequenceObj.StepName in self.parameters:
			parameters = self.parameters[self.SequenceObj.StepName]
			self.ParameterUpdate(parameters)
		self.runStep()

	def runStep(self):
		pass
	
	def Confirm(self, msg):
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
		self.camera = DeviceBase('DownCamera')


	def runStep(self):
		self.logTrace = True
		self.parameters, self.results = GetAssemblyParameterAndResults(self.SequenceObj, self.parameters)
		self.results['Start_Time'] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
		self.results['Operator'] = UserManager.CurrentUser.Name
		self.results['Software_Version'] = Utility.GetApplicationVersion()

		# current_position = list(self.FAU_xyz_stage.GetAxesPositions())
		# LogHelper.Log('Initialize', LogEventSeverity.Alert, 'current_position {0:.3f} {1:.3f} {2:.3f}.'.format(current_position[0], current_position[1], current_position[2]))

class StepLaserAndFauPower(StepBase):
	"""Laser power output at FAU"""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepLaserAndFauPower,self).__init__(SequenceObj, parameters, results)
		self.switch = OpticalSwitchDevice('JGRSwitch')

	def runStep(self):
		self.switch.SetClosePoints(1, 6)

class StepLoadComponent(StepBase):
	"""Load Compamnets."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepLoadComponent,self).__init__(SequenceObj, parameters, results)
		self.FAUstage = DeviceBase('Gantry')
		self.FAUGripper = IODevice('PneumaticControl', 'FAUGripper')
		self.FAUHolder = IODevice('VacuumControl', 'FAUHolder')
		self.DieHolder = IODevice('VacuumControl', 'DieHolder')
		self.switch = OpticalSwitchDevice('JGRSwitch')

	def runStep(self):
		self.ConsoleLog(LogEventSeverity.Trace, 'runStep')
		self.FAUHolder.Off()
		self.DieHolder.Off()
		self.FAUGripper.Off()
		self.FAUstage.ActivateState("Load")
		if self.Confirm("Please place Die in holder? \nClick Yes when ready , No to abort.") == False:
			return
		self.FAUstage.ActivateState("die_pos")
		if self.Confirm("Check if Die in position.\nClick Yes when ready , No to abort.") == False:
			return
		self.DieHolder.On()
		self.FAUstage.ActivateState("Load")
		if self.Confirm("Load F A U Ready? \nClick Yes to hold F A U in place, No to abort.") == False:
			return
		self.FAUHolder.On()
		if self.Confirm("F A U in place? \nClick Yes to continue, No to abort.") == False:
			return
		self.FAUstage.ActivateState("FAU_holder")
		if self.Confirm("Load F A U Ready? \nClick Yes to continue, No to abort.") == False:
			return
		self.FAUGripper.On()
		sleep(2)
		self.FAUHolder.Off()
		sleep(2)
		self.FAUstage.ActivateState("scanInit")

class StepCheckProbe(StepBase):
	"""Setup probe."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepCheckProbe,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepSetFirstLight(StepBase):
	"""Move FAU to first light posuition."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepSetFirstLight,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepSnapDieText(StepBase):
	"""Take snapshot of die text image."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepSnapDieText,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepFindFirstLight(StepBase):
	"""Find first light."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepFindFirstLight,self).__init__(SequenceObj, parameters, results)
		self.AeroBasicTaskName = "SpiralFine"

	def runStep(self):
		task = AeroBasicTask(self.AeroBasicTaskName)
		task.run()

class StepDryBalanceAlign(StepBase):
	"""Dry balance alignment."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepDryBalanceAlign,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepApplyEpoxy(StepBase):
	"""Apply epoxy."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepApplyEpoxy,self).__init__(SequenceObj, parameters, results)
		self.FAUstage = DeviceBase('Gantry')
		self.EpoxyArm = IODevice('PneumaticControl', 'EpoxyWand')
		self.UVArm = IODevice('PneumaticControl', 'MUVWand')
		self.FAUHolder = IODevice('VacuumControl', 'FAUHolder')
		self.UVEpoxy = DeviceBase('UVEpoxyStages')

	def runStep(self):
		self.EpoxyArm.Off();
		self.UVEpoxy.ActivateState("Epoxy_up")
		self.EpoxyArm.On();
		sleep(1)
		self.UVEpoxy.ActivateState("Epoxy")
		sleep(10)
		self.UVEpoxy.ActivateState("Epoxy_up")
		self.EpoxyArm.Off();
		self.UVEpoxy.ActivateState("Home")
		pass

class StepWetBalanceAlign(StepBase):
	"""Wet balance alignment."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepWetBalanceAlign,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

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

class StepTestResults(StepBase):
	"""Measure result."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepTestResults,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepUnloadBoard(StepBase):
	"""Unload compamnet."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepUnloadBoard,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepFinalize(StepBase):
	"""Save data."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepFinalize,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepCarmeaCalibration(StepBase):
	"""Save data."""
	def __init__(self, SequenceObj, parameters, results=None):
		super(StepCarmeaCalibration,self).__init__(SequenceObj, parameters, results)
		self.width = 0.1
		self.height = 0.1
		self.visionToolFolder = "..\Vision\\GF10\\right_side\\" 
		self.visionTool = 'GF10_FAU_right_side_TB'
		self.targetAxes = ['Y', 'Z']
		self.pointCollection = List[Vision.CalibratePointPair]()
		self.transformMatrix= "RightSideCameraTransform"

		self.camera = DeviceBase("RightSideCamera")
		self.cameraStage = MotionDevice("CameraStages")
		self.targetStage = MotionDevice('Gantry')
		self.lightControl = DeviceBase("IOControl")
		self.machineVision = DeviceBase("MachineVision")

	def RunVisionToolAddPair(self):
		self.camera.Snap()
		tool = os.path.join(self.visionToolFolder, self.visionTool)
		result = self.machineVision.RunVisionTool(tool)
		if result['Result'] != 'Success':
		    LogHelper.Log('RunVisionToolAddPair',  LogEventSeverity.Warning, 'Vision tool fail {0}'.format(tool))
		    return 0

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
		self.cameraStage.ActivateState('CameraCalibration')
		self.targetStage.ActivateState('RightCameraCalibration')
		self.lightControl.ActivateState('CameraCalibration')

		self.RunVisionToolAddPair()
		self.MoveTargetRelative(self.width, 0)
		self.RunVisionToolAddPair()
		self.MoveTargetRelative(0, self.height)
		self.RunVisionToolAddPair()
		self.MoveTargetRelative(-self.width, 0)
		self.RunVisionToolAddPair()

		self.machineVision.AddTransform(self.transformMatrix, self.pointCollection)
		self.camera.Live(False)

