"""
URL configuration for HR_management_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from HR_system.views import *

urlpatterns = [
    path('admin/', admin.site.urls),

    path("", index, name="index"),
    path('registered-companies/', registered_company_list, name='registered_company_list'),
    path("login/", login, name="login"),
    path("logout/", logout_view, name="logout"),
    path("HR-registration/", HRRegistration_page, name="HR_registration"),
    path("verify-email/", verify_email, name="verify_email"),

    path("admin-dashboard/", main_admin_page, name="main_admin_page"),
    path("approve-hr/<int:user_id>/", approve_hr, name="approve_hr"),
    path("delete-hr/<int:user_id>/", delete_hr, name="delete_hr"),

    path("hr-dashboard/", HR_page, name="HR_page"),
    path('hr/profile/<int:hr_id>/', HR_profile, name='HR_profile'),
    path("employee-register/", employee_register, name="employee_register"),
    path("employee/list/", employee_list, name="employee_list"),
    path("delete-employee/<int:id>/", delete_employee, name="delete_employee"),
    path('employee/edit/<int:emp_id>/', edit_employee, name='edit_employee'),

    path("employee-home/", employee_home, name="employee_home"),
    path("verify-employee-email/", verify_employee_email, name="verify_employee_email"),
    path("employee/<int:emp_id>/profile/", employee_profile, name="employee_profile"),
    path("employee/<int:emp_id>/edit-profile/", edit_profile, name="edit_profile"),
    path("employee/<int:emp_id>/change-password/", change_password, name="change_password"),

    path('forgot_password/', forgot_password, name="forgot_password"),
    path('verify_otp/', verify_otp, name="verify_otp"),
    path('reset_password/', reset_password, name="reset_password"),

   # Leave System
    path("apply-leave/", apply_leave, name="apply_leave"),
    path("leave-status/", leave_status, name="leave_status"),

    # HR Leave Approval
    path("hr/leave-requests/", hr_leave_requests, name="hr_leave_requests"),
    path("leave-cancel/<int:leave_id>/", cancel_leave, name="cancel_leave"),
    path("hr/approve-leave/<int:leave_id>/", approve_leave, name="approve_leave"),
    path("hr/reject-leave/<int:leave_id>/", reject_leave, name="reject_leave"),

    path('attendance-mark/', attendance_mark, name='attendance_mark'),
    path('attendance-reports/', attendance_reports, name='attendance_reports'),
    path('late-early-reports/', late_early_reports, name='late_early_reports'),
    path('reports-analytics/', reports_analytics, name='reports_analytics'),
    path('employee-attendance-list/', hr_employee_attendance_list, name='employee_attendance_list'),
    path('late-early-exit/', hr_late_early_exit, name='late_early_exit'),
    path('report-analytics/', hr_reports_analytics, name='hr_reports_analytics'),
    

    path('generate-payroll/<int:payroll_id>/', generate_payroll, name='generate_payroll'),
    path('payroll-list/', payroll_list, name='payroll_list'),
    path('give-salary/<int:payroll_id>/', give_salary, name='give_salary'),
    path('give-salary/', give_salary, name='give_salary_multi'),
    path('generate-all-payroll/', generate_all_payroll, name='generate_all_payroll'),

     # 🏖️ Holiday Management (new)
    path('manage-holidays/', manage_holidays, name='manage_holidays'),
    path('delete-holiday/<int:holiday_id>/', delete_holiday, name='delete_holiday'),

    path('toggle-sunday-off/', toggle_sunday_off, name='toggle_sunday_off'),

    path("payu/salary/<int:payroll_id>/", payu_salary_payment, name="payu_salary"),
    path("payu/salary-multiple/", payu_salary_multiple, name="payu_salary_multiple"),
    path("payu/success/", payu_success, name="payu_success"),
    path("payu/fail/", payu_fail, name="payu_fail"),

    # Demo payout
    path("salary/bank-transfer/<int:payroll_id>/", send_salary_bank_transfer,name="salary_bank_transfer"),

    path('payslip/<int:payroll_id>/', view_payslip, name='view_payslip'),
    path("payment-history/", payment_history, name="payment_history"),
    path("employee/payment-history/", employee_payment_history, name="employee_payment_history"),



    path("employee/<int:emp_id>/bank-details/", bank_details, name="bank_details"),
    path("check-bank/<int:emp_id>/", check_bank_details, name="check_bank_details"),

    path("test-email/", test_email, name="test_email"),    

]

# Always serve media files — Railway needs this because DEBUG=False
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve static files (optional fallback)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)



