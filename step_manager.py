clr.AddReferenceToFile('Utility.dll')
from Utility import *
import os.path
import json



def step_manager(SequenceObj, step):
	# This method loads alignment_parameters and alignment_results files

	# load the alignment parameters file
	parameters_filename = os.path.join(SequenceObj.TestResults.RootPath, 'Sequences', SequenceObj.ProcessSequenceName + '.cfg')
	if os.path.exists(parameters_filename):
		with open(parameters_filename, 'r') as f:
			alignment_parameters = json.load(f)
	else:
		Utility.LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Could not find alignment config file at %s'.format(parameters_filename))
		return 0

	# load the alignment results file if we're not starting a new sequence, otherwise create a new dictionary
	results_filename = os.path.join(SequenceObj.TestResults.RootPath, 'Data', 'temp_alignment_results.json') # store the temporary results file here
	if step != 'Initialize':
		with open(results_filename, 'r') as f:
			alignment_results = json.load(f)
	else:
		alignment_results = {'_file format':'JSON'}

	filename = os.path.basename(SequenceObj.scriptFilePath) # just get the filename
	filename = filename.split('.')[0] # get rid of the extension

	#import(file_name) as f
	exec('import ' + filename + ' as f2')
	alignment_results = exec('f2.' + step + '(SequenceObj, alignment_parameters, alignment_results)')

	if (alignment_results == 0) or (alignment_results is False):
		return 0

	# save the alignment results
	# with open(results_filename, 'w') as outfile:
	# 	json.dump(output, alignment_results, indent=2 , sort_keys=True)
	if save_pretty_json(alignment_results, results_filename):
		return 1
	else:
		return 0

def update_alignment_parameter(SequenceObj, key, value):
	# load the alignment parameters file
	parameters_filename = os.path.join(SequenceObj.TestResults.RootPath, 'Sequences', SequenceObj.ProcessSequenceName + '.cfg')
	if os.path.exists(parameters_filename):
		with open(parameters_filename, 'r') as f:
			alignment_parameters = json.load(f)
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

	# create json string
	output_string = json.dumps(variable, indent=2 , sort_keys=True)

	# find the arrays by splitting by square brackets
	split_output_string = re.split('\[|\]',output_string)
	output_string = ''
	# reassemble string, but removing whitepace and newline chars inside square brackets
	for i in range(len(split_output_string)):
		# odd numbered elements of the array will be between square brackets because that is how JSON files work
		if i % 2 == 0:
			output_string += split_output_string[i]
		else:
			output_string += '[' + re.sub('[\s\n]','',split_output_string[i]) + ']'

	with open('filename', 'w') as f:
		f.write(output_string)

	return True




