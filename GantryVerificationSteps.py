# Include all necessary assemblies from the C# side
# DO NOT REMOVE THESE REFERECES
import clr
clr.AddReference('System.Core')
import System
clr.ImportExtensions(System.Linq)
from System import IO
from System import Action
from System import Func
from System import DateTime
from System import Array
from System import String
from System import ValueTuple
from System import Math
#from System.Random import Next
#import random
from System.Diagnostics import Stopwatch
from System.Collections.Generic import List
clr.AddReferenceToFile('HAL.dll')
from HAL import Motion
from HAL import HardwareFactory
from HAL import HardwareInitializeState
from HAL import Vision
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoAligner.exe')
from CiscoAligner import PickAndPlace
from CiscoAligner import Station
from CiscoAligner import Alignments
from CiscoAligner import CoordinateCalibration

#-------------------------------------------------------------------------------
# median
# Helper function to calculate median of a list
#-------------------------------------------------------------------------------
def median(lst):
    
    even = (0 if len(lst) % 2 else 1) + 1
    half = (len(lst) - 1) / 2
    return sum(sorted(lst)[half:half + even]) / float(even)

#-------------------------------------------------------------------------------
# Initialize
# Initialize station for calibration
#-------------------------------------------------------------------------------
def Initialize(StepName, SequenceObj, TestMetrics, TestResults):

    #Clear the data panel on the main UI
    TestResults.ClearAllTestResult()

    #Show user what's going on
    Utility.ShowProcessTextOnMainUI('Move to verification start position.')    

    #Retrieve the reference to our hardware
    Gantry = HardwareFactory.Instance.GetHardwareByName('Gantry')
    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')

    # go to start position and ask for the vision fiducial to be installed
    Gantry.GetHardwareStateTree().ActivateState('Start')
    

    return 1

