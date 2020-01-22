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
    dievac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'TargetVaccumPortName').DataItem

    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

    #release vacuum
    # HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
    # HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)

    # Wait for load complete and get serial number
    # possibly using a barcode scanner later    
    ret = UserFormInputDialog.ShowDialog('Load GF die', 'Please load die (wave guides to the left) and enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Die_SN', UserFormInputDialog.ReturnValue)
        HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, True)
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
    dievac = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'TargetVaccumPortName').DataItem

    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)

    #release vacuum
    # HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(fauvac, False)
    # HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, False)

    # Wait for load complete and get serial number
    # possibly using a barcode scanner later    
    ret = UserFormInputDialog.ShowDialog('Load GF die', 'Please load die (wave guides to the left) and enter serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Die_SN', UserFormInputDialog.ReturnValue)
        HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(dievac, True)
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
# BalanceWedAlignment
# Balance alignment of the channels in epoxy with pitch sweep optimization
#-------------------------------------------------------------------------------
def SweepOptimizedBalanceWetAlignment(StepName, SequenceObj, TestMetrics, TestResults):

    # turn on the cameras
    HardwareFactory.Instance.GetHardwareByName('DownCamera').Live(True)
    HardwareFactory.Instance.GetHardwareByName('SideCamera').Live(True)

    # get the pitch sweep algo
    scan = Alignments.AlignmentFactory.Instance.SelectAlignment('HexapodRasterScan')
    pitchsweep = Alignments.AlignmentFactory.Instance.SelectAlignment('PitchSweepOptimization')

    # reload sweep parameters
    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationHexapodScanFrequency').DataItem
    scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
    scan.Channel = 1

    Axis = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationAxis').DataItem
    pitchsweep.Axis = Axis
    pitchsweep.MotionStages = HardwareFactory.Instance.GetHardwareByName('Hexapod')
    pitchsweep.StartPosition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationAbsoluteAngleStart').DataItem
    pitchsweep.EndPosition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationAbsoluteAngleEnd').DataItem
    pitchsweep.StepSize = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationStepSize').DataItem
    pitchsweep.FeedbackUnit = 'V'
    pitchsweep.ExecuteOnce = scan.ExecuteOnce = SequenceObj.AutoStep

    # create the pitch feedback delegate function
    def EvalPitch(a):
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute(Axis, a, Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)
        scan.ExecuteNoneModal()
        # wait to settle
        Utility.DelayMS(500)
        return HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal', 5)

    pitchsweep.EvalFunction = Func[float,float](EvalPitch)

    # get the pitch search X pull back distance
    # first perform a pull back, we will need to re-do the contact point again afterwards
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('X', TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PitchOptimizationPullBack').DataItem, Motion.AxisMotionSpeeds.Normal, True)       
    # readjust the pitch pivot point
    zero = TestResults.RetrieveTestResult('Optical_Z_Zero_Position')
    zeropitch = TestResults.RetrieveTestResult('Pitch_Pivot_X')
    offset = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxisPosition('X') - zero
    # HardwareFactory.Instance.GetHardwareByName('Hexapod').PivotPoint['X'] = zeropitch + offset
    # enable the new pivot point
    # HardwareFactory.Instance.GetHardwareByName('Hexapod').ApplyKSDCoordinateSystem('PIVOT')        
    
    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Optimizing hexapod pitch angle.')
    # start sweep
    pitchsweep.ExecuteNoneModal()
    # check result
    if not pitchsweep.IsSuccess or SequenceObj.Halt:
        return 0

    # Re-establish the contact point again
    HardwareFactory.Instance.GetHardwareByName('Hexapod').ZeroForceSensor()
    # get initial force
    forcesensor = HardwareFactory.Instance.GetHardwareByName('ForceSensorIOSource').FindByName('ForceSensor')
    startforce = forcesensor.ReadValueImmediate()
    # start force monitor
    threshold = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'ForceSensorContactThreshold').DataItem
    backoff = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'BackOffFromContactDetection').DataItem
    bondgap = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'EpoxyBondGap').DataItem
    # monitor force change
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

    scan.Range1 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange1').DataItem
    scan.Range2 = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanRange2').DataItem
    scan.Velocity = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanVelocity').DataItem
    scan.Frequency = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'HexapodFineScanFrequency').DataItem

    # set up a loop to zero in on the roll angle
    width = TestResults.RetrieveTestResult('Outer_Channels_Width')
    retries = 0

    LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Alert, 'Balancing channels...')

    while retries < 5 and not SequenceObj.Halt:

        # start the algorithms
        scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('TopChanMonitorSignal')
        scan.Channel = 1
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

         # wait to settle
        Utility.DelayMS(500)

        # remember the final position
        topchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # repeat scan for the second channel
        scan.MonitorInstrument = HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').FindByName('BottomChanMonitorSignal')
        scan.Channel = 2

        # start the algorithms again
        scan.ExecuteNoneModal()
        # check scan status
        if scan.IsSuccess == False or SequenceObj.Halt:
            return 0

        # wait to settle
        Utility.DelayMS(500)

        # get the final position of second channel
        bottomchanpos = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()

        # double check and readjust roll if necessary
        # calculate the roll angle
        h = Math.Atan(Math.Abs(topchanpos[1] - bottomchanpos[1]))
        if h < 1:
           break    # we achieved the roll angle when the optical Z difference is less than 1 um

        # calculate the roll angle
        r = Utility.RadianToDegree(Math.Atan(h / width))
        rollangle = -r
        if topchanpos[2] > bottomchanpos[2]:
           rollangle = -rollangle

        # adjust the roll angle again
        HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisRelative('U', rollangle, Motion.AxisMotionSpeeds.Normal, True)
        # wait to settle
        Utility.DelayMS(500)

        retries += 1
    
    # check stop conditions
    if retries >= 3 or SequenceObj.Halt:
       return 0

    # balanced position
    ymiddle = (topchanpos[1] + bottomchanpos[1]) / 2
    zmiddle = (topchanpos[2] + bottomchanpos[2]) / 2
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Y', ymiddle, Motion.AxisMotionSpeeds.Normal, True)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').MoveAxisAbsolute('Z', zmiddle, Motion.AxisMotionSpeeds.Normal, True)

    # record final wet align hexapod position
    hposition = HardwareFactory.Instance.GetHardwareByName('Hexapod').GetAxesPositions()
    TestResults.AddTestResult('Wet_Align_Hexapod_X', hposition[0])
    TestResults.AddTestResult('Wet_Align_Hexapod_Y', hposition[1])
    TestResults.AddTestResult('Wet_Align_Hexapod_Z', hposition[2])
    TestResults.AddTestResult('Wet_Align_Hexapod_U', hposition[3])
    TestResults.AddTestResult('Wet_Align_Hexapod_V', hposition[4])
    TestResults.AddTestResult('Wet_Align_Hexapod_W', hposition[5])

    # get power based on instrument    
    toppower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('TopChanMonitorSignal'), 6)
    bottompower = round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignals').ReadValue('BottomChanMonitorSignal'), 6)

    pm = HardwareFactory.Instance.GetHardwareByName('Powermeter')
    if pm != None and pm.InitializeState == HardwareInitializeState.Initialized:
        toppower = pm.ReadPowers().Item2[0]
        bottompower = pm.ReadPowers().Item2[1]

    # save process values
    TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan', toppower)
    TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan', bottompower)

    if SequenceObj.Halt:
        return 0
    else:
        return 1

