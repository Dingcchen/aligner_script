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
# Initialize
# Clears up test data and other prep work before process starts
#-------------------------------------------------------------------------------
def Initialize(StepName, SequenceObj, TestMetrics, TestResults):
    #clear the output data
    TestResults.ClearAllTestResult();

    TestResults.AddTestResult('Start_Time', DateTime.Now)
    TestResults.AddTestResult('Operator', UserManager.CurrentUser.Name)
    TestResults.AddTestResult('Software_Version', Utility.GetApplicationVersion())

    return 1

#-------------------------------------------------------------------------------
# CheckProbe
# Ask the user to visually check probe contact to the die
#-------------------------------------------------------------------------------
def CheckProbe(StepName, SequenceObj, TestMetrics, TestResults):

    #reset the positions
    HardwareFactory.Instance.GetHardwareByName('AxesStageController').GetHardwareStateTree().ActivateState('Load')

    #Ask operator to adjust probe
    if LogHelper.AskContinue("Adjust probe until pins are in contact with pads. Click Yes when done, No to abort.") == False:
        return 0

    return 1

#-------------------------------------------------------------------------------
# LocateDiode
# User vision to locate the die position
#-------------------------------------------------------------------------------
def LocateDiode(StepName, SequenceObj, TestMetrics, TestResults):

    id = clr.Reference[String]('')
    if PickAndPlace.Instance.PostAttachLocateDiode(id) == False:
        return 0

    #double check the diode sn
    sn = TestResults.RetrieveTestResult('Laser_SN')
    if id.Value != sn:
        LogHelper.Log(SequenceObj.ProcessSequenceName, LogEventSeverity.Warning, 'Diode serial numbers do not match. Wrong die loaded for measurement.')
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
    TestResults.SaveTestResultsToStorage(TestResults.RetrieveTestResult('Assembly_SN'))

    return 1



