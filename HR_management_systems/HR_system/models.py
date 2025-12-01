from django.db import models
from django.utils.timezone import now,localtime
from datetime import datetime, date, time, timedelta
import random
import calendar
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.contrib.auth import get_user_model


User = get_user_model()


def month_name_to_number(name):
    try:
        return list(calendar.month_name).index(name.capitalize())
    except:
        return None



class HRRegister(models.Model):
    company_name = models.CharField(max_length=200)
    hr_name = models.CharField(max_length=200, blank=True, null=True)
    company_email = models.EmailField(unique=True)
    company_password = models.CharField(max_length=200)
    company_phone = models.CharField(max_length=15, blank=True, null=True)
    company_address = models.TextField(blank=True, null=True)
    company_document = models.FileField(upload_to='company_docs/', null=True, blank=True)

    company_location = models.CharField(max_length=255, blank=True, null=True)
    additional_email = models.EmailField(blank=True, null=True)
    previous_verified_email = models.EmailField(blank=True, null=True)
    company_type = models.CharField(max_length=100, blank=True, null=True)

    is_sunday_off = models.BooleanField(
        default=False,
        help_text="If enabled, all Sundays are considered company holidays."
    )

    WEEKLY_OFF_CHOICES = [
        ("SUNDAY", "Sunday"),
        ("SATURDAY", "Saturday"),
        ("NONE", "No Weekly Off"),
        ("ROTATIONAL", "Rotational / Employee Specific"),
    ]
    weekly_off_policy = models.CharField(
        max_length=15,
        choices=WEEKLY_OFF_CHOICES,
        default="SUNDAY",
        help_text="Weekly off pattern for this company"
    )

    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    otp_verified = models.BooleanField(default=False)

    is_approved = models.BooleanField(default=False)
    email_token = models.CharField(max_length=255, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.company_name
    
    def generate_otp(self):
        """Generate 6-digit OTP valid for 2 minutes."""
        otp = str(random.randint(100000, 999999))
        self.otp_code = otp
        # expires in 2 minutes
        self.otp_expiry = timezone.now() + timedelta(minutes=2)  
        self.save(update_fields=["otp_code", "otp_expiry"])
        return otp

    def is_otp_valid(self, entered_otp):
        """Check if OTP exists, is not expired, and matches entered code."""
        if not self.otp_code or not self.otp_expiry:
            return False
        if timezone.now() > self.otp_expiry:
            return False
        return str(entered_otp).strip() == str(self.otp_code).strip()


# ------------------------------------------------------------------------------------

class Employee(models.Model):
    hr = models.ForeignKey(HRRegister, on_delete=models.CASCADE)
    emp_unique_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    emp_name = models.CharField(max_length=200)
    emp_email = models.EmailField(unique=True)
    emp_phone = models.CharField(max_length=12)
    emp_address = models.TextField(null=True, blank=True)
    emp_position = models.CharField(max_length=150)
    emp_password = models.CharField(max_length=255)
    emp_profile = models.ImageField(upload_to='employee_profiles/', blank=True, null=True)
    emp_dob = models.DateField(null=True, blank=True)
    emp_qualification = models.CharField(max_length=200, null=True, blank=True)
    emp_experience = models.PositiveIntegerField(null=True, blank=True)

    bank_holder_name = models.CharField(max_length=200, null=True, blank=True)
    bank_account_number = models.CharField(max_length=30, null=True, blank=True)
    bank_ifsc = models.CharField(max_length=20, null=True, blank=True)


    work_start_time = models.TimeField(default=time(9, 0))
    work_end_time = models.TimeField(default=time(17, 0))
    joining_date = models.DateField(null=True, blank=True)


    WEEKLY_OFF_CHOICES = [
        ("SUNDAY", "Sunday"),
        ("MONDAY", "Monday"),
        ("TUESDAY", "Tuesday"),
        ("WEDNESDAY", "Wednesday"),
        ("THURSDAY", "Thursday"),
        ("FRIDAY", "Friday"),
        ("SATURDAY", "Saturday"),
        ("NONE", "No Weekly Off"),
    ]
    weekly_off_day = models.CharField(
        max_length=10,
        choices=WEEKLY_OFF_CHOICES,
        blank=True,
        null=True,
        help_text="Employee-specific off day (if rotational)"
    )

    emp_email_token = models.CharField(max_length=255, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.emp_name} ({self.emp_unique_id})"

# ------------------------------------------------------------------------------------

class LeaveRequests(models.Model):
    # Leave status choices
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # Leave type choices
    LEAVE_TYPES = [
        ("CASUAL", "Casual Leave"),
        ("SICK", "Sick Leave"),
        ("PAID", "Paid Leave"),
        ("OTHER", "Other"),
    ]

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    document = models.FileField(upload_to="leave_docs/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    applied_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_days(self):
        """Calculate total leave days."""
        return (self.to_date - self.from_date).days + 1

    def __str__(self):
        return f"{self.employee.emp_name} - {self.leave_type} ({self.status})"
    
# ------------------------------------------------------------------------------------
    
class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField(default=now)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('Present', 'Present'),
            ('Absent', 'Absent'),
            ('Late', 'Late'),
            ('Early Exit', 'Early Exit'),
            ('Late / Early Exit', 'Late / Early Exit'),
        ],
        default='Absent'
    )

    work_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_late = models.BooleanField(default=False)
    is_early_exit = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']

    def save(self, *args, **kwargs):

        if self.check_in and self.check_out:

            ci = self.check_in
            co = self.check_out

            start_time = self.employee.work_start_time
            end_time = self.employee.work_end_time

            # Convert all to datetime
            ci_dt = datetime.combine(self.date, ci)
            co_dt = datetime.combine(self.date, co)
            start_dt = datetime.combine(self.date, start_time)
            end_dt = datetime.combine(self.date, end_time)

            # Handle shift crossing midnight
            if end_time < start_time:
                end_dt += timedelta(days=1)

            if co_dt < ci_dt:
                co_dt += timedelta(days=1)

            # Work hours
            self.work_hours = round((co_dt - ci_dt).total_seconds() / 3600, 2)

            # Determine status
            grace_period = timedelta(minutes=30)
            early_exit = (end_dt - co_dt) > grace_period

            # ---- LATE ----
            late = ci_dt > start_dt

            # ---- 50% RULE ----
            shift_seconds = (end_dt - start_dt).total_seconds()
            worked_seconds = (co_dt - ci_dt).total_seconds()

            if worked_seconds < shift_seconds * 0.5:
                self.status = "Absent"
                self.is_late = False
                self.is_early_exit = False
                super().save(*args, **kwargs)
                return

            if late and early_exit:
                self.status = "Late / Early Exit"
                self.is_late = True
                self.is_early_exit = True
            elif late:
                self.status = "Late"
                self.is_late = True
                self.is_early_exit = False
            elif early_exit:
                self.status = "Early Exit"
                self.is_late = False
                self.is_early_exit = True
            else:
                self.status = "Present"
                self.is_late = False
                self.is_early_exit = False

        else:
            self.status = "Absent"
            self.work_hours = None
            self.is_late = False
            self.is_early_exit = False

        super().save(*args, **kwargs)
        