#-------------------------------------------------------------------------------
# Finalize
# Save data to the file
#-------------------------------------------------------------------------------
def Finalize(StepName, SequenceObj, TestMetrics, TestResults):

    # get process values
    drytop = TestResults.RetrieveTestResult('Dry_Align_Power_Top_Outer_Chan')
    drybottom = TestResults.RetrieveTestResult('Dry_Align_Power_Bottom_Outer_Chan')
    wettop = TestResults.RetrieveTestResult('Wet_Align_Power_Top_Outer_Chan')
    wetbottom = TestResults.RetrieveTestResult('Wet_Align_Power_Bottom_Outer_Chan')
    uvtop = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Top_Outer_Chan')
    uvbottom = TestResults.RetrieveTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan')
    releasetop = TestResults.RetrieveTestResult('Post_Release_Power_Top_Outer_Chan')
    releasebottom = TestResults.RetrieveTestResult('Post_Release_Power_Bottom_Outer_Chan')

    # save process values
    TestResults.AddTestResult('Wet_Align_Power_Top_Outer_Chan_Loss', round(drytop - wettop, 6))
    TestResults.AddTestResult('Wet_Align_Power_Bottom_Outer_Chan_Loss', round(drybottom - wetbottom, 6))

    TestResults.AddTestResult('Post_UV_Cure_Power_Top_Outer_Chan_Loss', round(wettop - uvtop, 6))
    TestResults.AddTestResult('Post_UV_Cure_Power_Bottom_Outer_Chan_Loss', round(wetbottom - uvbottom, 6))

    TestResults.AddTestResult('Post_Release_Power_Top_Outer_Chan_Loss', round(uvtop - releasetop, 6))
    TestResults.AddTestResult('Post_Release_Power_Bottom_Outer_Chan_Loss', round(uvbottom - releasebottom, 6))

    #check user comment
    if TestResults.IsTestResultExists('Comment') == False:
        if Station.Instance.UserComment:
            TestResults.AddTestResult('Comment', Station.Instance.UserComment)
    else:
        if Station.Instance.UserComment:
            TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult('Comment') + ' ' + Station.Instance.UserComment)
        else:
            TestResults.AddTestResult('Comment', TestResults.RetrieveTestResult('Comment'))

    #save the data file
    TestResults.SaveTestResultsToStorage(TestResults.RetrieveTestResult('Assembly_SN'))

    return 1
