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
    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Load loopback type alignment
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def LoadLoopbackDie(StepName, SequenceObj, TestMetrics, TestResults):

    loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
    fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem

    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

    #release vacuum
    # HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)

    # Wait for load complete and get serial number
    # possibly using a barcode scanner later    
    ret = UserFormInputDialog.ShowDialog('Load board', 'Please load board (wave guides to the left) and enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Board_SN', UserFormInputDialog.ReturnValue)
    else:
        return 0

    ret = UserFormInputDialog.ShowDialog('Load FAU/MPO', 'Please load FAU/MPO and enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('MPO_SN', UserFormInputDialog.ReturnValue)
        HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
    else:
        return 0

    ret = UserFormInputDialog.ShowDialog('Enter assembly ID', 'Please enter assembly serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
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

    # enter chan 1 initial powers
    if 'Chan1InputPower' in SequenceObj.ProcessPersistentData:
        UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['ChanTopInputPower']
    else:
        UserFormInputDialog.ReturnValue = ''

    ret = UserFormInputDialog.ShowDialog('Top chan optical launch power', 'Please enter top channel launch power (dBm):', True)
    if ret == True:
        try:
            p = float(UserFormInputDialog.ReturnValue)
            SequenceObj.ProcessPersistentData['Chan1InputPower'] = UserFormInputDialog.ReturnValue
            TestResults.AddTestResult('Optical_Input_Power_Top_Outer_Chan', p)
        except:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Invalid entry. Please enter a valid number.')
            return 0
    else:
        return 0

    # enter chan 8 initial powers
    if 'Chan8InputPower' in SequenceObj.ProcessPersistentData:
        UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['Chan8InputPower']
    else:
        UserFormInputDialog.ReturnValue = ''

    ret = UserFormInputDialog.ShowDialog('Bottom chan optical launch power', 'Please enter bottom channel launch power (dBm):', True)
    if ret == True:
        try:
            p = float(UserFormInputDialog.ReturnValue)
            SequenceObj.ProcessPersistentData['Chan8InputPower'] = UserFormInputDialog.ReturnValue
            TestResults.AddTestResult('Optical_Input_Power_Bottom_Outer_Chan', p)
        except:
            LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Invalid entry. Please enter a valid number.')
            return 0
    else:
        return 0

    if SequenceObj.Halt:
        return 0
    else:
        return 1


#-------------------------------------------------------------------------------
# Load PD
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def LoadPDDie(StepName, SequenceObj, TestMetrics, TestResults):

    loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
    fauvac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'FAUVaccumPortName').DataItem

    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)

    #release vacuum
    # HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)

    # Wait for load complete and get serial number
    # possibly using a barcode scanner later    
    ret = UserFormInputDialog.ShowDialog('Load board', 'Please board (wave guides to the left) and enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Board_SN', UserFormInputDialog.ReturnValue)
    else:
        return 0

    ret = UserFormInputDialog.ShowDialog('Load FAU/MPO', 'Please load FAU/MPO and enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('MPO_SN', UserFormInputDialog.ReturnValue)
        HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, True)
    else:
        return 0

    ret = UserFormInputDialog.ShowDialog('Enter assembly ID', 'Please enter assembly serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
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

    if SequenceObj.Halt:
        return 0
    else:
        return 1


#-------------------------------------------------------------------------------
# InitializeRepeatability
# Clears up test data and other prep work before process starts
# For repeatablity test use only
#-------------------------------------------------------------------------------
def InitializeRepeatability(StepName, SequenceObj, TestMetrics, TestResults):
    
    totalruns = 30
    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # clear the output data
    Utility.ShowProcessTextOnMainUI() # clear message

    TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
    TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())
    TestResults.AddTestResult('Assembly_SN','RepeatabilityTest')

    # inject the required fields, if not there already
    try:
        runnum = TestResults.RetrieveTestResult('CurrentRunNumber')
        runnum = runnum + 1
        TestResults.AddTestResult('CurrentRunNumber', runnum)
        if runnum > totalruns:
            if LogHelper.AskContinue('Repeatability test done.'):
                return 0
            else:
                TestResults.AddTestResult('CurrentRunNumber', 1)
                return 1
    except:
        TestResults.AddTestResult('CurrentRunNumber', 1)

    return 1

