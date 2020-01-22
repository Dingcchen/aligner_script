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

    # clear the output data
    TestResults.ClearAllTestResult()
    Utility.ShowProcessTextOnMainUI() # clear message

    TestResults.AddTestResult('Start_Time', DateTime.Now)
    TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
    TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())

    # Open the epoxy shield 
    HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl').SetOutputValue('EpoxyShieldStates', 'Out')
    # Raise the epoxy tool
    HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl').SetOutputValue('EpoxyToolStates', 'Up')

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
    if PickAndPlace.PickAndPlace.Instance.CheckSubmountTray() == False or PickAndPlace.PickAndPlace.Instance.CheckLaserDiodeTray() == False or PickAndPlace.PickAndPlace.Instance.CheckEpoxyTray() == False:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Material depleted. Please reload.')
        return 0

    if not LogHelper.AskContinue('Load board and move board probe card in contact with pads. Click OK when done, No to abort.'):
        return 0

    if not LogHelper.AskContinue('Raise LSA probe card to LSA pick up height. Click OK when done, No to abort.'):
        return 0

    ret = UserFormInputDialog.ShowDialog('Enter board serial number', 'Please enter board serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Board_SN', UserFormInputDialog.ReturnValue)
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
def LocateBoard(StepName, SequenceObj, TestMetrics, TestResults):

    # snap an image of the die
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Board_SN'))
    Utility.CreateDirectory(dir)
    PickAndPlace.PickAndPlace.Instance.SubmountInspect(IO.Path.Combine(dir, 'BoardTop.jpg'))

    ret = PickAndPlace.PickAndPlace.Instance.GetNextSubmount(True)

    if ret == False or SequenceObj.Halt == True:
        return 0

    return 1

#-------------------------------------------------------------------------------
# PickUpLaserDiode
# Use vision to find the next laser diode and pick it up
#-------------------------------------------------------------------------------
def PickUpLSA(StepName, SequenceObj, TestMetrics, TestResults):

    # generate the laser diode file name
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Board_SN'))
    Utility.CreateDirectory(dir)
    filename = IO.Path.Combine(dir, 'LSATop.jpg')

    while PickAndPlace.PickAndPlace.Instance.CheckLaserDiodeTray() and SequenceObj.Halt == False:
        # snap an image of the laser diode
        PickAndPlace.PickAndPlace.Instance.DiodePrePickInspect(filename)

        if PickAndPlace.PickAndPlace.Instance.GetNextLaserDiode() == True:
            
            # save the bottom image
            if PickAndPlace.PickAndPlace.Instance.DiodePostPickInspect(IO.Path.Combine(dir, 'LSABottom.jpg')) == False:
                LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to find the location of the LSA on gripper.')
                return 0
            
            # log sn in status
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'LSA is at ' + '{:4.2f}'.format(PickAndPlace.PickAndPlace.Instance.TheLaserDiode.PositionAngle) + ' degree angle.')
            return 1

    # tray depleted
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Laser diode tray depleted. Please refill to resume process.')
    return 0

#-------------------------------------------------------------------------------
# PickUpLaserDiode
# Use vision to find the next laser diode and pick it up
#-------------------------------------------------------------------------------
def TestLSAProbe(StepName, SequenceObj, TestMetrics, TestResults):

    # Ask operator to lower LSA probe pin
    if LogHelper.AskContinue('Lower LSA probe card until pins are in contact with LSA. Click OK when done, No to abort.'):
         # turn on to test diode probe connection
        if HardwareFactory.Instance.GetHardwareByName('LDD').SetCurrentSourceEnable(True):
            TestResults.AddTestResult('Laser_SN', PickAndPlace.PickAndPlace.Instance.TheLaserDiode.PartID)
            return 1
        else:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'LSA failed to turn on. Please check the probe pin contact.')
            # bad contact, return the diode
            HardwareFactory.Instance.GetHardwareByName('LDD').SetCurrentSourceEnable(False)

    return 0

#-------------------------------------------------------------------------------
# PlaceLaserDiode
# Place the LSA on die for alignment
#-------------------------------------------------------------------------------
def PlaceLSAOnBoard(StepName, SequenceObj, TestMetrics, TestResults):

    if PickAndPlace.PickAndPlace.Instance.PlaceDiodeOnSubmount() == False:
        return 0

    # retrieve current position
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    # retrieve the vision LSA to WG gap
    visiongap = PickAndPlace.PickAndPlace.Instance.GetLSAtoDieAlignedOpticalZGap()

    # get the specified gaps from recipe
    gapx = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DryAlignGapX').DataItem
    gapz = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DryAlignGapZ').DataItem

    # move to achieve the right gap
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Z', position[2] + gapz, Motion.AxisMotionSpeeds.Slow, True) == False:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move motor to target position.')
        return 0

    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('X', position[0] + visiongap - gapx, Motion.AxisMotionSpeeds.Slow, True) == False:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to move motor to target position.')
        return 0

    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Channel_Pre_Dry_Align_X', position[0])
    TestResults.AddTestResult('Channel_Pre_Dry_Align_Y', position[1])
    TestResults.AddTestResult('Channel_Pre_Dry_Align_Z', position[2])

    if SequenceObj.Halt:
        return 0
    
    return 1

