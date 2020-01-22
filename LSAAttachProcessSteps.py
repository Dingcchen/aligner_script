# Include all necessary assemblies from the C# side
# DO NOT REMOVE THESE REFERECES
import clr
clr.AddReference('System.Core')
from System import IO
from System import Action
from System import Func
from System import DateTime
from System import Array
from System import String
from System import ValueTuple
from System import Math
from System.Diagnostics import Stopwatch
from System.Collections.Generic import List
clr.AddReferenceToFile('HAL.dll')
from HAL import Motion
from HAL import HardwareFactory
from HAL import HardwareInitializeState
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoAligner.exe')
from CiscoAligner import PickAndPlace
from CiscoAligner import Station
from CiscoAligner import Alignments

def Template(StepName, SequenceObj, TestMetrics, TestResults):
    # DO NOT DELETE THIS METHOD
    # This is the method pattern for all python script called by AutomationCore PythonScriptManager.
    # The method arguments must be exactly as shown. They are the following:
    # SequenceName: This is the name of the process sequence that owns this step. This is required for retrieving process recipe values.
    # StepName: This is the name of the step that invokes this step. Useful for log entry and alerts to user.
    # TestMetrics: The object that holds all the process recipe values. See the C# code for usage.
    # TestResults: The object that stores all process result values. See the C# code for usage.

    TestResults.ClearAllTestResult()

    Utility.DelayMS(2000)
    if Stop:
        return 0

    pivot = TestMetrics.GetTestMetricItem(SequenceName, 'InitialPivotPoint').DataItem
    TestResults.AddTestResult('Pivot', pivot)

    Utility.DelayMS(2000)
    if Stop:
        return 0

    TestResults.AddTestResult('Step2Result', 999)
    LogHelper.Log(StepName, LogEventSeverity.Alert, 'Step1 done')
        
    # Must always return an integer. 0 = failure, everythingthing else = success
    return 1

