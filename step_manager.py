import clr
clr.AddReferenceToFile('Utility.dll')
from Utility import *
import os.path
import json
import re
from collections import *
from AlignerUtil import GetAndCheckUserInput
from AlignerUtil import GetAssemblyParameterAndResults
import shutil
from System import DateTime
from datetime import datetime

from HAL import Motion
from HAL import HardwareFactory

def step_manager(SequenceObj, alignStep):
	# This method loads alignment_parameters and alignment_results files

	# load the alignment parameters file
	alignment_results = OrderedDict()
	parameters_filename = os.path.join(SequenceObj.RootPath, 'Sequences', SequenceObj.ProcessSequenceName + '.cfg')
	if os.path.exists(parameters_filename):
		with open(parameters_filename, 'r') as f:
			alignment_parameters = json.load(f, object_pairs_hook=OrderedDict)
	else:
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Could not find alignment config file at {}'.format(parameters_filename))
		return 0

	Assembly_SN = alignment_parameters['Assembly_SN'] 
	if SequenceObj.StepName == 'Initialize':
		alignment_parameters, alignment_results = GetAssemblyParameterAndResults(SequenceObj, alignment_parameters)
	else:
		results_filename = "..\\Data\\" + Assembly_SN + "\\temp_alignment_results.json"
		with open(results_filename, 'r') as f:
			alignment_results = json.load(f, object_pairs_hook=OrderedDict)

	filename = os.path.basename(SequenceObj.ScriptFilePath) # just get the filename
	filename = filename.split('.')[0] # get rid of the extension

	LogHelper.Log('step_manager', LogEventSeverity.Alert, 'run')
	procedure = alignStep(SequenceObj, alignment_parameters, alignment_results)
	procedure.run()
	alignment_results[SequenceObj.StepName] = procedure.results

	# or (alignment_results is False):
	if (alignment_results == 0) :
		return 0

	Assembly_SN = alignment_parameters['Assembly_SN'] 
	results_filename = "..\\Data\\" + Assembly_SN + "\\temp_alignment_results.json"
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



class StepBase(object):
	def __init__(self, SequenceObj, parameters, results):
		self.SequenceObj = SequenceObj
		self.parameters = parameters
		self.results = OrderedDict()
		self.DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
		self.LeftSideCamera = HardwareFactory.Instance.GetHardwareByName('LeftSideCamera')
		self.RightSideCamera = HardwareFactory.Instance.GetHardwareByName('RightSideCamera')
		self.IOController = HardwareFactory.Instance.GetHardwareByName('IOControl')
		self.SGRX8Switch = HardwareFactory.Instance.GetHardwareByName('JGRSwitch')
		self.VacuumControl = HardwareFactory.Instance.GetHardwareByName('VacuumControl')
		self.meter = None
		self.FAU_xyz_stage = HardwareFactory.Instance.GetHardwareByName('Gantry')
		self.MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
		self.title = self.SequenceObj.StepName

	def run(self):
		#Show user what's going on.
		msg = "Step : " +  type(self).__name__ + "\n" + self.__doc__
		Utility.ShowProcessTextOnMainUI(msg)    
		self.runStep()

	def runStep(self):
		pass

class StepInit(StepBase):
	"""Setup default."""
	def __init__(self, SequenceObj, parameters, results):
		LogHelper.Log('InitStep', LogEventSeverity.Alert, 'run')
		super(StepInit,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		self.SequenceObj.TestResults.AddTestResult('Start_Time', DateTime.Now)
		self.results['Start_Time'] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
		self.SequenceObj.TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
		self.results['Operator'] = UserManager.CurrentUser.Name
		self.SequenceObj.TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())
		self.results['Software_Version'] = Utility.GetApplicationVersion()
		self.IOController.GetHardwareStateTree().ActivateState('Default')

		current_position = list(self.FAU_xyz_stage.GetAxesPositions())
		LogHelper.Log('Initialize', LogEventSeverity.Alert, 'current_position {0:.3f} {1:.3f} {2:.3f}.'.format(current_position[0], current_position[1], current_position[2]))

class StepLaserAndFauPower(StepBase):
	"""Laser power output at FAU"""
	def __init__(self, SequenceObj, parameters, results):
		super(StepLaserAndFauPower,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepLoadComponent(StepBase):
	"""Load Compamnets."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepLoadComponent,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepCheckProbe(StepBase):
	"""Setup probe."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepCheckProbe,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepSetFirstLight(StepBase):
	"""Move FAU to first light posuition."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepSetFirstLight,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepSnapDieText(StepBase):
	"""Take snapshot of die text image."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepSnapDieText,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepFindFirstLight(StepBase):
	"""Find first light."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepFindFirstLight,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepDryBalanceAlign(StepBase):
	"""Dry balance alignment."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepDryBalanceAlign,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepApplyEpoxy(StepBase):
	"""Apply epoxy."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepApplyEpoxy,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepWetBalanceAlign(StepBase):
	"""Wet balance alignment."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepWetBalanceAlign,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepUVCure(StepBase):
	"""UV cure."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepUVCure,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepTestResults(StepBase):
	"""Measure result."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepTestResults,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepUnloadBoard(StepBase):
	"""Unload compamnet."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepUnloadBoard,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass

class StepFinalize(StepBase):
	"""Save data."""
	def __init__(self, SequenceObj, parameters, results):
		super(StepFinalize,self).__init__(SequenceObj, parameters, results)

	def runStep(self):
		pass



