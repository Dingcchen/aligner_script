# Include all assemblies from the C# side
# DO NOT REMOVE THESE REFERECES
import clr
clr.AddReference('System.Core')
from System import *
from System import Action
from System import DateTime
from System import Array
from System import String
from System import Diagnostics
from System.Collections.Generic import List
clr.AddReferenceToFile('HAL.dll')
from HAL import Motion
clr.AddReferenceToFile('Algorithm.dll')
from Algorithm import *
clr.AddReferenceToFile('Automation.dll')
from Automation import *
clr.AddReferenceToFile('Process.dll')
from Process import *
clr.AddReferenceToFile('Utility.dll')
from Utility import *
clr.AddReferenceToFile('CiscoLaserSubmountAligner.exe')
from CiscoLaserSubmountAligner import *


def Step1(SequenceName, StepName, TestMetrics, TestResults, Stop):
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

def Step2(SequenceName, StepName, TestMetrics, TestResults, Stop):
    
    LogHelper.Log(StepName, LogEventSeverity.Alert, 'Step2 done')
        
    #Must always return an integer. 0 = failure, everythingthing else = success
    return 1

