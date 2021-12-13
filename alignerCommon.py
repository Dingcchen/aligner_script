import clr
from collections import OrderedDict
import os
import json
clr.AddReferenceToFile('HAL.dll')
from HAL import HardwareFactory
clr.AddReferenceToFile('Utility.dll')
from Utility import *

def LoadJsonFileOrderedDict(jsonfile):
	if(isinstance(jsonfile, str)):
		filename = os.path.join(os.getcwd(), jsonfile)
		if os.path.exists(filename):
			with open(filename, 'r') as f:
				return json.load(f, object_pairs_hook=OrderedDict)
	elif(isinstance(jsonfile, OrderedDict)):
		return jsonfile
	return OrderedDict()

class MethodBase(object):
	def __init__(self, parameters=None, results=None):
		self.parameters = LoadJsonFileOrderedDict(parameters)
		self.results = LoadJsonFileOrderedDict(results)


class DeviceBase(object):
	def __init__(self, deviceName):
		self.deviceName = deviceName
		self.hardware = HardwareFactory.Instance.GetHardwareByName(deviceName)
		
	def __getattr__(self, attr):	
		if hasattr(self.hardware, attr):
			return getattr(self.hardware, attr)
	 	raise AttributeError("'%s' has no attribute '%s'" % (self.deviceName, attr))

	def ActivateState(self, state):
		self.hardware.GetHardwareStateTree().ActivateState(state)
		
if __name__ == "__main__":
	pass