#-------------------------------------------------------------------------------
# CalibrateDownCamera
# Calibrate the down camera to stage positions
#-------------------------------------------------------------------------------
def CalibrateCamera(StepName, SequenceObj, TestMetrics, TestResults):
    
    # camera shift distance for calibration
    CAMERA_CAL_TARGET_SHIFT = 1.6

    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')
    Gantry = HardwareFactory.Instance.GetHardwareByName('Gantry')

    # Generate the calibration points
    cornerpoints = [(0,0),(-CAMERA_CAL_TARGET_SHIFT / 2, 0),(0, -CAMERA_CAL_TARGET_SHIFT / 2),\
        (CAMERA_CAL_TARGET_SHIFT / 2, 0),(CAMERA_CAL_TARGET_SHIFT / 2, 0),\
        (0, CAMERA_CAL_TARGET_SHIFT / 2),(0, CAMERA_CAL_TARGET_SHIFT / 2),\
        (-CAMERA_CAL_TARGET_SHIFT / 2, 0),(-CAMERA_CAL_TARGET_SHIFT / 2, 0)]      

    # Create the calibration point collection
    downCameraPoints = List[Vision.CalibratePointPair]()
    DownCamAngles = []

    # move to camera calibration preset position
    if not Gantry.GetHardwareStateTree().ActivateState('Start'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to down camera start calibration position.')
        return 0

    if SequenceObj.Halt:
        return 0

    # turn off all lights and then set to recipe level
    #DownCamera.LightControl1.Item2.SetIlluminationOff()        

    # start the calibration routine
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "Calibrating cameras...")

    # Get recipe parameters
    #downcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamCalExposure').DataItem
    downvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ReticlePatternVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem
    # set exposure and lighting
    #DownCamera.SetExposureTime(downcamexposure)
    #DownCamera.LightControl1.Item2.GetHardwareStateTree().ActivateState('CameraCalibration')
    
    # remember where we started
    calibrateaxes = Array[String]([ 'X', 'Y' ])    
    camangles = []

    # Iterate through the points and acquire calibration points
    for p in cornerpoints:
        if not Gantry.MoveAxesRelative(calibrateaxes, Array[float]([p[0], p[1]]), Motion.AxisMotionSpeeds.Normal, True):
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to calibration position.')
            return 0
        # Wait for stage to settle
        Utility.DelayMS(1000)

        # variable to save results
        camsnapx = []
        camsnapy = []
        camsnapangle = []

        # start acqusition
        for i in range(snaps):
            DownCamera.Snap()
            res = MachineVision.RunVisionTool(downvision)
            if res['Result'] != 'Success':
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
                return 0
            # save result
            camsnapx.append(res['X'])
            camsnapy.append(res['Y'])
            camsnapangle.append(res['Angle'])

        # Done repeat snaps, find the median for each value
        medianx = median(camsnapx)
        mediany = median(camsnapy)
        camangles.append(median(camsnapangle))

        # Add to point collection
        downCameraPoints.Add( Vision.CalibratePointPair(medianx, mediany, Gantry.GetAxisPosition('X'), Gantry.GetAxisPosition('Y')))

    # Down camera loop done, save angle information and reset hardware
    DownCamAngles.append(sum(camangles)/len(camangles))
    #DownCamera.LightControl1.Item2.SetIlluminationOff()
    #DownCamera.Live(True)

    #Done snap, return to start
    Gantry.GetHardwareStateTree().ActivateState('Start')

    # Generate the transforms and save
    MachineVision.AddTransform('DownCameraTransform', downCameraPoints)
    TestResults.AddTestResult('StaticAngle', sum(DownCamAngles)/len(DownCamAngles))

    # Get camera resolution
    width = clr.Reference[System.Int32]()
    height = clr.Reference[System.Int32]()
    # establish and save the camera vectors
    # get the down cam center positions
    DownCamera.GetImageSize(width, height)

    # Output the camera resolution
    TestResults.AddTestResult('CameraResolutionX', width.Value)
    TestResults.AddTestResult('CameraResolutionY', height.Value)

    # find the center position in real coordinate
    dcCalCenter = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](width.Value / 2, height.Value / 2))
    if dcCalCenter == None:
        return 0

    # Move to center of image
    if not Gantry.MoveAxesAbsolute(calibrateaxes, Array[float]([dcCalCenter.Item1, dcCalCenter.Item2]), Motion.AxisMotionSpeeds.Normal, True):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to calibrated center position.')
        return 0

    # Wait for stage to settle
    Utility.DelayMS(500)

    # Save the origin position
    origin = Gantry.GetAxesPositions(calibrateaxes)
    TestResults.AddTestResult('OriginXTarget', dcCalCenter.Item1)
    TestResults.AddTestResult('OriginYTarget', dcCalCenter.Item2)
    
    
    #one more vision verification
    DownCamera.Snap()
    res = MachineVision.RunVisionTool(downvision)
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
        return 0
    dcCalCenter = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](res['X'], res['Y']))
    if dcCalCenter == None:
        return 0

    #record vision result
    TestResults.AddTestResult('OriginXVision', dcCalCenter.Item1)
    TestResults.AddTestResult('OriginYVision', dcCalCenter.Item2)
    origin = Gantry.GetAxesPositions(calibrateaxes)
    TestResults.AddTestResult('OriginXGantry', origin[0])
    TestResults.AddTestResult('OriginYGantry', origin[1])




    posErrorX = TestResults.RetrieveTestResult('OriginXTarget') - TestResults.RetrieveTestResult('OriginXVision')
    posErrorY = TestResults.RetrieveTestResult('OriginYTarget') - TestResults.RetrieveTestResult('OriginYVision')

    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "Position error in aquiring center of camera [{0:.2f} um,{1:.2f} um].".format(posErrorX*1000,posErrorY*1000))

    return 1

