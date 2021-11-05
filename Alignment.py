'''
Created on Dec 9, 2020

@author: dingchen
'''
from AlignerUtil import *

def ScramblePolarizationMPC201(scramblerType=ScrambleMethodType.Triangle):
	PolarizationControl.SetScrambleMethod(scramblerType)
	sleep(1)
	if scramblerType == ScrambleMethodType.Discrete:
		freq = 20000
	else:
		freq = 2000
	PolarizationControl.SetScrambleRate(freq) #Hz
	sleep(1)
	PolarizationControl.SetScrambleEnableState(True)
	sleep(0.3)
	if not PolarizationControl.ReadScrambleEnableState():
		return False
	return True

class LaserSwitch(object):
	def __init__(self, device, channel):
		self.device = device
		self.channel = channel
		
	def Set(self):
		if self.channel == 1:
			IOController.SetOutputValue(self.device, False)
		elif self.channel==2:
			IOController.SetOutputValue(self.device, True)
		LogHelper.Log('LaserSwitch', LogEventSeverity.Alert, 'laser switch {0}.'.format(self.channel))

class OpticalSwitch(object):

	def __init__(self, device, mod1chn, mod2chn, comment):
		self.device = device
		self.mod1chn = mod1chn
		self.mod2chn = mod2chn
		self.comment = comment
		
	def Set(self):
		self.device.SetClosePoints(1,self.mod1chn)
		LogHelper.Log('SwitchLaserAndLoopbackChannel', LogEventSeverity.Alert, 'switch SGR X8 module 1 to channel {0}.'.format(self.mod1chn))
		sleep(1)
		self.device.SetClosePoints(2,self.mod2chn)
		LogHelper.Log('SwitchLaserAndLoopbackChannel', LogEventSeverity.Alert, 'switch SGR X8 module 2 to channel {0}.'.format(self.mod2chn))
		LogHelper.Log('SwitchLaserAndLoopbackChannel', LogEventSeverity.Alert, self.comment)
		sleep(1)

class PolarizationController(object):
	def __init__(self, meter):
		self.meter = meter
		self.state = []
		self.scrambleType = ScrambleMethodType.Triangle
		# self.scrambleFrequence = 2000
		
	def EnableScramble(self, scrambleType = ScrambleMethodType.Triangle):
		self.scrambleType = scrambleType
		if self.scramblerType == ScrambleMethodType.Discrete:
			freq = 20000
		else:
			freq = 2000
		PolarizationControl.SetScrambleRate(freq) #Hz
		sleep(1)
		PolarizationControl.SetScrambleEnableState(True)

	def ReadScramblePower(self):
		self.Scramble(scramblerType=ScrambleMethodType.Discrete)
		sleep(1)
		scramble_power = self.meter.ReadPowerWithStatistic(n_measurements=1000)
		LogHelper.Log('PolarizationController', LogEventSeverity.Alert,
					 'scramble peak: ave {0:.3f}V median {1:.3f}  STD {2:.3f}, min {3:.3f}, max {4:.3f}'.format(scramble_power[0],scramble_power[1],scramble_power[2], scramble_power[3], scramble_power[4]))
		PolarizationControl.SetScrambleEnableState(False)
		return scramble_power
		
	def DisableScramble(self):
		PolarizationControl.SetScrambleEnableState(False)

	def SetPolarizations(self, state, channels = ['1','2','3','4']	):
		PolarizationControl.SetScrambleEnableState(False)
		sleep(0.2)
		LogHelper.Log('PolarizationController', LogEventSeverity.Alert,
					 'Setting polarization to [{0:.2f}, {1:.2f}, {2:.2f}, {3:.2f}]...'.format(state[0],state[1],state[2],state[3]))
		for i in range(4):
			if not PolarizationControl.SetPolarization(state[i], channels[i]):
				return False
			sleep(0.2)
	# def FastOptimizePolarization(mode='max'):

		
