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

    TestResults.ClearAllTestResult();

    Utility.DelayMS(2000);
    if Stop:
        return 0

    pivot = TestMetrics.GetTestMetricItem(SequenceName, 'InitialPivotPoint').DataItem
    TestResults.AddTestResult('Pivot', pivot);

    Utility.DelayMS(2000);
    if Stop:
        return 0

    TestResults.AddTestResult('Step2Result', 999);
    LogHelper.Log(StepName, LogEventSeverity.Alert, 'Step1 done')
        
    #Must always return an integer. 0 = failure, everythingthing else = success
    return 1

#-------------------------------------------------------------------------------
# SelectDie
# Select the die that was processed previously
#-------------------------------------------------------------------------------
def SelectDie(StepName, SequenceObj, TestMetrics, TestResults):
    #reset the positions
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetHardwareStateTree().ActivateState('Load');

    #Let operator choose a serial number from previous run
    #get all the serial numbers on the system and put them in a combobox dialog
    sn = '';
    ret = UserFormInputDialog.ShowDialog('Select unit to measure:', 'Select the assembly number for post temp cycle measure:', False, list(map(lambda x: IO.Path.GetFileName(x), IO.Directory.GetDirectories(TestResults.OutputDestinationConfiguration))))
    if ret == True:
        sn = UserFormInputDialog.ReturnValue
    else:
        return 0

    #load the assembly data
    if TestResults.LoadTestResultsFromStorage(sn) == False:
        LogHelper.Log(SequenceObj.ProcessSequenceName, Utility.LogEventSeverity.Warning, 'Loading build data for ' + UserFormInputDialog.ReturnValue + ' failed.')
        return 0

    TestResults.AddTestResult('Post_Temp_Cycle_Measure_Start_Time', DateTime.Now);
    TestResults.AddTestResult('Post_Temp_Cycle_Measure_Operator', UserManager.CurrentUser.Name);

    return 1

#-------------------------------------------------------------------------------
# ProbeAndMeasure
# Probe the laser diode and turn on laser power. Measure the IFF values
#-------------------------------------------------------------------------------
def ProbeAndMeasure(StepName, SequenceObj, TestMetrics, TestResults):
    if PickAndPlace.Instance.PostAttachProbeDiode() == False:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to probe laser diode.')
        PickAndPlace.Instance.ReleaseLaserDiode()
        return 0

    #turn on LDDS
    LDDCurr = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LDDDriveCurrentLow').DataItem
    HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetLDCurrentLevel(LDDCurr)
    HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetLDCurrentLevel(LDDCurr)

    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(True) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(True) == False:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Failed to turn on laser diode. Please check laser diode probe contacts.')
        return 0

    TestResults.AddTestResult('Channel_1A_Post_Temp_Cycle_LDD_Current_mA', LDDCurr)
    TestResults.AddTestResult('Channel_2B_Post_Temp_Cycle_LDD_Current_mA', LDDCurr)

    #measure and record
    TestResults.AddTestResult('Channel_1A_Post_Temp_Cycle_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel1AMonitorSignal', 5), 6))
    TestResults.AddTestResult('Channel_2B_Post_Temp_Cycle_Power', round(HardwareFactory.Instance.GetHardwareByName('ChannelsAnalogSignal').ReadValue('Channel2BMonitorSignal', 5), 6))

    return 1

#-------------------------------------------------------------------------------
# Unload
# Turn off the laser and retract the probe
#-------------------------------------------------------------------------------
def Unload(StepName, SequenceObj, TestMetrics, TestResults):

    #turn off LDDs
    if HardwareFactory.Instance.GetHardwareByName('LDDChannel1A').SetCurrentSourceEnable(False) == False or HardwareFactory.Instance.GetHardwareByName('LDDChannel2B').SetCurrentSourceEnable(False) == False:
        return 0

    #move the load position
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetHardwareStateTree().ActivateState('Load')

    #close gripper
    HardwareFactory.Instance.GetHardwareByName('GripperControl').SetSourceEnabledStates(False)
    #release submount
    PickAndPlace.Instance.ReleaseSubmount()

    TestResults.AddTestResult('Post_Temp_Cycle_Measure_End_Time', DateTime.Now)

    return 1



