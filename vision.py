'''
Created on Feb 2, 2021

@author: dingchen
'''
from AlignerUtil import *

class Vision(object):
	def __init__(self, toolname, camera, preset):
		self.toolname = toolname
		self.preset = preset
		self.camera = camera
		self.X = None
		self.Y = None
		self.Angle = None

	def run(self):
		self.camera.setup()
		selpf.result = MachineVision.RunVisionTool(toolname)
		if self.result['Result'] != 'Success': # check result
			LogHelper.Log("Vision", LogEventSeverity.Warning, 'Failed to locate position.')
			return False
		self.X = self.result["X"]
		self.Y = self.result["Y"]
		self.Angle = self.result["Angle"]
		return True

class Camera(object):

	def __init__(self, camera, stage, exposure, ringLight, coaxialLight, backLight):
		self.camera = camera
		self.exposure = exposure
		self.stage = stage
		self.ringLight = ringLight
		self.coaxialLight = coaxialLight
		self.backLight = backLight

	def setup(self):
		self.stage.ActivateState()
		self.ringLight.ActivateState()
		self.coaxialLight.ActivateState()
		self.backLight.ActivateState()
		self.camera.SetExposureTime(self.exposure)
		sleep(0.5)
		self.camera.snap()
		self.camera.Live(True)


class Stage(object):

	def __init__(self, stage, position):
		self.stage = stage
		self.position = position

	def ActivateState(self):
		self.stage.GetHardwareStateTree().ActivateState(self.position)

def setFirstLightPosition():

	downCamera_position = Stage(DownCameraStages, )
	downCamera = Camera(DownCamera,)
