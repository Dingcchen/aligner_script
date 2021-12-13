# Include all necessary assemblies from the C# side
# DO NOT REMOVE THESE REFERECES
import clr
clr.AddReference("Microsoft.Office.Interop.Excel")
import Microsoft.Office.Interop.Excel as Excel
import os
import sys
import json
clr.AddReference('System.Core')
from System import IO
from System import Action
from System import Func
from System import DateTime
from System import Array
from System import String
from System import ValueTuple
import math as math
from System.Diagnostics import Stopwatch
from collections import *
from System.Collections.Generic import List

from alignerCommon import *


# IronPython imports to enable Excel interop

def WriteRow(excelfile, data, rownum):
    pass

def WriteObject(excelfile, data, colnum, rownum):

    for k in data:
        if(colnum != ''):
            excelfile.write(col)
        value = d.get(k)
        if(isinstance(value, list)):
            row = [k]
            row.extend(value)
            WriteRow(excelfile, row, rownum)
        elif(isinstance(value, dict)):
            row = [k]
            WriteRow(excelfile, row, rownum)
            WriteObject(excelfile, value, colnum+1)
        elif(isinstance(value, OrderedDict)):
            row = [k]
            WriteRow(excelfile, row, rownum)
            WriteObject(excelfile, value, colnum+1)
        else:
            row = [k]
            row.append(value)
            WriteRow(excelfile, row, rownum)
            

def WriteExcel(filename, data):
    ex = Excel.ApplicationClass()
    ex.Visible = True

    excelfile = os.path.join(os.getcwd(), filename)
    workbook = ex.Workbooks.Open(excelfile)
    # worksheet = workbook.ActiveSheet
    workbook.Close(True)
    ex.Quit()
    


class ExcelInterface(MethodBase):
    def __init__(self, parameters, results):
        super(ExcelInterface,self).__init__(parameters, results)
        self.workbook = None
        self.ExcelApplication = None
        self.ActiveSheet = None
        
    def Open(self, filename):
        self.ExcelApplication = Excel.ApplicationClass()
        self.ExcelApplication.Visible = True
        if os.path.exists(filename):
            excelfile = os.path.join(os.getcwd(), filename)
            self.workbook = self.ExcelApplication.Workbooks.Open(excelfile)
            self.ActiveSheet = self.workbook.ActiveSheet

    def Close(self):
        self.workbook.Close(True)
        self.ExcelApplication.Quit()

if __name__ == "__main__":
    current_path = excelfile = os.getcwd()

    parameters = OrderedDict()
    parameters_filename = os.path.join(current_path, "../Sequences/Kraken_FR4.cfg")
    results_filename = os.path.join(current_path, "../Data/test/result.json")

    ei = ExcelInterface(parameters_filename, results_filename)
    
    ei.Open("KRK-EV-01-K007_result.xlsx")
    ei.Close()
    









