'''
Created on Feb 2, 2021

@author: dingchen
'''
from AlignerUtil import *

class Transformer(object):
	def __init__(self, transformConfig, x_axis, y_axis, w_axis):
		self.transformConfig = transformConfig
		self._x_axis = x_axis
		self._y_axis = y_axis
		self._w_axis = w_axis

	@property
	def x_axis(self):
		return self._x_axis

	@property
	def y_axis(self):
		return self._y_axis

	@property
	def w_axis(self):
		return self._w_axis

	def transform(self, x, y):
		return MachineVision.ApplyTransform(self.transformConfig, ValueTuple[float,float](x, y))

class Vision(object):
	def __init__(self, toolname, camera, parameters):
		self._toolname = toolname
		self.camera = camera
		self.x = None
		self.y = None
		self.angle = None
		self.x2 = None
		self.y2 = None
		self.angle2 = None
		self.parameters = parameters

	def run(self, transformer):
		self.camera.setup()
		result = MachineVision.RunVisionTool(self.toolname)
		if result['Result'] != 'Success': # check result
			LogHelper.Log("Vision", LogEventSeverity.Warning, 'Failed to locate position {}.'.format(self.toolname))
			return False
		txy = transformer.transform(result["X"], result["Y"])
		angle = Utility.RadianToDegree(result['Angle'])
		LogHelper.Log('Vision', LogEventSeverity.Alert, '{0} (x,y) ({1:.3f}, {2:.3f}) Angle: {3:.3f}'.format(self._toolname, txy.Item1, txy.Item2, angle))
		if not LogHelper.AskContinue('Did the vision system correctly identify the {}?'.format(self._toolname)):
			return False

		self.x = txy.Item1
		self.y = txy.Item2
		self.angle = angle
		if("X2" in result and "Y2" in result and "Angle2" in result):
			txy = transformer.transform(result["X2"], result["Y2"])
			angle = Utility.RadianToDegree(result['Angle2'])
			self.x2 = txy.Item1
			self.y2 = txy.Item2
			self.angle2 = angle
		return True

	@property
	def toolname(self):
		tn = self.parameters[self._toolname]
		if tn is not None:
			return tn
		return self._toolname

	@property
	def X(self):
		return self.x

	@property
	def Y(self):
		return self.y

	@property
	def Angle(self):
		return self.angle

	@property
	def X2(self):
		return self.x2

	@property
	def Y2(self):
		return self.y2

	@property
	def Angle2(self):
		return self.angle2

class Stage(object):

	def __init__(self, stage, position):
		self.stage = stage
		self.position = position

	def ActivateState(self):
		self.stage.GetHardwareStateTree().ActivateState(self.position)

	@property
	def position(self):
		return self._position

	@position.setter
	def position(self, key):
		# nodeValue = self.stage.GetNodeValue(key)
		# if( not nodeValue):
		self._position = key

class DownCameraStage(Stage):
	def __init__(self, position):
		super(DownCameraStage, self).__init__(DownCameraStages, position)

class SideCameraStage(Stage):
	def __init__(self, position):
		super(SideCameraStage, self).__init__(SideCameraStages, position)

class IOControllerStage(Stage):
	def __init__(self, position):
		super(IOControllerStage, self).__init__(IOController, position)

class Camera(object):

	def __init__(self, camera, cameraStage, IOStage, exposure):
		self.camera = camera
		self.cameraStage = cameraStage
		self.IOStage = IOStage
		self.exposure = exposure

	def setup(self):
		if self.cameraStage is not None:
			self.cameraStage.ActivateState()
		self.IOStage.ActivateState()
		self.camera.SetExposureTime(self.exposure)
		sleep(0.5)
		self.camera.Snap()
		self.camera.Live(True)

class DownCameraControl(Camera):
	def __init__(self, stage, exposure = 3):
		cameraStage = DownCameraStage(stage)
		IOStage = IOControllerStage(stage)
		super(DownCameraControl, self).__init__(DownCamera, cameraStage, IOStage, exposure)