#-------------------------------------------------------------------------------
# LSADryAlign
# Dry alignment LSA
#-------------------------------------------------------------------------------
def LSADryAlign(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('UpCamera').Live(True)

    # set the 2B LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDD').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    if not HardwareFactory.Instance.GetHardwareByName('LDD').SetCurrentSourceEnable(True):
        return 0

    # get the hexapod alignment algorithm
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    # get the fine scan parameters
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('MonitorSignal')
    scan.Channel = 1
    scan.ExecuteOnce = SequenceObj.AutoStep
    
    # do a few scans to make sure we are at the maximum
    initpower = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal', 5)
    retries = 0
    limit = 5
    # do a few scans to make sure we are in the closest range possible
    while retries < limit and SequenceObj.Halt == False:
        scan.ExecuteNoneModal()
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # wait to settle
        Utility.DelayMS(500)

        p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal', 5)
        if abs(p - initpower) / abs(p) < 0.05:
            break   # power close enough, good alignment
        if p > initpower:
           initpower = p

        retries += 1

    if retries >= limit or SequenceObj.Halt:
        return 0

    # log the final values
    drymin = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DryAlignMinPower').DataItem
    if HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal', 5) < drymin:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Channel dry align power below specified minium of ' + drymin)
        return 0

    # assume everything is good, log position.
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Channel_Dry_Align_Power', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal')))
    TestResults.AddTestResult('Channel_Dry_Align_X', position[0])
    TestResults.AddTestResult('Channel_Dry_Align_Y', position[1])
    TestResults.AddTestResult('Channel_Dry_Align_Z', position[2])

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# MoveLaserSafe
# Move laser diode to safe height before epoxy
#-------------------------------------------------------------------------------
def MoveLSASafe(StepName, SequenceObj, TestMetrics, TestResults):

    # turn off the laser diodes
    if not HardwareFactory.Instance.GetHardwareByName('LDD').SetCurrentSourceEnable(False):
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
    if PickAndPlace.PickAndPlace.Instance.ApplyEpoxyOnSubmount(1) == False:
        return 0
    if PickAndPlace.PickAndPlace.Instance.ApplyEpoxyOnSubmount(2) == False:
        return 0

    if SequenceObj.Halt:
        return 0

    # take a snap shot
    dir = IO.Path.Combine(TestResults.OutputDestinationConfiguration, TestResults.RetrieveTestResult('Board_SN'))
    Utility.CreateDirectory(dir)
    PickAndPlace.PickAndPlace.Instance.PostEpoxyDispenseInspect(IO.Path.Combine(dir, 'PostEpoxyDispense.jpg'))

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# EpoxyWhet
# Slowly lowers the diode into the epoxy pool
#-------------------------------------------------------------------------------
def EpoxyWhet(StepName, SequenceObj, TestMetrics, TestResults):

    # move back to the aligned position in certain order
    if PickAndPlace.PickAndPlace.Instance.HoverDiodeOnSubmount() == False:
        return 0

    # Close the epoxy shield before we start realigning
    HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl').SetOutputValue('EpoxyShieldStates', 'In')

    y = float(TestResults.RetrieveTestResult('Channel_Dry_Align_Y'))
    z = float(TestResults.RetrieveTestResult('Channel_Dry_Align_Z'))
    whet = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetZGap').DataItem

    # first Y
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Y', y, Motion.AxisMotionSpeeds.Normal, True) == False:
        return 0

    # then Z, with whetting
    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Z', z + whet, Motion.AxisMotionSpeeds.Normal, True) == False:
        return 0

    # slowly move down to aligned Z in 2um increments
    moved = 0.002
    while moved < whet:
        if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisRelative('Z', -0.002, Motion.AxisMotionSpeeds.Slow, True) == False:
            return 0
        moved += 0.002

    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('Z', z, Motion.AxisMotionSpeeds.Slow, True) == False:
        return 0

    # finally X
    # we want to move to the final wet align gap instead of dry align gap
    x = float(TestResults.RetrieveTestResult('Channel_Pre_Dry_Align_X'))
    drygap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'DryAlignGapX').DataItem
    wetgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'WetAlignGapX').DataItem
    newx = x + (drygap - wetgap)

    if HardwareFactory.Instance.GetHardwareByName('AxesStageController').MoveAxisAbsolute('X', newx, Motion.AxisMotionSpeeds.Slow, True) == False:
        return 0

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# ChannelsBalancedWetAlign
# Wet align both channels again before UV cure
#-------------------------------------------------------------------------------
def LSAWetAlign(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('UpCamera').Live(True)

    # set the LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDD').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    if not HardwareFactory.Instance.GetHardwareByName('LDD').SetCurrentSourceEnable(True):
        return 0

    # make sure epoxy shield is closed before we start realigning
    HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl').SetOutputValue('EpoxyShieldStates', 'In')

    # get the hexapod alignment algorithm
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    # assume parameter hasn't been changed

    # start the algorithm
    scan.ExecuteNoneModal()
    # check status
    if scan.IsSuccess == False or SequenceObj.Halt:
        return 0

    # do a few scans to make sure we are at the maximum
    initpower = float(TestResults.RetrieveTestResult('Channel_Dry_Align_Power'))
    p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal')
    retries = 0
    limit = 5
    # get the maximum loss from dry align
    maxlossratio = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'WetAlignMaximumPowerLossRatio').DataItem

    # do a few scans to make sure we are in the closest range possible
    while p < initpower and abs(p - initpower) / abs(initpower) > maxlossratio and retries < limit:
        scan.ExecuteNoneModal()
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        p = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal')
        retries += 1

    if retries >= limit:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to recover dry align power.')
        return 0

    # assume everything is good, log position.
    position = HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetAxesPositions()
    TestResults.AddTestResult('Channel_Wet_Align_Power', '{:f}'.format(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal')))
    TestResults.AddTestResult('Channel_Wet_Align_X', position[0])
    TestResults.AddTestResult('Channel_Wet_Align_Y', position[1])
    TestResults.AddTestResult('Channel_Wet_Align_Z', position[2])

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# UVCure
# UV cure the epoxy bond
#-------------------------------------------------------------------------------
def UVCure(StepName, SequenceObj, TestMetrics, TestResults):

    # set the LDD currents and turn it on
    HardwareFactory.Instance.GetHardwareByName('LDD').SetLDCurrentLevel(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem)
    if not HardwareFactory.Instance.GetHardwareByName('LDD').SetCurrentSourceEnable(True):
        return 0

    # make sure epoxy shield is closed before we start UV curing
    HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl').SetOutputValue('EpoxyShieldStates', 'In')

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
        UVPowerTracking.Add(Array[float]([round(float(stopwatch.ElapsedMilliseconds) / 1000, 1), round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal'), 5)]))
        Utility.ShowProcessTextOnMainUI('UV cure time ' + str(uvtime - int(stopwatch.ElapsedMilliseconds / 1000)) + ' seconds remaining.')

    # start UV exposure
    ret = HardwareFactory.Instance.GetHardwareByName('UVSource').StartStepUVExposures(TestMetrics.GetTestMetricItem('UVCureStepProfileParameters', profile).DataItem, '', Action[int](LogPower))

    # stop timer when UV done
    stopwatch.Stop()

    if not ret:
        return 0

    # Save process values
    TestResults.AddTestResult('Channel_Post_UV_Cure_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal', 5), 6))

    # save uv cure power tracking
    TestResults.SaveArrayResultsToStorage(TestResults.RetrieveTestResult('Board_SN'), 'UVCureChannelPowers', 'Elapsed Time(s),Chan Signal(V)', UVPowerTracking)
    Utility.ShowProcessTextOnMainUI()

    if SequenceObj.Halt:
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
    TestResults.AddTestResult('Channel_Post_Release_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('MonitorSignal', 5), 6))

    # turn off LDDs
    if not HardwareFactory.Instance.GetHardwareByName('LDD').SetCurrentSourceEnable(False):
        return 0

    # release diode
    if PickAndPlace.PickAndPlace.Instance.ReleaseLaserDiode() == False:
        return 0

    # Open the epoxy shield 
    HardwareFactory.Instance.GetHardwareByName('MultiStatesIOControl').SetOutputValue('EpoxyShieldStates', 'Out')

    # move the load position
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetHardwareStateTree().ActivateState('Load')

    TestResults.AddTestResult('End_Time', DateTime.Now)

    if SequenceObj.Halt:
        return 0

    return 1

#-------------------------------------------------------------------------------
# Finalize
# Save data to the file
#-------------------------------------------------------------------------------
def Finalize(StepName, SequenceObj, TestMetrics, TestResults):

    #check user comment
    if TestResults.IsTestResultExists('Comment') == False:
        if Station.Instance.UserComment:
            TestResults.AddTestResult('Comment', Station.Instance.UserComment)
    else:
        if Station.Instance.UserComment:
            TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult("Comment") + ' ' + Station.Instance.UserComment)
        else:
            TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult("Comment"))

    #save the data file
    TestResults.SaveTestResultsToStorage(TestResults.RetrieveTestResult('Board_SN'))

    return 1