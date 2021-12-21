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
		LogHelper.Log('DeviceBase', LogEventSeverity.Alert, deviceName)
		
	def __getattr__(self, attr):	
		if hasattr(self.hardware, attr):
			return getattr(self.hardware, attr)
		raise AttributeError("'%s' has no attribute '%s'" % (self.deviceName, attr))

	def ActivateState(self, state):
		self.hardware.GetHardwareStateTree().ActivateState(state)

		
class IODevice(DeviceBase):
	def __init__(self, deviceName, IOName):
		self.IOName = IOName
		super(IODevice, self).__init__(deviceName)

	def On(self):
		self.hardware.SetOutputValue(self.IOName, True)

	def Off(self):
		self.hardware.SetOutputValue(self.IOName, False)


class MotionDevice(DeviceBase):
	def __init__(self, deviceName):
		super(MotionDevice, self).__init__(deviceName)

	def Profile(self):
		pass


class MeterDevice(DeviceBase):
	def __init__(self, deviceName):
		super(IODevice, self).__init__(deviceName)
		self.power = 0.0
		self.unit = ""
		self.dev = 0.0
		self.min = 0.0
		self.max = 0.0

	def ReadPower(self, channel):
		self.channel = channel
		return self.power

	def SwitchChannel(self, channel):
		self.channel = channel

	def ReadPowerWithStatistic(self, channel, n_measurements=10):
		measurements = []
		self.channel = channel
		for i in range(n_measurements):
		    measurements.append(self.ReadPower(channel))
		    sleep(.01)
	
		mean = sum(measurements) / len(measurements)
		if n_measurements > 1:
		    stdev = (sum(map(lambda x: (x - mean) ** 2, measurements)) / (n_measurements - 1)) ** 0.5
		else:
			stdev = None
		self.power = mean
		self.dev = stdev
		self.min = min(measurements)
		self.max = max(measurements)
		measurements.sort()
		l = n_measurements/2
		self.median = (measurements[l] + measurements[l-1])/2
		return (self.power, self.median, self.dev, self.min, self.max)


if __name__ == "__main__":
	pass