#-------------------------------------------------------------------------------
# Initialize
# Clears up test data and other prep work before process starts
#-------------------------------------------------------------------------------
def Initialize(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('UpCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # clear the output data
    TestResults.ClearAllTestResult()
    Utility.ShowProcessTextOnMainUI() # clear message

    TestResults.AddTestResult('Start_Time', DateTime.Now)
    TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
    TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())

    # Open the epoxy shield 
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldOut').SetOutputValue(True)
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldIn').SetOutputValue(False)

    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetHardwareStateTree().ActivateState('Load')

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Load
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def Load(StepName, SequenceObj, TestMetrics, TestResults):
    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetHardwareStateTree().ActivateState('Load')

    # Wait for load complete and get serial number
    # possibly using a barcode scanner later
    if PickAndPlace.Instance.CheckSubmountTray() == False or PickAndPlace.Instance.CheckLaserDiodeTray() == False or PickAndPlace.Instance.CheckEpoxyTray() == False:
        return 0

    ret = UserFormInputDialog.ShowDialog('Enter assembly serial number', 'Please enter assembly serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
    else:
        return 0

    ret = UserFormInputDialog.ShowDialog('Enter die serial number', 'Please enter die serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Die_SN', UserFormInputDialog.ReturnValue)
    else:
        return 0

    # epoxy related information
    # persist some of the values for next run
    if 'EpoxyTubeNumber' in SequenceObj.ProcessPersistentData:
        UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyTubeNumber']
    else:
        UserFormInputDialog.ReturnValue = ''
    
    ret = UserFormInputDialog.ShowDialog('Epoxy tube number', 'Please enter epoxy tube number:')
    if ret == False:
        return 0
    # save back to persistent data
    SequenceObj.ProcessPersistentData['EpoxyTubeNumber'] = UserFormInputDialog.ReturnValue
    TestResults.AddTestResult('Epoxy_Tube_Number', UserFormInputDialog.ReturnValue)

    if 'EpoxyExpirationDate' in SequenceObj.ProcessPersistentData:
        UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['EpoxyExpirationDate']
    else:
        UserFormInputDialog.ReturnValue = ''
    
    ret = UserFormInputDialog.ShowDialog('Epoxy expiration date', 'Please enter epoxy expiration date (MM/DD/YYYY):')
    if ret == False:
        return 0
    # save back to persistent data
    SequenceObj.ProcessPersistentData['EpoxyExpirationDate'] = UserFormInputDialog.ReturnValue
    TestResults.AddTestResult('Epoxy_Expiration_Date', UserFormInputDialog.ReturnValue)

    return 1

#-------------------------------------------------------------------------------
# FindSubmount
# Use vision to find the location of the die
#-------------------------------------------------------------------------------
def FindSubmount(StepName, SequenceObj, TestMetrics, TestResults):

    # snap an image of the die
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
    Utility.CreateDirectory(dir)
    PickAndPlace.Instance.SubmountInspect(IO.Path.Combine(dir, 'DieTop.jpg'))

    ret = False
    if TestMetrics.GetTestMetricItem('PickAndPlaceParameters', 'RequireLaserToDieAngleMatching').DataItem == True:
        ret = PickAndPlace.Instance.GetNextSubmountNoAngleAdjustment()
    else:
        ret = PickAndPlace.Instance.GetNextSubmountNoAngleAdjustment(True)

    if ret == False or SequenceObj.Halt == True:
        return 0

    return 1

#-------------------------------------------------------------------------------
# PickUpLaserDiode
# Use vision to find the next laser diode and pick it up
#-------------------------------------------------------------------------------
def PickUpLaserDiode(StepName, SequenceObj, TestMetrics, TestResults):

    # generate the laser diode file name
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
    Utility.CreateDirectory(dir)
    filename = IO.Path.Combine(dir, 'LaserDIodeTop.jpg')

    while PickAndPlace.Instance.CheckLaserDiodeTray() and SequenceObj.Halt == False:
        # snap an image of the laser diode
        PickAndPlace.Instance.DiodePrePickInspect(filename)

        if PickAndPlace.Instance.GetNextLaserDiode() == True:
            
            # save the bottom image
            if PickAndPlace.Instance.DiodePostPickInspect(IO.Path.Combine(dir, 'LaserDIodeBottom.jpg')) == False:
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to find the location of the laser diode on submount.')
                return 0
            
            # log sn in status
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Laser on LSA is at ' + '{:4.2f}'.format(PickAndPlace.Instance.TheLaserDiode.PositionAngle) + ' degree angle.')

            # set the die target angle in the next process step
            PickAndPlace.Instance.TheSubmount.SetTargetAngle(PickAndPlace.Instance.TheLaserDiode.PositionAngle)

            # test the probe contact
            HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentHigh').DataItem)
            HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentHigh').DataItem)
            # turn on to test diode probe connection
            if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(True) and HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(True):
                TestResults.AddTestResult('Laser_SN', PickAndPlace.Instance.TheLaserDiode.PartID)
                return 1
            else:
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Laser diode failed to turn on. Return it back to nest.')
                # bad contact, return the diode
                HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(False)
                HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(False)
                PickAndPlace.Instance.ReturnLaserDiode()
                return 0
        else:
            return 0

    # tray depleted
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Laser diode tray depleted. Please refill to resume process.')
    return 0

#-------------------------------------------------------------------------------
# CheckLaserDiodeGap
# Use vision in side camera to gauge the laser to die gap
#-------------------------------------------------------------------------------
def CheckLaserDiodeGap(StepName, SequenceObj, TestMetrics, TestResults):

    # Place the diode on die
    if PickAndPlace.Instance.PlaceDiodeOnSubmount() == False:
        return 0

    # save the theoretical LSA to die alignment position
    alignpos = PickAndPlace.Instance.GetVisionLSAToDieAlignmentPosition()
    TestResults.AddTestResult('Up_Down_Vision_Align_Position', '{:f},{:f},{:f}'.format(alignpos.X, alignpos.Y, alignpos.Z))

    # set the right light level
    HardwareFactory.Instance.GetHardwareByName('SideCamera').SetExposureTime(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'SideCameraSubmountAndDieExposure').DataItem)
    # get the epoxy location through vision
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Snap()
    # find the epoxy center position
    res = HardwareFactory.Instance.GetHardwareByName('MachineVision').RunVisionTool(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'SideCamFindSubmountAndDiode').DataItem)

    # turn on live view
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    #check vision results
    if res['Result'] != 'Success':
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Vision tool ' + TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'SideCamFindSubmountAndDiode').DataItem + ' failed.')
        return 0

    # load the um to pixel ratio
    ratio = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'SideCameraMMToPixelRatio').DataItem
    # retrieve the vision values and find the differences in um
    # Keep in mind that in vision coordinate system, X value is higher at right part of the image
    # Y value is higher at the lower part of the image
    xdiffum = (res['LaserX'] - res['DieX']) * ratio
    zdiffum = (res['DieY'] - res['LaserY']) * ratio

    # save the gap info
    TestResults.AddTestResult('Initial_Side_Vision_Gap_X', '{:f}'.format(xdiffum))
    TestResults.AddTestResult('Initial_Side_Vision_Gap_Z', '{:f}'.format(zdiffum))

    if TestMetrics.GetTestMetricItem('PickAndPlaceParameters', 'RequireLaserToDieAngleMatching').DataItem  == True and SequenceObj.Halt == False:
        return 1
    elif SequenceObj.Halt:
        return 0
    else:
        visionposx = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxisPosition('X') - xdiffum
        visionposz = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxisPosition('Z') + zdiffum
        TestResults.AddTestResult('Side_Vision_Align_Position', '{:f},{:f},{:f}'.format(alignpos.X, alignpos.Y, alignpos.Z))

        # move to specified gap from recipe
        gapxz = list(map(lambda x: float(x), TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserToDiePlacementGapXZ').DataItem.split(',')))
        # move to achieve the right gap
        if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxesAbsolute(Array[String](['X', 'Z']), Array[float]([visionposx + gapxz[0], visionposz - gapxz[1]]), Motion.AxisMotionSpeeds.Normal, True) == False:
            return 0
            return 0

    return 1

#-------------------------------------------------------------------------------
# SetSubmountAngle
# Rotate the die to match the laser diode angle
#-------------------------------------------------------------------------------
def SetSubmountAngle(StepName, SequenceObj, TestMetrics, TestResults):

    # if no angle matching required
    if TestMetrics.GetTestMetricItem('PickAndPlaceParameters', 'RequireLaserToDieAngleMatching').DataItem == False:
        return 1

    # inspect the die and match to laser angle
    if PickAndPlace.Instance.GetNextSubmountAngleAdjustment(PickAndPlace.Instance.TheLaserDiode.PositionAngle):
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Laser die is at ' + '{:f}'.format(PickAndPlace.Instance.TheSubmount.PositionAngle) + ' degrees angle.')
        return 1

    return 0

#-------------------------------------------------------------------------------
# PlaceLaserDiode
# Place the laser diode on die for alignment
#-------------------------------------------------------------------------------
def PlaceLaserDiode(StepName, SequenceObj, TestMetrics, TestResults):

    if TestMetrics.GetTestMetricItem('PickAndPlaceParameters', 'RequireLaserToDieAngleMatching').DataItem == False:
        return 1

    if PickAndPlace.Instance.PlaceDiodeOnSubmount() == False:
        return 0

    # save the theoretical lsa to die alignment position
    alignpos = PickAndPlace.Instance.GetVisionLSAToDieAlignmentPosition()
    TestResults.AddTestResult('Up_Down_Vision_Align_Position', '{:f},{:f},{:f}'.format(alignpos.X, alignpos.Y, alignpos.Z))

    # retrieve the gap we found before
    xdiffum = float(TestResults.RetrieveTestResult('Initial_Side_Vision_Gap_X'))
    zdiffum = float(TestResults.RetrieveTestResult('Initial_Side_Vision_Gap_Z'))

    visionposx = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxisPosition('X') - xdiffum
    visionposz = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxisPosition('Z') + zdiffum
    TestResults.AddTestResult('Side_Vision_Align_Position', '{:f},{:f},{:f}'.format(visionposx, alignpos.Y, visionposz))

    # move to specified gap from recipe
    gapxz = list(map(lambda x: float(x), TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserToDiePlacementGapXZ').DataItem.split(',')))

    # move to achieve the right gap
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxesAbsolute(Array[String](['X', 'Z']), Array[float]([visionposx + gapxz[0], visionposz - gapxz[1]]), Motion.AxisMotionSpeeds.Normal, True) == False:
        return 0

    if SequenceObj.Halt:
        return 0
    
    return 1

#-------------------------------------------------------------------------------
# Channel2BFirstLight
# First light alignment on channel 2B
#-------------------------------------------------------------------------------
def Channel2BFirstLight(StepName, SequenceObj, TestMetrics, TestResults):
    
    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('UpCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # set the 2B LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentHigh').DataItem)
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(False) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(True) == False:
        return 0

    # get the hexapod alignment algorithm
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    # Reload parameters from recipe file
    minpower = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanMinPower').DataItem # this value will be in hexapod analog input unit. 
    scan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
    scan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').FindByName('Channel2BMonitorSignal')
    scan.Channel = 2
    scan.ExecuteOnce = SequenceObj.AutoStep

    initpower2B = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5)
    retries = 0
    limit = 5

    if initpower2B < minpower:
        # do a few scans to make sure we are in the closest range possible
        while retries < limit:
            scan.ExecuteNoneModal()
            if scan.IsSuccess == False or SequenceObj.Halt:
                return 0

            # wait to settle
            Utility.DelayMS(500)

            # check return condition
            p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5)
            if p > initpower2B or abs(p - initpower2B) / abs(p) < 0.1:
                break  # power close enough, good alignment
            if p > initpower2B:
                initpower2B = p

            retries += 1
        
        if retries >= limit:
            return 0    # error condition

        if HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5) < minpower:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Minimum first light power not achieved.')
            return 0

    # rescan smaller area
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    # start the scan again
    scan.ExecuteNoneModal()

    if scan.IsSuccess == False or  SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Channel2BDryAlign