class SearchMaxPosition(object):
	def __init__(self, id, laser, meter, opticalSwitch, threshold, polarizationController=None):
		self.id = id
		self.laser = laser
		self.meter = meter
		self.opticalSwitch = opticalSwitch
		self.polarizationController = polarizationController
		self.peak_position = []
		self.polarization_state = []
		self.peak_power = ()
		self.scramble_power = ()
		self.balanced_power = ()
		self.polarization_power = ()
		self.threshold = threshold
		self.pitch_offset = 0.0

	@property
	def Z_position(self):
		if self.peak_position:
			return self.peak_position[2]
		return None

	@property
	def result(self):
		output = OrderedDict()
		output['peak_position'] = map(lambda x: round(x,4), list( self.peak_position ))
		output["peak_power"] = self.peak_power
		if len(self.balanced_power) > 0:
			# balanced_power = self.balanced_power
			# balanced_power.append(self.meter.unit)
			output["balanced_power"] = self.balanced_power
			output["Off_peak_loss"] = [-10 * math.log10(self.balanced_power[0]/self.peak_power[0]), "dB"]
		if len(self.scramble_power) > 0:
			output["scramble_power"] = self.scramble_power
		if len(self.polarization_state) > 0:
			output["polarization_state"] = self.polarization_state
		output["peak_offset"] = self.pitch_offset
		return output

	def SetPitchOffset(self, balanced_position):
		if self.peak_position:
			y_offset = self.peak_position[1] - balanced_position[1]
			z_offset = self.peak_position[2] - balanced_position[2]
			self.pitch_offset = (y_offset, z_offset, math.sqrt(y_offset*y_offset + z_offset*z_offset))
		return self.pitch_offset

	def ReadPower(self):
		if self.laser != None:
			self.laser.Set()
		self.opticalSwitch.Set()
		return self.meter.ReadPowerWithStatistic(self.meter.channel)

	def scan(self, SequenceObj):
		if self.laser != None:
			self.laser.Set()
		self.opticalSwitch.Set()
		UseOpticalSwitch = False
		if self.polarizationController:
			UseOpticalSwitch = True
			if not self.polarization_state:
				if self.polarizationController.EnableScramble():
					return False
			else:
				(self.polarization_state, self.polarization_power) = self.polarizationController.SetPolarization(self.polarization_state)

		self.meter.ReadPowerWithStatistic(self.meter.channel, n_measurements=100)
		LogHelper.Log('SearchMaxPosition', LogEventSeverity.Alert, "Meter channel {0} threshold {1:.2f} reading max {2:.2f}".format(self.meter.channel, self.threshold, self.meter.max))
		if self.meter.max < self.threshold: #check max signal found
			if not NanocubeSpiralScan(SequenceObj, self.meter.channel, threshold = self.threshold, UseOpticalSwitch = UseOpticalSwitch):
				Nanocube.GetHardwareStateTree().ActivateState('Center')
				return False

		LogHelper.Log('Alignment.scan', LogEventSeverity.Alert, "Start Gradient climb")
		sleep(0.5)
		if not NanocubeGradientClimb(SequenceObj, self.meter.channel, threshold = self.threshold, UseOpticalSwitch = UseOpticalSwitch) or SequenceObj.Halt:
			return False
			
		# remember the peak top channel position
		position= Nanocube.GetAxesPositions()
		power = self.meter.ReadPowerWithStatistic(self.meter.channel)
		LogHelper.Log('Alignment.scan', LogEventSeverity.Alert,
					 'peak: {0:.3f}V (STD {1:.3f}) @ [{2:.2f}, {3:.2f}, {4:.2f}]um'.format(power[0],power[2], position[0],position[1],position[2]))

		self.peak_position = position
		self.peak_power = power

		if self.polarizationController:
			self.scramble_power =  self.polarizationController.ReadScramblePower()
		return True


class RollAlignment(object):
	def __init__(self, channels, WG2WG_dist_mm, max_z_difference_um, fau_flip=False):
		self.channels = channels
		self.WG2WG_dist_mm = WG2WG_dist_mm
		self.top_position = 0.0
		self.bottom_position = 0.0
		self.max_z_difference_um = max_z_difference_um 
		self.num_channels = 0
		self.balanced_position = [50.0, 50.0, 50.0]
		self.pitch_offset = []
		self.fau_flip = fau_flip

	@property
	def Results(self):
		output = OrderedDict()
		for channel in self.channels:
			output[channel.id] = channel.result
		output['balanced_position'] = map(lambda x: round(x,4), list( self.balanced_position ))
		return output
		
	def scan(self, SequenceObj):
		for channel in self.channels:
			if not channel.scan(SequenceObj):
				return False
		
		for i in range(3):
			self.balanced_position[i] = 0.0
			for channel in self.channels:
				self.balanced_position[i] += channel.peak_position[i]
			self.balanced_position[i] /= len(self.channels)
		return True

	def FindTopAndBottomPosition(self):
		pass
	
	def OptimizePosition(self):
		# double check and readjust roll if necessary
		# calculate the roll angle, different in Z.
		self.FindTopAndBottomPosition()

		h = self.top_position - self.bottom_position
		# balanced position
		ydiff = self.balanced_position[1]-50.0
		zdiff = self.balanced_position[2]-50.0
		if Math.Abs(h) < self.max_z_difference_um and Math.Abs(ydiff) < 0.5 and Math.Abs(zdiff) < 0.5:
			# we achieved the roll angle when the optical Z difference. 
			Nanocube.MoveAxisAbsolute('Y', self.balanced_position[1], Motion.AxisMotionSpeeds.Normal, True)
			Nanocube.MoveAxisAbsolute('Z', self.balanced_position[2], Motion.AxisMotionSpeeds.Normal, True)
			return True
		else:
			Nanocube.MoveAxisAbsolute('Y', 50, Motion.AxisMotionSpeeds.Normal, True)
			Nanocube.MoveAxisAbsolute('Z', 50, Motion.AxisMotionSpeeds.Normal, True)

			Hexapod.MoveAxisRelative('Y', ydiff/1000, Motion.AxisMotionSpeeds.Normal, True)
			Hexapod.MoveAxisRelative('Z', zdiff/1000, Motion.AxisMotionSpeeds.Normal, True)

			# calculate the roll angle
			r = Utility.RadianToDegree(Math.Asin(h / (self.WG2WG_dist_mm*1000)))

			LogHelper.Log("RollAlignment", LogEventSeverity.Alert, 'Flipped {0} wave guide distant {1}'.format(self.fau_flip, self.WG2WG_dist_mm))
			if self.fau_flip:
				rollangle = -r
			else:
				rollangle = r
			"""
			rollangle = 0.5 * rollangle

			if rollangle > 0.5:
				rollangle = 0.5
			elif rollangle < -0.5:
				rollangle = -0.5
			"""

			# adjust the roll angle 
			Hexapod.MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
			return False

	def Iteration(self,  SequenceObj, num=10):
		if self.num_channels != len(self.channels):
			return False
		
		for i in range(num):
			LogHelper.Log('Alignment.RollAlignment.Iteration', LogEventSeverity.Alert, 'Iteration {0}'.format(i))
			if not self.scan(SequenceObj):
				return False
			if self.OptimizePosition():
				break
		for channel in self.channels:
			channel.SetPitchOffset(self.balanced_position)
			channel.balanced_power = channel.ReadPower()
			LogHelper.Log('Alignment.RollAlignment.Iteration', LogEventSeverity.Alert, ' {0} balanced power {1:.3f}'.format(channel.id, channel.balanced_power[0]))
		return True
	
