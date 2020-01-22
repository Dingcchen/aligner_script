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
# Load
# Ask operator for serial numbers of the components
#-------------------------------------------------------------------------------
def Load(StepName, SequenceObj, TestMetrics, TestResults):

    loadposition = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LoadPresetPosition').DataItem #'BoardLoad'
    laserfauvacuumport = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'LaserFAUVaccumPortName').DataItem
    pmfauvacuumport = TestMetrics.GetTestMetricItem(SequenceObj.ProcessSequenceName, 'PowerMeterFAUVaccumPortName').DataItem

    # reset the positions
    HardwareFactory.Instance.GetHardwareByName('UVWandStage').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Hexapod').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('Nanocube').GetHardwareStateTree().ActivateState(loadposition)
    HardwareFactory.Instance.GetHardwareByName('DownCameraStages').GetHardwareStateTree().ActivateState(loadposition)

    # Wait for load complete and get serial number
    # possibly using a barcode scanner later
    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(pmfauvacuumport, True)
    ret = UserFormInputDialog.ShowDialog('Load and scan serial number', 'Please load powermeter FAU (FLAT SIDE DOWN) and scan serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Powermeter_FAU_SN', UserFormInputDialog.ReturnValue)
    else:
        HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(pmfauvacuumport, False)
        return 0

    HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(laserfauvacuumport, True)
    ret = UserFormInputDialog.ShowDialog('Load and scan serial number', 'Please load laser FAU (FLAT SIDE DOWN) and scan serial number:', True)
    if ret == True:
        TestResults.AddTestResult('Laser_FAU_SN', UserFormInputDialog.ReturnValue)
    else:
        HardwareFactory.Instance.GetHardwareByName('VacuumControl').SetOutputValue(laserfauvacuumport, False)
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
        UserFormInputDialog.ReturnValue = SequenceObj.ProcessPersistentData['Chan1InputPower']
    else:
        UserFormInputDialog.ReturnValue = ''

    ret = UserFormInputDialog.ShowDialog('Top chan optical launch power', 'Please enter top channel (Laser CH1) launch power (dBm):', True)
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

    ret = UserFormInputDialog.ShowDialog('Bottom chan optical launch power', 'Please enter bottom channel (Laser CH8) launch power (dBm):', True)
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