# ------------------------------------------------------------------------------------

class CompanyHoliday(models.Model):
    hr = models.ForeignKey(HRRegister, on_delete=models.CASCADE)
    holiday_date = models.DateField()
    holiday_name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.holiday_name} ({self.holiday_date})"
    
# ------------------------------------------------------------------------------------

class SalaryStructure(models.Model):
    """Defines salary components for each employee."""
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE)
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    per_day_salary = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        # 🛠 Fix: convert None to 0 before addition
        basic = self.basic_salary or Decimal(0)
        hra = self.hra or Decimal(0)
        allowances = self.allowances or Decimal(0)
        
        total = basic + hra + allowances
        self.per_day_salary = total / Decimal(30) if total > 0 else Decimal(0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Salary Structure - {self.employee.emp_name}"
    
# ------------------------------------------------------------------------------------


class MonthlyPayroll(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    generated_on = models.DateTimeField(auto_now_add=True)

    total_present = models.IntegerField(default=0)
    total_late = models.IntegerField(default=0)
    total_early_exit = models.IntegerField(default=0)
    total_late_early = models.IntegerField(default=0)
    total_absent = models.IntegerField(default=0)
    total_leave = models.IntegerField(default=0)
    weekly_offs = models.IntegerField(default=0)  
    holidays = models.IntegerField(default=0)

    gross_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    next_pay_date = models.DateField(null=True, blank=True)

    is_paid = models.BooleanField(default=False)
    is_freeze = models.BooleanField(default=False)
    payment_date = models.DateTimeField(blank=True, null=True)
    payment_method = models.CharField(
        max_length=50,
        choices=[('BANK', 'Bank Transfer'), ('UPI', 'UPI'), ('CASH', 'Cash'),('PAYU', 'PayU Gateway'),],
        blank=True,
        null=True
    )
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def mark_as_paid(self, method, transaction_id=None, paid_by=None, remarks=None):
        """
        Mark salary as paid, set next_pay_date to first day of the month AFTER payment date,
        and create a PaymentHistory record.
        """
        if self.is_paid:
            return  # already paid, no-op

        self.is_paid = True
        self.is_freeze = True

        self.payment_date = timezone.now()
        self.payment_method = method
        self.transaction_id = transaction_id

        # next_pay_date = first day of next month from payment_date
        pay_dt = self.payment_date.date()
        next_month = pay_dt.month + 1
        next_year = pay_dt.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        self.next_pay_date = date(next_year, next_month, 1)

        self.save()

        # create PaymentHistory record
        PaymentHistory.objects.create(
            payroll=self,
            employee=self.employee,
            amount=self.net_salary,
            payment_method=method,
            transaction_id=transaction_id,
            month=self.month,
            year=self.year,
            paid_by=paid_by,
            remarks=remarks or ""
        )

    class Meta:
        unique_together = ('employee', 'month', 'year')


    def get_weekly_offs_in_month(self, year, month):
        """
        Return weekly off dates based on HR policy:
        - SUNDAY
        - SATURDAY
        - NONE
        - ROTATIONAL (employee-specific off day)
        """

        hr = self.employee.hr
        offs = []
        policy = hr.weekly_off_policy

        name_to_day = {
            "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3,
            "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6
        }

        # No weekly off
        if policy == "NONE":
            return offs

        # Rotational weekly off (employee-specific)
        if policy == "ROTATIONAL":
            emp_day = (self.employee.weekly_off_day or "").upper()
            if emp_day not in name_to_day:
                return offs
            weekly_off_days = [name_to_day[emp_day]]

        else:
            week = policy.upper()

            # If policy = SUNDAY but toggle is off → no weekly offs
            if week == "SUNDAY" and not hr.is_sunday_off:
                return []

            # If Sunday & toggle ON → weekly off = Sunday
            if week == "SUNDAY" and hr.is_sunday_off:
                weekly_off_days = [6]

            # Other weekly offs (Saturday, etc.)
            else:
                weekly_off_days = [name_to_day.get(week, None)]
                if weekly_off_days == [None]:
                    return []


        # Loop and collect all weekly offs
        d = date(year, month, 1)
        while d.month == month:
            if d.weekday() in weekly_off_days:
                offs.append(d)
            d += timedelta(days=1)

        return offs

    
    @property
    def is_current_month(self):
        today = timezone.now().date()
        month_num = month_name_to_number(self.month)
        if not month_num:
            return False
        return today.month == month_num and today.year == self.year

    
    def calculate_salary(self):
        if self.is_freeze or self.is_paid:
            return
        """Automatically calculate monthly salary based on attendance & structure."""
        from HR_system.models import Attendance, LeaveRequests, SalaryStructure ,CompanyHoliday

        try:
            salary_structure = SalaryStructure.objects.get(employee=self.employee)
        except SalaryStructure.DoesNotExist:
            self.gross_salary = Decimal(0)
            self.net_salary = Decimal(0)
            self.save()
            return

        # Determine month number and days
        try:
            month_number = month_name_to_number(self.month)
            if not month_number:
                return
        except ValueError:
            return  # invalid month name, skip calculation

        days_in_month = calendar.monthrange(self.year, month_number)[1]

        weekly_offs = self.get_weekly_offs_in_month(self.year, month_number)
        self.weekly_offs = len(weekly_offs)

        # ✅ Holidays
        holiday_qs = CompanyHoliday.objects.filter(
        hr=self.employee.hr,
        holiday_date__month=month_number,
        holiday_date__year=self.year
        )
        holidays = holiday_qs.count()
        self.holidays = holidays

        # ✅ Working Days
        working_days = days_in_month - (self.weekly_offs + self.holidays)

        # Attendance records
        attendances = Attendance.objects.filter(
            employee=self.employee,
            date__month=month_number,
            date__year=self.year
        )

        holiday_dates = list(holiday_qs.values_list("holiday_date", flat=True))
        attendances = attendances.exclude(date__in=holiday_dates)

        # Count attendance
        self.total_present = attendances.filter(status="Present").count()
        self.total_late = attendances.filter(status="Late").count()
        self.total_early_exit = attendances.filter(status="Early Exit").count()
        self.total_late_early = attendances.filter(status="Late / Early Exit").count()
        self.total_absent = attendances.filter(status="Absent").count()

        # Approved leaves
        approved = LeaveRequests.objects.filter(employee=self.employee, status="APPROVED")
        leave_days = 0

        month_start = date(self.year, month_number, 1)
        month_end = date(self.year, month_number, days_in_month)

        for lr in approved:
            s = max(lr.from_date, month_start)
            e = min(lr.to_date, month_end)
            if s <= e:
                leave_days += (e - s).days + 1

        self.total_leave = leave_days


        # Salary base values
        gross_salary = salary_structure.basic_salary + salary_structure.hra + salary_structure.allowances
        per_day = gross_salary / Decimal(days_in_month)

        # Calculate paid days (Late = 0.5 day, Late/Early = 0.75 day)
        total_paid_days = (
            (self.total_present * Decimal("1.0")) +
            (self.total_leave * Decimal("1.0")) +
            (self.total_late * Decimal("0.5")) +
            (self.total_early_exit * Decimal("0.5")) +
            (self.total_late_early * Decimal("0.75"))
        )

        unpaid_days = Decimal(working_days) - total_paid_days
        if unpaid_days < 0:
            unpaid_days = Decimal(0)

        attendance_deductions = (unpaid_days * per_day).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Total deductions (fixed + attendance)
        total_deductions = salary_structure.deductions + attendance_deductions

        # Net salary (no 50% rule)
        net_salary = gross_salary - total_deductions

        # Assign and round properly
        self.gross_salary = gross_salary.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.deductions = total_deductions.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.net_salary = max(Decimal(0), net_salary.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        self.save()

    def __str__(self):
        return f"{self.employee.emp_name} - {self.month} {self.year}"
    
# ------------------------------------------------------------------------------------

class PaymentHistory(models.Model):
    payroll = models.ForeignKey("MonthlyPayroll", on_delete=models.SET_NULL, null=True, blank=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50,
                                      choices=[('BANK','Bank Transfer'),('UPI','UPI'),
                                               ('CASH','Cash'),('PAYU', 'PayU Gateway')])
    transaction_id = models.CharField(max_length=200, blank=True, null=True)
    
    paid_on = models.DateTimeField(auto_now_add=True)

    month = models.CharField(max_length=20)
    year = models.IntegerField()

    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-paid_on']

    def __str__(self):
        return f"{self.employee.emp_name} — {self.amount} ({self.month} {self.year})"

    