class TwoChannelRollAlignment(RollAlignment):
	def __init__(self, channels, WG2WG_dist_mm, max_z_difference_um, fau_flip=False):
		super(TwoChannelRollAlignment, self).__init__(channels, WG2WG_dist_mm, max_z_difference_um,fau_flip=fau_flip)
		self.num_channels = 2
		
	def FindTopAndBottomPosition(self):
		if len(self.channels) == 2:
			self.top_position = self.channels[0].Z_position
			self.bottom_position = self.channels[1].Z_position
		else:	
			LogHelper.Log('DualLoopbackRollAlignment', LogEventSeverity.Warning, 'Wrong number of channels')
		
		
class FourChannelRollAlignment(RollAlignment):
	def __init__(self, channels, WG2WG_dist_mm, max_z_difference_um, fau_flip=False):
		super(FourChannelRollAlignment, self).__init__(channels, WG2WG_dist_mm, max_z_difference_um,fau_flip=fau_flip)
		self.num_channels = 4
		
	def FindTopAndBottomPosition(self):
		if len(self.channels) == 4:
			self.top_position = (self.channels[0].Z_position + self.channels[1].Z_position)/2
			self.bottom_position = (self.channels[2].Z_position + self.channels[3].Z_position)/2
		else:	
			LogHelper.Log('DualLoopbackRollAlignment', LogEventSeverity.Warning, 'Wrong number of channels')
		
class TestResult(object):
	def __init__(self, id, laser, meter, opticalSwitch, polarizationController=None):
		self.id = id
		self.laser = laser
		self.meter = meter
		self.opticalSwitch = opticalSwitch
		self.polarizationController = polarizationController
		self.max_power = 0.0
		self.min_power = 0.0
		self.scramble_power = 0.0
		self.mean_power = 0.0
		self.unit = ""

	def run(self, SequenceObj):
		if self.laser != None:
			self.laser.Set()
		self.opticalSwitch.Set()
		self.unit = self.meter.unit
		if self.polarizationController:
			(self.max_polarizations, self.max_power) = FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1, coarse_scan = False)
			(self.min_polarizations, self.min_power) = FastOptimizePolarizationMPC201(SequenceObj,feedback_channel=1, mode='min', coarse_scan = False)
			ScramblePolarizationMPC201(SequenceObj, scramblerType=ScrambleMethodType.Discrete)
			sleep(1)
			self.scramble_power = self.meter.ReadPowerWithStatistic(self.meter.channel, n_measurements=100)
			PolarizationControl.SetScrambleEnableState(False)
			LogHelper.Log("TestCase", LogEventSeverity.Alert, 'max power {0:.3f} min power {1:.3f}.'.format(self.max_power, self.min_power))
		else:
			self.mean_power = self.meter.ReadPower(self.meter.channel)
			# LogHelper.Log("TestCase", LogEventSeverity.Alert, 'power {0:.3f}.'.format(self.mean_power))


	@property
	def Result(self):
		output = OrderedDict()
		if self.polarizationController:
			output['max_power'] = self.max_power
			output['min_power'] = self.min_power
			output['max_polarizations'] = map(lambda x: '%.3f'%x, self.max_polarizations )
			output['min_polarizations'] = map(lambda x: '%.3f'%x, self.min_polarizations )
			output['scramble_power'] = self.scramble_power
		else:
			output['power'] = [self.mean_power, self.unit]
		return output

class TestResults(object):
	def __init__(self, cases):
		self.cases = cases

	def run(self, SequenceObj):
		for case in self.cases:
			case.run(SequenceObj)

	@property
	def Results(self):
		output = OrderedDict()
		for case in self.cases:
			output[case.id] = case.Result
		return output