#-------------------------------------------------------------------------------
# Load
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def Load(StepName, SequenceObj, TestMetrics, TestResults):

    loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'

    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

    # Wait for load complete and get serial number
    # possibly using a barcode scanner later
    ret = UserFormInputDialog.ShowDialog('Load board', 'Please load board and then enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Assembly_SN', UserFormInputDialog.ReturnValue)
    else:
        return 0

    ret = UserFormInputDialog.ShowDialog('Load MPO', 'Please load MPO and enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('MPO_SN', UserFormInputDialog.ReturnValue)
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

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# OptimizeRollAngle
# Find the optimal roll angle for loop back on both channels
# NOTE: This routine is designed for loop back, not PD signal
#-------------------------------------------------------------------------------
def OptimizeRollAngle(StepName, SequenceObj, TestMetrics, TestResults):
    
    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # declare variables we will use
    retries = 0
    limit = 3

    # get the alignment algorithms
    hscan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    nscan = Alignments.AlignmentFactory.Instance.SelectAlignment('NanocubeRasterScan')
    optimalrollsearch = Alignments.AlignmentFactory.Instance.SelectAlignment('SimplexMaximumSearch')

    # get hexapod search parameters from recipe file
    hscan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis1').DataItem
    hscan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodRoughScanAxis2').DataItem
    hscan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    hscan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    hscan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    hscan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem
    hscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
    
    # get nanocube scan parameters
    nscan.Axis1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis1').DataItem
    nscan.Axis2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanAxis2').DataItem
    # we are working in um when dealing with Nanocube
    nscan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanRange1').DataItem * 1000
    nscan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanRange2').DataItem * 1000
    # start at the middle position
    nscan.Axis1Position = 50
    nscan.Axis2Position = 50
    nscan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanVelocity').DataItem * 1000
    nscan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'NanocubeScanFrequency').DataItem
    nscan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
    hscan.Channel = nscan.Channel = 1
    hscan.ExecuteOnce = nscan.ExecuteOnce = SequenceObj.AutoStep

    # Load the simplex search parameter to optimize roll angle
    optimalrollsearch.NMax = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollNMax').DataItem
    optimalrollsearch.RTol = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollRTol').DataItem
    optimalrollsearch.MinRes = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMinRes').DataItem
    optimalrollsearch.Lambda = (str)(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollLambda').DataItem)
    optimalrollsearch.MaxRestarts = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxRestarts').DataItem
    optimalrollsearch.MaxTinyMoves = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'RollMaxTinyMoves').DataItem
    optimalrollsearch.ExecuteOnce = SequenceObj.AutoStep

    startangle = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('U')   # get the starting pitch angle
    # Now we will start the optimal roll angle search using the Nanocube for speed and accuracy
    # define the delegate for algo feedback
    def EvalRoll(a):
        # tweak the roll angle then optimize power with Nanocube
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('U', startangle + a[0], Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)
        # scan for optimal
        hscan.ExecuteNoneModal()

        # wait to settle
        Utility.DelayMS(500)
        '''
        # double check Nanocube position and make sure it's always within the motion range
        axis1offset = (float)(HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(nscan.Axis1) - nscan.Axis1Position)
        axis2offset = (float)(HardwareFactory.Instance.GetHardwareByName('Nanocube').GetAxisPosition(nscan.Axis2) - nscan.Axis2Position)

        if Math.Abs(axis1offset) >= nscan.Range1 / 2 or Math.Abs(axis2offset) >= nscan.Range2 / 2:
            if Math.Abs(axis1offset) > nscan.Range1 / 2:
                HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisRelative(nscan.Axis1, -axis1offset, Motion.AxisMotionSpeeds.Normal, True)
                HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative(nscan.Axis1, axis1offset / 1000, Motion.AxisMotionSpeeds.Normal, True)

            if Math.Abs(axis2offset) > nscan.Range2 / 2:
                HardwareFactory.Instance.GetHardwareByName('Nanocube').MoveAxisRelative(nscan.Axis2, -axis2offset, Motion.AxisMotionSpeeds.Normal, True)
                HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative(nscan.Axis2, axis2offset / 1000, Motion.AxisMotionSpeeds.Normal, True)

                # wait to settle
            Utility.DelayMS(500)

            # optimize again
            hscan.ExecuteNoneModal()

            # wait to settle
            Utility.DelayMS(500)
        '''

        return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)  # we want to maximize the bottom channel power since doing so means we are aligned in roll

    # connect the call back function
    optimalrollsearch.EvalFunction = Func[Array[float],float](EvalRoll)
    # start roll optimization
    optimalrollsearch.ExecuteNoneModal()

    if optimalrollsearch.IsSuccess == False or  SequenceObj.Halt:
        return 0

    # wait to settle
    Utility.DelayMS(500)

    #save the final data for bottom channel
    position = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('First_Light_Top_Channel_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6))
    TestResults.AddTestResult('First_Light_Bottom_Channel_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6))
    TestResults.AddTestResult('First_Light_Hexapod_X', position[0])
    TestResults.AddTestResult('First_Light_Hexapod_Y', position[1])
    TestResults.AddTestResult('First_Light_Hexapod_Z', position[2])
    TestResults.AddTestResult('First_Light_Hexapod_U', position[3])
    TestResults.AddTestResult('First_Light_Hexapod_V', position[4])
    TestResults.AddTestResult('First_Light_Hexapod_W', position[5])

    return 1

#-------------------------------------------------------------------------------
# ApplyEpoxyRepeatability
# Manually apply epoxy and establish contact point
# For repeatability test use only. Will not actually dispense epoxy
#-------------------------------------------------------------------------------
def ApplyEpoxyRepeatability(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # Ask operator to apply epoxy. Use automation later
    # if not LogHelper.AskContinue('Apply epoxy. Click Yes when done.'):
    #    return 0

    # open to whet epoxy
    whetgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetGap').DataItem
    # move to epoxy whet position
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -whetgap, Motion.AxisMotionSpeeds.Slow, True)
    # wait a few seconds
    Utility.DelayMS(TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyWhetTime').DataItem)
    # back to zero position
    zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('X', zero, Motion.AxisMotionSpeeds.Slow, True)

    # do a contact to establish True bond gap
    # start move incrementally until force sensor detect contact
    # first zero out the force sensr
    HardwareFactory.Instance.GetHardwareByName('Hexapod').ZeroForceSensor()
    # get initial force
    forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
    startforce = forcesensor.ReadValueImmediate()
    # start force monitor
    threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
    backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
    bondgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyBondGap').DataItem
    # Monitor force change
    while (forcesensor.ReadValueImmediate() - startforce) < threshold:
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', 0.001, Motion.AxisMotionSpeeds.Slow, True)
        Utility.DelayMS(5)
        # check for user interrupt
        if SequenceObj.Halt:
            return 0

    # found contact point, back off set amount
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', backoff, Motion.AxisMotionSpeeds.Normal, True)
    # put the required bondgap
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', -bondgap, Motion.AxisMotionSpeeds.Normal, True)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# DriftMonitor
# Save drift data to the file
# For repeatability test use only. Save results to file
#-------------------------------------------------------------------------------
def DriftMonitor(StepName, SequenceObj, TestMetrics, TestResults):

    # Set up feedback variable
    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    chan1 = 0.0
    chan2 = 0.0
    # Set up file name
    run =  TestResults.RetrieveTestResult('CurrentRunNumber')
    filename = 'C:\Aligner\Data\DryAlignDriftMonitor_%d.csv.' % run
    f = open(filename, 'a')    
    # set up timer
    start = DateTime.Now
    while (DateTime.Now - start).Seconds < 600:
        hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()        
        # check for feedback source
        if pm is not None and pm.InitializeState == HardwareInitializeState.Initialized:
            power = pm. ReadPowers()
            chan1 = power.Item2[0]
            chan2 = power.Item2[1]
        else:
            chan1 = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)
            chan2 = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal', 5)
            
        f.write('%d,%f,%f,%f,%f,%f,%f,%f,%f\r\n' % ((DateTime.Now - start).Seconds,chan1,chan2,hposition[0],hposition[1],hposition[2],hposition[3],hposition[4],hposition[5]))
        # wait 5 seconds
        Utility.DelayMS(5000)
        Utility.ShowProcessTextOnMainUI(str((DateTime.Now - start).Seconds) + ' seconds elapsed.')
    f.close()

    Utility.ShowProcessTextOnMainUI()

    return 1

#-------------------------------------------------------------------------------
# FinalizeRepeatability
# Save data to the file
# For repeatability test use only. Save results to file
#-------------------------------------------------------------------------------
def FinalizeRepeatability(StepName, SequenceObj, TestMetrics, TestResults):

    # get the relevant values first
    x = TestResults.RetrieveTestResult('Wet_Align_Hexapod_X')
    y = TestResults.RetrieveTestResult('Wet_Align_Hexapod_Y')
    z = TestResults.RetrieveTestResult('Wet_Align_Hexapod_Z')
    u = TestResults.RetrieveTestResult('Wet_Align_Hexapod_U')
    v = TestResults.RetrieveTestResult('Wet_Align_Hexapod_V')
    w = TestResults.RetrieveTestResult('Wet_Align_Hexapod_W')

    chan1 = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')
    chan2 = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')

    # construct the file name
    filename = 'C:\Aligner\Data\DryAlignRepeatabilityTest.csv.'
    try:
        # append new field if file already exists
        f = open(filename, 'a')        
        f.write('%f,%f,%f,%f,%f,%f,%f,%f\r\n' % (chan1,chan2,x,y,z,u,v,w))
        f.close()
    except:
        # create the file and write the header
        f = open(filename, 'w')
        f.write('Chan1,Chan2,X,Y,Z,U,V,W\r\n')
        f.close()    
        f = open(filename, 'a')
        f.write('%f,%f,%f,%f,%f,%f,%f,%f\r\n' % (chan1,chan2,x,y,z,u,v,w))
        f.close()     

    return 1
