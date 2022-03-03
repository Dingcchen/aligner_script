import clr
from collections import OrderedDict
import os
import json
from time import sleep
from System import Action
from System import Array
from System import String
from System import ValueTuple
from System.Diagnostics import Stopwatch
clr.AddReferenceToFile('HAL.dll')
from HAL import Motion
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

def Confirm(msg):
    return LogHelper.AskContinue(msg)

def VoiceConfirm(msg):
    return LogHelper.VoiceConfirmation(msg)


class MethodBase(object):
	def __init__(self, parameters=None, results=None):
		self.logTrace = False
		self.parameters = LoadJsonFileOrderedDict(parameters)
		self.results = LoadJsonFileOrderedDict(results)

	def DeviceUpdate(self, devices):
		for device in devices:
			deviceName = devices[device]
			self.ConsoleLog(LogEventSeverity.Trace, device)
			if hasattr(self, device):
				hardware = HardwareFactory.Instance.GetHardwareByName(deviceName)
				LogHelper.Log('device update', LogEventSeverity.Warning, 'Update {0} to {1}'.format(device, deviceName))
				setattr(self, device, hardware)
				
	def ParameterUpdate(self, parameters):
		for k in parameters:
			self.ConsoleLog(LogEventSeverity.Trace, k)
			if k == "devices":
				self.DeviceUpdate(parameters["devices"])
			elif hasattr(self, k):
				setattr(self, k, parameters[k])

	def ConsoleLog(self, severity, msg):
		if not msg:
			return
		EnableLogTrace = LogHelper.EnableLogTrace
		if self.logTrace:
			LogHelper.EnableLogTrace = True
		LogHelper.Log(type(self).__name__, severity, msg)
		if self.logTrace:
			LogHelper.EnableLogTrace = EnableLogTrace
		

class DeviceBase(object):
	def __init__(self, deviceName):
		self.deviceName = deviceName
		self.hardware = HardwareFactory.Instance.GetHardwareByName(deviceName)
		LogHelper.Log('DeviceBase', LogEventSeverity.Alert, deviceName)
		
	def __getattr__(self, attr):	
		if hasattr(self.hardware, attr):
			return getattr(self.hardware, attr)
		raise AttributeError("'%s' has no attribute '%s'" % (self.deviceName, attr))

	def ActivateState(self, state,SafeSequence=True):
		self.hardware.GetHardwareStateTree().ActivateState(state, UseSafeSequence=SafeSequence)

		
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
		self.positions = []
		self.speed = Motion.AxisMotionSpeeds.Normal

	def GetPositions(self, axes=None):
		positions = []
		for x in axes:
			pos = self.hardware.ReadAxisPosition(x)
			positions.append(pos)
		return positions
		"""
		self.positions = list(self.hardware.GetPositions(axes))
		return self.positions
		"""

	def MoveAxesRelative(self, axes, position, WaitForDone=True):
		self.hardware.MoveAxesRelative(Array[String](axes), Array[float](position), self.speed, WaitForDone)

	def MoveAxisRelative(self, axis, Distance, WaitForDone=True):
		self.hardware.MoveAxisRelative(axis, Distance, self.speed, WaitForDone)

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


class OpticalSwitchDevice(DeviceBase):
	def __init__(self, deviceName):
		super(OpticalSwitchDevice, self).__init__(deviceName)
		self.ModuleAChannel = 0
		self.ModuleBChannel = 0
		self.Comment = ""
		self.Title = "Optical switch"

	def Log(self, msg):
		LogHelper.Log(self.Title, LogEventSeverity.Alert, 'switch SGR X8 module 1 to channel {0}.'.format(self.ModuleAChannel))

	def Set(self):
		self.hardware.SetClosePoints(1, self.ModuleAChannel)
		self.Log('switch SGR X8 module 1 to channel {0}.'.format(self.ModuleAChannel))
		self.hardware.SetClosePoints(2, self.ModuleBChannel)
		self.Log('switch SGR X8 module 2 to channel {0}.'.format(self.ModuleBChannel))
		self.Log(self.Comment)

