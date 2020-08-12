import re

# Retrieve_line = '    var = TestResults.RetrieveTestResult( \'Assembly_SN\')++'
# add_line =  'TestResults.AddTestResult(\'Outer_Channels_Width\', round(pow(pow(end.Item1 - start.Item1, 2) + pow(end.Item2 - start.Item2, 2),0.5), 5))'

RetrieveTestResult_pattern = re.compile('TestResults.RetrieveTestResult\((.+)\)')
AddTestResult_pattern = re.compile('TestResults.AddTestResult\((.+?),(.+)\)')

input_filename = 'DieLevelFiberToDieAttachProcessSteps.py.bak'
output_filename = 'DieLevelFiberToDieAttachProcessSteps.py'


'''
match = RetrieveTestResult_pattern.search(Retrieve_line) 
print(match)
# print(match.group(0))
# print(match.group(1).strip())

line = Retrieve_line
newline = 'alignment_results[' + match.group(1).strip() + ']' 
if match.span(0)[0] > 0:
	newline = line[0:match.span(0)[0]] + newline
if match.span(0)[1] < len(line):
	print(len(line))
	newline = newline + line[match.span(0)[1]:]
print('-->')
print(newline)




match = AddTestResult_pattern.search(add_line) 
print(match)
print(match.group(1))
print(match.group(2))

line = add_line
newline = 'alignment_results[' + match.group(1).strip() + '] = ' + match.group(2).strip()
if match.span(0)[0] < 0:
	newline = line[0:match.span(0)[0]] + newline
if match.span(0)[1] > len(line):
	print(len(line))
	newline = newline + line[match.span(0)[1]:]
print('-->')
print(newline)
'''
temp_file = ''
output_file = ''
with open(input_filename, 'r') as f:
	for line in f:
		match = RetrieveTestResult_pattern.search(line) 
		if match is not None:
			newline = 'alignment_results[' + match.group(1).strip() + ']'

			if match.span(0)[0] > 0:
				newline = line[0:match.span(0)[0]] + newline
			if match.span(0)[1] < len(line):
				newline = newline + line[match.span(0)[1]:]
		else:
			newline = line
		
		temp_file += newline.rstrip() + '\n'

	for line in temp_file.splitlines():
		match = AddTestResult_pattern.search(line) 
		if match is not None:
			newline = 'alignment_results[' + match.group(1).strip() + '] = ' + match.group(2).strip()

			if match.span(0)[0] > 0:
				newline = line[0:match.span(0)[0]] + newline
			if match.span(0)[1] < len(line):
				newline = newline + line[match.span(0)[1]:]
		else:
			newline = line
		
		output_file += newline.rstrip() + '\n'

	
with open(output_filename, 'w') as f:
	f.write(output_file)

