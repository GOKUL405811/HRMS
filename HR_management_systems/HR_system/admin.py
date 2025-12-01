from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(HRRegister)
admin.site.register(Employee)
admin.site.register(LeaveRequests)
admin.site.register(Attendance)
admin.site.register(SalaryStructure)
admin.site.register(MonthlyPayroll)