#-------------------------------------------------------------------------------
# FixtureCameras
# Calibrate cameras
#-------------------------------------------------------------------------------
def GetWaferAngle(StepName, SequenceObj, TestMetrics, TestResults):

    Utility.ShowProcessTextOnMainUI()

    #Retrieve the reference to our hardware
    Gantry = HardwareFactory.Instance.GetHardwareByName('Gantry')
    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')

    calibrateaxes = Array[String]([ 'X', 'Y' ])

    # Get recipe parameters
    #downcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamCalExposure').DataItem
    downvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ReticlePatternVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem

    #generate a vector in pixel space and get the stage space coordinate
    vectorstart = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](0, 0))
    vectorend = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](10000, 0))

    #calculate the camera to x axis angle
    angle = Math.Atan((vectorend.Item2 - vectorstart.Item2) / (vectorend.Item1 - vectorstart.Item1))
    TestResults.AddTestResult('CalibratedAngle', angle)

    #get the static angle back
    waferAngle = angle - TestResults.RetrieveTestResult('StaticAngle')
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "First guess for wafer angle {0:E} deg.".format(waferAngle*180/Math.PI))

    camCenterPosition = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](TestResults.RetrieveTestResult('CameraResolutionX') / 2, TestResults.RetrieveTestResult('CameraResolutionY')  / 2))
    if camCenterPosition == None:
        return 0


    #get the wafer pattern pitch
    xpitch = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PatternPitchX').DataItem
    i=0
    fiducialLocationError = {'X':0,'Y':0}
    dy = 0
    while i<12:
        i += 1
        if SequenceObj.Halt:
            return 0
        xoffset = Math.Cos(waferAngle) * xpitch - fiducialLocationError['X']
        yoffset = Math.Sin(waferAngle) * xpitch - fiducialLocationError['Y']
        

        #move to next reticle
        if not Gantry.MoveAxesRelative(calibrateaxes, Array[float]([xoffset, yoffset]), Motion.AxisMotionSpeeds.Normal, True):
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to calibrated center position.')
            return 0

        Utility.DelayMS(500)

        #check where we ended up
        DownCamera.Snap()
        res = MachineVision.RunVisionTool(downvision)
        if res['Result'] != 'Success':
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to locate the fiducial.')
            if i>0:
                continue
            else:
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Could not find second fiducial for wafer angle calculation.')
                return 0

        dcCalCenter = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](res['X'], res['Y']))
        if dcCalCenter == None:
            return 0

        fiducialLocationError['X'] = dcCalCenter.Item1 - camCenterPosition.Item1
        fiducialLocationError['Y'] = dcCalCenter.Item2 - camCenterPosition.Item2
        TestResults.AddTestResult('fiducialLocationErrorX',fiducialLocationError['X'])
        TestResults.AddTestResult('fiducialLocationErrorY',fiducialLocationError['Y'])

        currentGantryPosition = Gantry.GetAxesPositions(calibrateaxes)

        #record vision result
        TestResults.AddTestResult('LastAngleCalcXVision', dcCalCenter.Item1 + (currentGantryPosition[0] - TestResults.RetrieveTestResult('OriginXGantry')))
        TestResults.AddTestResult('LastAngleCalcYVision', dcCalCenter.Item2 + (currentGantryPosition[1] - TestResults.RetrieveTestResult('OriginYGantry')))

        dx = TestResults.RetrieveTestResult('LastAngleCalcXVision') - TestResults.RetrieveTestResult('OriginXGantry')
        dy = TestResults.RetrieveTestResult('LastAngleCalcYVision') - TestResults.RetrieveTestResult('OriginYGantry')

        newWaferAngle = Math.Atan(dy / dx)


        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "New guess for wafer angle {0:E} deg (change of {1:E} deg).".format(newWaferAngle*180/Math.PI,(newWaferAngle-waferAngle)*180/Math.PI))

        waferAngle = newWaferAngle

    TestResults.AddTestResult('WaferAngle', waferAngle)
    TestResults.AddTestResult('maxXIndex', i)

    #TODO: continue west to the end of the wafer, then go east, find E/W center and go North/South, find global center, spiral out



    return 1