class UVSourceDevice(DeviceBase):
	def __init__(self, deviceName):
		super(UVSourceDevice, self).__init__(deviceName)
		self.profile ="10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF,10:IR=30,20:OFF" 
		self.channels = "1,2"

	def Start(self):
		totaltime = sum(map(lambda x: float(x.split(':')[0]), self.profile.split(',')))
		stopwatch = Stopwatch()
		stopwatch.Start()

		def LogPower(i):
			# create the delegate for the UV cure function
			# UVPowerTracking.Add(Array[float]([round(float(stopwatch.ElapsedMilliseconds) / 1000, 1), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 5), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 5)]))
			Utility.ShowProcessTextOnMainUI('UV cure time ' + str(totaltime - int(stopwatch.ElapsedMilliseconds / 1000)) + ' seconds remaining.')

		self.hardware.StartStepUVExposures(self.profile, self.channels, Action[int](LogPower))

		stopwatch.Stop()


"""
Task and Algorithm
"""

class MachineVisionTask(MethodBase):
	def __init__(self, parameters=None):
		super(MachineVisionTask, self).__init__(parameters)
		self.visionToolFolder = "..\Vision\\storm\\right_side\\" 
		self.visionTool = 'FAU_right_side_TB'
		self.exposure = 20.0
		self.lightingState = "vision_right_edge"
		self.targetInitPoistion = "right_edge"
		self.cameraInitPoistion = "die_edge"
		self.transformMatrix= "RightSideCameraTransform"
		self.parameters = parameters

		# Devices used
		self.camera = DeviceBase("RightSideCamera")
		self.Lighting = DeviceBase('IOControl')
		self.targetStage = MotionDevice("Gantry")
		self.cameraStage = MotionDevice("CameraStages")
		self.machineVision = DeviceBase("MachineVision")

		# Result
		self.success = False
		self.result = None
		self.result_mm = None

	def run(self):
		if self.parameters is not None:
			self.ParameterUpdate(self.parameters)
		self.camera.Live(True)
		self.Lighting.ActivateState(self.lightingState)
		self.camera.SetExposureTime(self.exposure)
		sleep(0.5)
		self.camera.Snap()
		tool = os.path.join(self.visionToolFolder, self.visionTool)
		self.result = self.machineVision.RunVisionTool(tool)
		self.success = (self.result['Result'] == 'Success')
		if self.success:
			x = self.result["X"]
			y = self.result["Y"]
			self.result_mm = self.machineVision.ApplyTransform(self.transformMatrix, ValueTuple[float,float](x, y))
			x = self.result_mm.Item1
			y = self.result_mm.Item2
			angle =  Utility.RadianToDegree(self.result['Angle']) 
			LogHelper.Log('MachineVisionTask',  LogEventSeverity.Warning, 'Vision tool find X {0}, Y {1}, Angle {2}'.format(x, y, angle))
		else:
			LogHelper.Log('MachineVisionTask',  LogEventSeverity.Warning, 'Vision tool fail {0}'.format(self.visionTool))

	@property
	def X(self):
		if self.success:
			return self.result_mm.Item1
		return None

	@property
	def Y(self):
		if self.success:
			return self.result_mm.Item2
		return None

	@property
	def Angle(self):
		if self.success:
			return Utility.RadianToDegree(self.result['Angle']) 
		return None


class SearchTask(MotionDevice):
	def __init__(self, deviceName, taskName):
		super(SearchTask, self).__init__(deviceName)
		self.taskName = taskName
		self.searchSuccess = False

	def Search():
		pass

class AeroBasicTask(SearchTask):
	def __init__(self, taskName):
		super(SearchTask, self).__init__('gantry', taskName)

	def Search(self):
		self.controller.RunAeroBasicTask(self.taskName)
		self.positions = self.GetPositions()


class RollAlignment(MethodBase):
	def __init__(self, searchChannels):
		self.channels = channels
		self.WG2WG_dist_mm = 0.75
		self.top_position = 0.0
		self.bottom_position = 0.0
		self.max_z_difference_um = 0.2 
		self.num_channels = 0
		self.balanced_position = [50.0, 50.0, 50.0]
		self.pitch_offset = []
		self.fau_flip = false




if __name__ == "__main__":
	pass