import os.path
import json

def step_manager(SequenceObj, step):
	filename = os.path.join(SequenceObj.TestResults.OutputDestinationConfiguration, 'temp_alignment_results.json')
	with open(filename, 'r') as outfile:
		alignment_results = json.load(outfile)
	# alignment_results = load_alignment_results(SequenceObj)


	alignment_metrics = load_alignment_results(SequenceObj)

	#import(file_name) as f
	#exec('import ' + file_name + ' as f')
	is_successful, alignment_results = step(SequenceObj, alignment_metrics, alignment_results)


	if not save_alignment_results(SequenceObj, alignment_results):
		LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed save alignment results!')
		return 0
	return 1