class LeftSideCameraControl(Camera):
	def __init__(self, stage, exposure = 3):
		cameraStage = SideCameraStage(stage)
		IOStage = IOControllerStage(stage)
		super(LeftSideCameraControl, self).__init__(LeftSideCamera, cameraStage, IOStage, exposure)

class RightSideCameraControl(Camera):
	def __init__(self, stage, exposure = 3):
		cameraStage = None
		IOStage = IOControllerStage(stage)
		super(RightSideCameraControl, self).__init__(RightSideCamera, cameraStage, IOStage, exposure)

class VisionAlign(object):
	def __init__(self, visionDie, visionFAU, transformer):
		self.visionDie = visionDie
		self.visionFAU = visionFAU
		self.transformer = transformer

	def run(self):
		LogHelper.Log("VisionAlign ", LogEventSeverity.Alert, 'Run vision Die.')
		if self.visionDie.run(self.transformer) is False:
			return False

		LogHelper.Log("VisionAlign ", LogEventSeverity.Alert, 'Run vision FAU.')
		if self.visionFAU.run(self.transformer) is False:
			return False

	def align_X(self, gap=0):
		move_x = self.visionDie.X - self.visionFAU.X + gap
		if not Hexapod.MoveAxisRelative(self.transformer.x_axis, move_x, Motion.AxisMotionSpeeds.Slow, True):
			LogHelper.Log("VisionAlign X", LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
			return False
		sleep(0.2)
		return True

	def align_Y(self, gap=0):
		move_y = self.visionDie.Y - self.visionFAU.Y + gap
		if not Hexapod.MoveAxisRelative(self.transformer.y_axis, move_y, Motion.AxisMotionSpeeds.Slow, True):
			LogHelper.Log("VisionAlign Y", LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
			return False
		sleep(0.2)
		return True

	def align_angle(self, rotate_degree=0):
		move_angle = (self.visionFAU.Angle - self.visionDie.Angle) - rotate_degree
		# adjust the yaw angle
		if not Hexapod.MoveAxisRelative(self.transformer.w_axis, move_angle, Motion.AxisMotionSpeeds.Normal, True):
			return False
		sleep(0.2)
		return True

class VisionDiffAlign(object):
	def __init__(self, visionDiff, transformer):
		self.visionDiff = visionDiff
		self.transformer = transformer

	def run(self):
		LogHelper.Log("VisionDiffAlign ", LogEventSeverity.Alert, 'Run vision Die.')
		if self.visionDiff.run(self.transformer) is False:
			return False

	def align_X(self, gap=0):
		move_x = self.visionDiff.X2 - self.visionDiff.X + gap
		if not Hexapod.MoveAxisRelative(self.transformer.x_axis, move_x, Motion.AxisMotionSpeeds.Slow, True):
			LogHelper.Log("VisionDiffAlign X", LogEventSeverity.Warning, 'Failed to move hexapod in X direction.')
			return False
		sleep(0.2)
		return True

	def align_Y(self, gap=0):
		move_y = self.visionDiff.Y - self.visionDiff.Y + gap
		if not Hexapod.MoveAxisRelative(self.transformer.y_axis, move_y, Motion.AxisMotionSpeeds.Slow, True):
			LogHelper.Log("VisionDiffAlign Y", LogEventSeverity.Warning, 'Failed to move hexapod in Y direction.')
			return False
		sleep(0.2)
		return True

	def align_angle(self, rotate_degree=0):
		move_angle = (self.visionDiff.Angle2 - self.visionDiff.Angle) - rotate_degree
		# adjust the yaw angle
		if not Hexapod.MoveAxisRelative(self.transformer.w_axis, move_angle, Motion.AxisMotionSpeeds.Normal, True):
			return False
		sleep(0.2)
		return True


def VisionAlignTop(parameters, x=0.0, y=0.0, angle=0.0):

	downCamera_DieTop = DownCameraControl('Die_Top')
	vision_DieTop = Vision('DieTopVisionTool', downCamera_DieTop, parameters)

	downCamera_FAUTop = DownCameraControl('FAU_Top')
	vision_FAUTop = Vision('FAUTopVisionTool', downCamera_FAUTop, parameters)

	transformer = Transformer('DownCameraTransform', 'X', 'Y', 'W')
	visionAlign = VisionAlign(vision_DieTop, vision_FAUTop, transformer)

	if visionAlign.run() is False:
		return False

	visionAlign.align_Y(y)
	visionAlign.align_X(x)
	visionAlign.align_angle(rotate_degree=angle+90)
	return True


def VisionAlignSide(parameters, die_stage='Die_Side', fau_stage='FAU_Side', x=0.0, y=0.0, angle=0.0):

	sideCamera_DieSide = LeftSideCameraControl(die_stage, exposure = 1)
	vision_DieSide = Vision('DieSideVisionTool', sideCamera_DieSide, parameters)

	sideCamera_FAUSide = LeftSideCameraControl(fau_stage, exposure = 1)
	vision_FAUSide = Vision('FAUSideVisionTool', sideCamera_FAUSide, parameters)

	transformer = Transformer('LeftSideCameraTransform', 'X', 'Z', 'V')
	visionAlign = VisionAlign(vision_DieSide, vision_FAUSide, transformer)

	if visionAlign.run() is False:
		return False

	visionAlign.align_Y(y)
	visionAlign.align_X(x)
	visionAlign.align_angle(rotate_degree=angle)
	return True


def VisionFiberEdge(parameters, x=0.0, y=0.0, angle=0.0):

	sideCamera_DieSide = LeftSideCameraControl('Die_Side_Close', exposure = 1)
	vision_DieSide = Vision('DieSideEdgeVisionTool', sideCamera_DieSide, parameters)

	sideCamera_FAUSide = LeftSideCameraControl('FAU_Side_Close', exposure = 1)
	vision_FAUSide = Vision('FAUSideEdgeVisionTool', sideCamera_FAUSide, parameters)

	transformer = Transformer('LeftSideCameraTransform', 'X', 'Z', 'V')
	visionAlign = VisionAlign(vision_DieSide, vision_FAUSide, transformer)

	if visionAlign.run() is False:
		return False

	visionAlign.align_X(x)
	visionAlign.align_Y(y)
	visionAlign.align_angle(rotate_degree=angle)
	return True

def VisionRightEdge(parameters, x=0.0, y=0.0, angle=0.0):

	sideCamera_DieSide = RightSideCameraControl('Die_Side_Close', exposure = 3)
	vision_DieSide = Vision('DieRightSideEdgeVisionTool', sideCamera_DieSide, parameters)

	sideCamera_FAUSide = RightSideCameraControl('FAU_Side_Close', exposure = 3)
	vision_FAUSide = Vision('FAURightSideEdgeVisionTool', sideCamera_FAUSide, parameters)

	transformer = Transformer('RightSideCameraTransform', 'X', 'Z', 'V')
	visionAlign = VisionAlign(vision_DieSide, vision_FAUSide, transformer)

	if visionAlign.run() is False:
		return False

	visionAlign.align_X(x)
	visionAlign.align_Y(y)
	visionAlign.align_angle(rotate_degree=angle)
	return True


def VisionRightEdgeDiff(parameters, stage="die_right_side", x=0.0, y=0.0, angle=0.0):

	sideCamera_DieSide = RightSideCameraControl(stage, exposure = 5)
	vision_DieSide = Vision('DieRightSideDiffVisionTool', sideCamera_DieSide, parameters)

	transformer = Transformer('RightSideCameraTransform', 'X', 'Z', 'V')
	visionDiffAlign = VisionDiffAlign(vision_DieSide, transformer)

	if visionDiffAlign.run() is False:
		return None

	visionDiffAlign.align_X(x)
	visionDiffAlign.align_Y(y)
	visionDiffAlign.align_angle(rotate_degree=angle)
	return visionDiffAlign