# Dry alignment on channel 2B
#-------------------------------------------------------------------------------
def Channel2BDryAlign(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('UpCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # set the 2B LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(False) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(True) == False:
        return 0

    # get the hexapod alignment algorithm
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    # get the fine scan parameters
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').FindByName('Channel2BMonitorSignal')
    scan.Channel = 2
    scan.ExecuteOnce = SequenceObj.AutoStep
    
    # retrieve process parameters
    theoriticalalignedposition = list(map(lambda x: float(x), TestResults.RetrieveTestResult('Side_Vision_Align_Position').split(',')))
    xoffset = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DryAlignGapX').DataItem
    absolutex = theoriticalalignedposition[0] + xoffset

    # move x to final align position directly
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('X', absolutex, Motion.AxisMotionSpeeds.Slow, True) == False:
        return 0

    # do a few scans to make sure we are at the maximum
    initpower2B = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5)
    retries = 0
    limit = 5
    # do a few scans to make sure we are in the closest range possible
    while retries < limit and SequenceObj.Halt == False:
        scan.ExecuteNoneModal()
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # wait to settle
        Utility.DelayMS(500)

        p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5)
        if abs(p - initpower2B) / abs(p) < 0.05:
            break   # power close enough, good alignment
        if p > initpower2B:
           initpower2B = p

        retries += 1

    if retries >= limit or SequenceObj.Halt:
        return 0

    # log the final values
    drymin = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DryAlignMinPower').DataItem
    if HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5) < drymin:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Channel 2B dry align power below specified minium of ' + drymin)
        return 0

    # assume everything is good, log position.
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Channel_2B_Dry_Align_Power', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal')))
    TestResults.AddTestResult('Channel_2B_Dry_Align_X', position[0])
    TestResults.AddTestResult('Channel_2B_Dry_Align_Y', position[1])
    TestResults.AddTestResult('Channel_2B_Dry_Align_Z', position[2])
    TestResults.AddTestResult('Channel_2B_Dry_Align_U', position[3])
    TestResults.AddTestResult('Channel_2B_Dry_Align_V', position[4])
    TestResults.AddTestResult('Channel_2B_Dry_Align_W', position[5])

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# Channel1ADryAlign
# Assume 2B alignment brings 1A close to target, do a quick alignment on channel 1A
#-------------------------------------------------------------------------------
def Channel1ADryAlign(StepName, SequenceObj, TestMetrics, TestResults):

    # set the LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(True) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(True) == False:
        return 0

    # Get the hexapod alignment algorithm and target to 1A
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').FindByName('Channel1AMonitorSignal')
    scan.Channel = 1
    scan.ExecuteOnce = SequenceObj.AutoStep

    # start the algorithm
    scan.ExecuteNoneModal()
    # check status
    if scan.IsSuccess == False or SequenceObj.Halt:
        return 0

    # wait to settle
    Utility.DelayMS(500)

    initpower1A = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal', 5)
    retries = 0
    limit = 5

    # do a few scans to make sure we are in the closest range possible
    while retries < limit:
        scan.ExecuteNoneModal()
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # wait to settle
        Utility.DelayMS(500)

        # check return condition
        p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal', 5)
        if p > initpower1A or abs(p - initpower1A) / abs(p) < 0.1:
            break  # power close enough, good alignment
        if p > initpower1A:
            initpower1A = p

        retries += 1
        
    if retries >= limit:
        return 0    # error condition

    # 1A power must be within some value of 2B or it's no good
    drypower2B = float(TestResults.RetrieveTestResult('Channel_2B_Dry_Align_Power'))
    drypower1A = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal', 5)
    if drypower1A < drypower2B and (drypower2B - drypower1A) / drypower2B > 0.5:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Channel 1A dry align power too low compared to 2B.')
        return 0

    # assume everything is good, log position.
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Channel_1A_Dry_Align_Power', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal')))
    TestResults.AddTestResult('Channel_1A_Dry_Align_X', position[0])
    TestResults.AddTestResult('Channel_1A_Dry_Align_Y', position[1])
    TestResults.AddTestResult('Channel_1A_Dry_Align_Z', position[2])
    TestResults.AddTestResult('Channel_1A_Dry_Align_U', position[3])
    TestResults.AddTestResult('Channel_1A_Dry_Align_V', position[4])
    TestResults.AddTestResult('Channel_1A_Dry_Align_W', position[5])

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# MoveLaserSafe
# Move laser diode to safe height before epoxy
#-------------------------------------------------------------------------------
def MoveLaserSafe(StepName, SequenceObj, TestMetrics, TestResults):

    # turn off the laser diodes
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(False) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(False) == False:
        return 0

    # here we want to move away in X and then Z slowly
    xsafe = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PostDryAlignSafeXOffset').DataItem
    zsafe = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PostDryAlignSafeZOffset').DataItem

    HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisRelative('X', xsafe, Motion.AxisMotionSpeeds.Slow, True)
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisRelative('Z', zsafe, Motion.AxisMotionSpeeds.Slow, True)

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# ApplyEpoxy
# Dispense epoxy onto the die epoxy trenches
#-------------------------------------------------------------------------------
def ApplyEpoxy(StepName, SequenceObj, TestMetrics, TestResults):

    # get and apply epoxy
    if PickAndPlace.Instance.ApplyEpoxyOnSubmount(1) == False:
        return 0
    if PickAndPlace.Instance.ApplyEpoxyOnSubmount(2) == False:
        return 0

    if SequenceObj.Halt:
        return 0

    # take a snap shot
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Assembly_SN'))
    Utility.CreateDirectory(dir)
    PickAndPlace.Instance.PostEpoxyDispenseInspect(IO.Path.Combine(dir, 'PostEpoxyDispense.jpg'))

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# EpoxyWhet
# Slowly lowers the diode into the epoxy pool
#-------------------------------------------------------------------------------
def EpoxyWhet(StepName, SequenceObj, TestMetrics, TestResults):

    # move back to the aligned position in certain order
    if PickAndPlace.Instance.HoverDiodeOnSubmount() == False:
        return 0

    # Here is a hack...
    # Close the epoxy shield before we start realigning
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldOut').SetOutputValue(False)
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldIn').SetOutputValue(True)

    x = float(TestResults.RetrieveTestResult('Channel_1A_Dry_Align_X'))
    y = float(TestResults.RetrieveTestResult('Channel_1A_Dry_Align_Y'))
    z = float(TestResults.RetrieveTestResult('Channel_1A_Dry_Align_Z'))
    u = float(TestResults.RetrieveTestResult('Channel_1A_Dry_Align_U'))
    v = float(TestResults.RetrieveTestResult('Channel_1A_Dry_Align_V'))
    w = float(TestResults.RetrieveTestResult('Channel_1A_Dry_Align_W'))
    whet = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetZGap').DataItem

    # first rotation
    if HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxesAbsolute(Array[String](['U', 'V', 'W']), Array[float]([u, v, w]), Motion.AxisMotionSpeeds.Normal, True) == False:
        return 0

    # then Y
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Y', y, Motion.AxisMotionSpeeds.Normal, True) == False:
        return 0

    # then Z, with whetting
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Z', z - whet, Motion.AxisMotionSpeeds.Normal, True) == False:
        return 0

    # slowly move down to aligned Z in 2um increments
    moved = 0.002
    while moved < whet:
        if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisRelative('Z', 0.002, Motion.AxisMotionSpeeds.Slow, True) == False:
            return 0
        moved += 0.002

    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Z', z, Motion.AxisMotionSpeeds.Slow, True) == False:
        return 0

    # finally X
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('X', x, Motion.AxisMotionSpeeds.Slow, True) == False:
        return 0

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# ChannelsBalancedWetAlign
# Wet align both channels again before UV cure
#-------------------------------------------------------------------------------
def ChannelsBalancedWetAlign(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('UpCamera').Live(True)

    # set the LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(True) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(True) == False:
        return 0

    # make sure epoxy shield is closed before we start realigning
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldOut').SetOutputValue(False)
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldIn').SetOutputValue(True)

    # get the hexapod alignment algorithm
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    # get the fine scan parameters
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodBalanceScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodBalanceScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodBalanceScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodBalanceScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').FindByName('Channel2BMonitorSignal')
    scan.Channel = 2
    scan.ExecuteOnce = SequenceObj.AutoStep

    # start the algorithm
    scan.ExecuteNoneModal()
    # check status
    if scan.IsSuccess == False or SequenceObj.Halt:
        return 0

    # do a few scans to make sure we are at the maximum
    initpower2B = float(TestResults.RetrieveTestResult('Channel_2B_Dry_Align_Power'))
    p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal')
    retries = 0
    limit = 5
    # get the maximum loss from dry align
    maxlossratio = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'WetAlignMaximumPowerLossRatio').DataItem

    # do a few scans to make sure we are in the closest range possible
    while p < initpower2B and abs(p - initpower2B) / abs(initpower2B) > maxlossratio and retries < limit:
        scan.ExecuteNoneModal()
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal')
        retries += 1

    if retries >= limit:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to recover channel 2B dry align power.')
        return 0

    # assume everything is good, log position.
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Channel_2B_Wet_Align_Power', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal')))
    TestResults.AddTestResult('Channel_2B_Wet_Align_X', position[0])
    TestResults.AddTestResult('Channel_2B_Wet_Align_Y', position[1])
    TestResults.AddTestResult('Channel_2B_Wet_Align_Z', position[2])
    TestResults.AddTestResult('Channel_2B_Wet_Align_U', position[3])
    TestResults.AddTestResult('Channel_2B_Wet_Align_V', position[4])
    TestResults.AddTestResult('Channel_2B_Wet_Align_W', position[5])

    # switch to channel 1A
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').FindByName('Channel1AMonitorSignal')
    scan.Channel = 1
    scan.ExecuteOnce = SequenceObj.AutoStep

    # start the algorithm
    scan.ExecuteNoneModal()
    # check status
    if scan.IsSuccess == False or SequenceObj.Halt:
        return 0

    # check the final power from 1A
    initpower1A = float(TestResults.RetrieveTestResult('Channel_1A_Dry_Align_Power'))
    p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal')
    retries = 0

    # do a few scans to make sure we are in the closest range possible
    while p < initpower1A and abs(p - initpower1A) / abs(initpower1A) > maxlossratio and retries < limit:
        scan.ExecuteNoneModal()
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal')
        retries += 1

    if retries >= limit:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to recover channel 1A dry align power.')
        return 0

    # assume everything is good, log position.
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Channel_1A_Wet_Align_Power', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal')))
    TestResults.AddTestResult('Channel_1A_Wet_Align_X', position[0])
    TestResults.AddTestResult('Channel_1A_Wet_Align_Y', position[1])
    TestResults.AddTestResult('Channel_1A_Wet_Align_Z', position[2])
    TestResults.AddTestResult('Channel_1A_Wet_Align_U', position[3])
    TestResults.AddTestResult('Channel_1A_Wet_Align_V', position[4])
    TestResults.AddTestResult('Channel_1A_Wet_Align_W', position[5])

    # split the Y and Z move there
    midY = (float(TestResults.RetrieveTestResult('Channel_2B_Wet_Align_Y')) + float(TestResults.RetrieveTestResult('Channel_1A_Wet_Align_Y'))) / 2
    midZ = (float(TestResults.RetrieveTestResult('Channel_2B_Wet_Align_Z')) + float(TestResults.RetrieveTestResult('Channel_1A_Wet_Align_Z'))) / 2

    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Y', midY, Motion.AxisMotionSpeeds.Slow, True) == False:
        return 0

    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Z', midZ, Motion.AxisMotionSpeeds.Slow, True) == False:
        return 0

    # log the final values
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Final_Align_Power_Channel_1A', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal')))
    TestResults.AddTestResult('Final_Align_Power_Channel_2B', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal')))
    TestResults.AddTestResult('Final_Align_X', position[0])
    TestResults.AddTestResult('Final_Align_Y', position[1])
    TestResults.AddTestResult('Final_Align_Z', position[2])
    TestResults.AddTestResult('Final_Align_U', position[3])
    TestResults.AddTestResult('Final_Align_V', position[4])
    TestResults.AddTestResult('Final_Align_W', position[5])

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# UVCure
# UV cure the epoxy bond
#-------------------------------------------------------------------------------
def UVCure(StepName, SequenceObj, TestMetrics, TestResults):

    # set the LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(True) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(True) == False:
        return 0

     # make sure epoxy shield is closed before we start realigning
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldOut').SetOutputValue(False)
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldIn').SetOutputValue(True)

    # get the uv profile
    profile = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'UVCureStepProfiles').DataItem
    # this is a hack, here we assume there is only one UV step. 
    # get the UV time from the first step in order to display count down timer
    uvtime = float(TestMetrics.GetTestMetricItem('UVCureStepProfileParameters', profile).DataItem.split(',')[0].split(':')[0])
    # log the profile used
    TestResults.AddTestResult('UV_Cure_Profile', profile)
    
    # create collection to track UV power
    UVPowerTracking = List[Array[float]]()
    stopwatch = Stopwatch()
    stopwatch.Start()

    # create the delegate for the UV cure function
    def LogPower(i):
        UVPowerTracking.Add(Array[float]([round(float(stopwatch.ElapsedMilliseconds) / 1000, 1), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal'), 5), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal'), 5)]))
        Utility.ShowProcessTextOnMainUI('UV cure time ' + str(uvtime - int(stopwatch.ElapsedMilliseconds / 1000)) + ' seconds remaining.')

    # start UV exposure
    ret = HardwareFactory.Instance.GetHardwareByName('UVSource').StartStepUVExposures(TestMetrics.GetTestMetricItem('UVCureStepProfileParameters', profile).DataItem, '', Action[int](LogPower))

    # stop timer when UV done
    stopwatch.Stop()

    # Save process values
    TestResults.AddTestResult('Channel_1A_Post_UV_Cure_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal', 5), 6))
    TestResults.AddTestResult('Channel_2B_Post_UV_Cure_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5), 6))

    # save uv cure power tracking
    TestResults.SaveArrayResultsToStorage(TestResults.RetrieveTestResult('Assembly_SN'), 'UVCureChannelPowers', 'Elapsed Time(s),Chan 1A Signal(V),Chan 2B Signal(V)', UVPowerTracking)
    Utility.ShowProcessTextOnMainUI()

    if not ret or SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# Unload
# Release gripper and unload die
#-------------------------------------------------------------------------------
def Unload(StepName, SequenceObj, TestMetrics, TestResults):

    # open gripper and wait
    HardwareFactory.Instance.GetHardwareByName('GripperControl').SetCurrentLevels(TestMetrics.GetTestMetricItem('PickAndPlaceParameters', 'GripperDriveCurrentSetting').DataItem)
    if HardwareFactory.Instance.GetHardwareByName('GripperControl').SetSourceEnabledStates(True) == False:
        return 0

    Utility.DelayMS(TestMetrics.GetTestMetricItem('PickAndPlaceParameters', 'GripperOpenDelay').DataItem)

    # measure post release power
    TestResults.AddTestResult('Channel_1A_Post_Release_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal', 5), 6))
    TestResults.AddTestResult('Channel_2B_Post_Release_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5), 6))

    # turn off LDDs
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(False) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(False) == False:
        return 0

    # release diode
    if PickAndPlace.Instance.ReleaseLaserDiode() == False:
        return 0

    # Open the epoxy shield 
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldOut').SetOutputValue(True)
    HardwareFactory.Instance.GetHardwareByName('PressureControl').FindByName('EpoxyShieldIn').SetOutputValue(False)

    # move the load position
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetHardwareStateTree().ActivateState('Load')
    PickAndPlace.Instance.ReleaseSubmount()

    TestResults.AddTestResult('End_Time', DateTime.Now)

    if SequenceObj.Halt:
        return 0

    return 1