def VerifyGantryAccuracy(StepName, SequenceObj, TestMetrics, TestResults):

    Utility.ShowProcessTextOnMainUI()

    #Retrieve the reference to our hardware
    Gantry = HardwareFactory.Instance.GetHardwareByName('Gantry')
    DownCamera = HardwareFactory.Instance.GetHardwareByName('DownCamera')
    MachineVision = HardwareFactory.Instance.GetHardwareByName('MachineVision')

    downvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ReticlePatternVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem

    calibrateaxes = Array[String]([ 'X', 'Y' ]) #Active gantry axes

    # Get recipe parameters
    #downcamexposure = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DownCamCalExposure').DataItem
    downvision = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ReticlePatternVisionTool').DataItem
    snaps = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NumberOfAcquisitions').DataItem

    # move to camera calibration preset position
    if not Gantry.GetHardwareStateTree().ActivateState('Start'):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to down camera start calibration position.')
        return 0

    #set the 'index' of the predefines 'start' location as 0,0
    #other locations will be defined in reticle widths and heights away from this origin
    #currentLocationIndex = {'X':0, 'Y':0}
    waferAngle = TestResults.RetrieveTestResult('WaferAngle')
    PatternPitchX = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PatternPitchX').DataItem
    PatternPitchY = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PatternPitchY').DataItem

    
    maxXIndex = TestResults.RetrieveTestResult('maxXIndex')
    
    
    # go row by row and look for fiducials
    # start on the next row once you hit the maxXIndex
    # if no fiducials are found on the row stop
    fiducialPositionIndex = {}
    fiducialPositionIndex['X'] = 0
    fiducialPositionIndex['Y'] = 0
    fiducialFoundOnRow = True
    xTravelDir = 1
    while fiducialFoundOnRow:
        fiducialFoundOnRow = False
        #fiducialPositionIndex['X'] = 0
        #stop loop if halt button is pressed
        while ((fiducialPositionIndex['X']<= maxXIndex) & (fiducialPositionIndex['X'] >= 0)) :
            if SequenceObj.Halt:
                return 0

            nextX = Math.Cos(waferAngle) * PatternPitchX * fiducialPositionIndex['X'] - Math.Sin(waferAngle) * PatternPitchY * fiducialPositionIndex['Y'] + TestResults.RetrieveTestResult('OriginXGantry')
            nextY = Math.Sin(waferAngle) * PatternPitchX * fiducialPositionIndex['X'] + Math.Cos(waferAngle) * PatternPitchY * fiducialPositionIndex['Y'] + TestResults.RetrieveTestResult('OriginYGantry')

            ### check if next position is in the gantry range of travel
            #if ((nextX) < Gantry.AxesSoftLowerTravelLimits[0]) or ((nextX) > Gantry.AxesSoftUpperTravelLimits[0]):
            #    continue
            #elif ((nextY) < Gantry.AxesSoftLowerTravelLimits[1]) or ((nextY) > Gantry.AxesSoftUpperTravelLimits[1]):
            #    continue
            

            #move to next reticle
            if not Gantry.MoveAxesAbsolute(calibrateaxes, Array[float]([nextX, nextY]), Motion.AxisMotionSpeeds.Normal, True):
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to next fiducial.')
                return 0
            Utility.DelayMS(500)

            #LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "{} gantry moves remaining in step.".format(moves))

            DownCamera.Snap()
            res = MachineVision.RunVisionTool(downvision)
            if res['Result'] != 'Success':
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Machine vision (downvision) was not successful.')
                fiducialPositionIndex['X'] += xTravelDir
                continue

            dcCalCenter = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](res['X'], res['Y']))
            if dcCalCenter == None:
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'DownCameraTransform did not return a value.')
                fiducialPositionIndex['X'] += xTravelDir
                continue

            fiducialFoundOnRow = True

            currentGantryPosition = Gantry.GetAxesPositions(calibrateaxes)

            #calculate actual visioned location of fiducial
            currentVisionX = dcCalCenter.Item1 + (currentGantryPosition[0] - TestResults.RetrieveTestResult('OriginXGantry'))
            currentVisionY = dcCalCenter.Item2 + (currentGantryPosition[1] - TestResults.RetrieveTestResult('OriginYGantry'))

            
            #by our calibration and our knowledge of the wafer angle we can calculate where we SHOULD have ended up in stage coordinates
            #currentTargetX = Math.Cos(waferAngle) * PatternPitchX * currentLocationIndex['X'] - Math.Sin(waferAngle) * PatternPitchY * currentLocationIndex['Y'] + TestResults.RetrieveTestResult('OriginXTarget')
            #currentTargetY = Math.Sin(waferAngle) * PatternPitchX * currentLocationIndex['X'] + Math.Cos(waferAngle) * PatternPitchY * currentLocationIndex['Y'] + TestResults.RetrieveTestResult('OriginYTarget')

            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "Position error in aquiring fiducial [{0:.2f} um,{1:.2f} um].".format((currentVisionX - nextX)*1000,(currentVisionY - nextY)*1000))
            TestResults.AddTestResult('LastXFidPosError_um', (currentVisionX - nextX)*1000)
            TestResults.AddTestResult('LastYFidPosError_um', (currentVisionY - nextY)*1000)


            fiducialPositionIndex['X'] +=  xTravelDir
        xTravelDir = -xTravelDir
        fiducialPositionIndex['X'] +=  xTravelDir
        #fiducialPositionIndex['X'] = fiducialPositionIndex['X'] + xTravelDir
        fiducialPositionIndex['Y'] += 1

        fiducialPositionIndex['X'] = 0
    fiducialPositionIndex['Y'] = 0
    fiducialFoundOnRow = True
    xTravelDir = 1
    while fiducialFoundOnRow:
        fiducialFoundOnRow = False
        #fiducialPositionIndex['X'] = 0
        #stop loop if halt button is pressed
        while ((fiducialPositionIndex['X']<= maxXIndex) & (fiducialPositionIndex['X'] >= 0)) :
            if SequenceObj.Halt:
                return 0

            nextX = Math.Cos(waferAngle) * PatternPitchX * fiducialPositionIndex['X'] - Math.Sin(waferAngle) * PatternPitchY * fiducialPositionIndex['Y'] + TestResults.RetrieveTestResult('OriginXGantry')
            nextY = Math.Sin(waferAngle) * PatternPitchX * fiducialPositionIndex['X'] + Math.Cos(waferAngle) * PatternPitchY * fiducialPositionIndex['Y'] + TestResults.RetrieveTestResult('OriginYGantry')

            ### check if next position is in the gantry range of travel
            #if ((nextX) < Gantry.AxesSoftLowerTravelLimits[0]) or ((nextX) > Gantry.AxesSoftUpperTravelLimits[0]):
            #    continue
            #elif ((nextY) < Gantry.AxesSoftLowerTravelLimits[1]) or ((nextY) > Gantry.AxesSoftUpperTravelLimits[1]):
            #    continue
            

            #move to next reticle
            if not Gantry.MoveAxesAbsolute(calibrateaxes, Array[float]([nextX, nextY]), Motion.AxisMotionSpeeds.Normal, True):
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move to next fiducial.')
                return 0
            Utility.DelayMS(500)

            #LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "{} gantry moves remaining in step.".format(moves))

            DownCamera.Snap()
            res = MachineVision.RunVisionTool(downvision)
            if res['Result'] != 'Success':
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Machine vision (downvision) was not successful.')
                fiducialPositionIndex['X'] += xTravelDir
                continue

            dcCalCenter = MachineVision.ApplyTransform('DownCameraTransform', ValueTuple[float,float](res['X'], res['Y']))
            if dcCalCenter == None:
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'DownCameraTransform did not return a value.')
                fiducialPositionIndex['X'] += xTravelDir
                continue

            fiducialFoundOnRow = True

            currentGantryPosition = Gantry.GetAxesPositions(calibrateaxes)

            #calculate actual visioned location of fiducial
            currentVisionX = dcCalCenter.Item1 + (currentGantryPosition[0] - TestResults.RetrieveTestResult('OriginXGantry'))
            currentVisionY = dcCalCenter.Item2 + (currentGantryPosition[1] - TestResults.RetrieveTestResult('OriginYGantry'))

            
            #by our calibration and our knowledge of the wafer angle we can calculate where we SHOULD have ended up in stage coordinates
            #currentTargetX = Math.Cos(waferAngle) * PatternPitchX * currentLocationIndex['X'] - Math.Sin(waferAngle) * PatternPitchY * currentLocationIndex['Y'] + TestResults.RetrieveTestResult('OriginXTarget')
            #currentTargetY = Math.Sin(waferAngle) * PatternPitchX * currentLocationIndex['X'] + Math.Cos(waferAngle) * PatternPitchY * currentLocationIndex['Y'] + TestResults.RetrieveTestResult('OriginYTarget')

            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, "Position error in aquiring fiducial [{0:.2f} um,{1:.2f} um].".format((currentVisionX - nextX)*1000,(currentVisionY - nextY)*1000))
            TestResults.AddTestResult('LastXFidPosError_um', (currentVisionX - nextX)*1000)
            TestResults.AddTestResult('LastYFidPosError_um', (currentVisionY - nextY)*1000)


            fiducialPositionIndex['X'] +=  xTravelDir
        xTravelDir = -xTravelDir
        fiducialPositionIndex['X'] +=  xTravelDir
        #fiducialPositionIndex['X'] = fiducialPositionIndex['X'] + xTravelDir
        fiducialPositionIndex['Y'] -= 1
        
    return 1


#-------------------------------------------------------------------------------
# LocateEpoxyToolAndHeight
# Locate and measure the height of the epoxy tool
#-------------------------------------------------------------------------------
def Finalize(StepName, SequenceObj, TestMetrics, TestResults):


    return 1


