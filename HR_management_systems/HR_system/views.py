from django.conf import settings
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect ,get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.urls import reverse
import uuid, re
from django.db import transaction 
from decimal import Decimal, InvalidOperation
from django.db.models import Q
from django.utils.timezone import now
from random import randint
from django.contrib.auth.decorators import login_required
from .models import *
import random
from datetime import datetime, time as dt_time
from datetime import timedelta
from django.utils.dateparse import parse_date


from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_email_safe(subject, message, from_email, recipient_list, fail_silently=True):
    """
    Send email but never raise an exception that kills the request.
    Returns True if send attempted successfully (or fail_silently used),
    False if an exception occurred but was caught.
    """
    try:
        # Use Django's send_mail; we pass fail_silently to avoid exceptions
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=fail_silently,
        )
        return True
    except Exception as e:
        # Log full exception in server logs so you can inspect later
        logger.exception("Email sending failed: %s", e)
        return False


# ----------------------------------------------------------------------------------------------
from django.views.decorators.csrf import csrf_exempt
import hashlib
from datetime import date
from django.utils.safestring import mark_safe

def payu_generate_hash(data):
    seq = (
        f"{data['key']}|{data['txnid']}|{data['amount']}|"
        f"{data['productinfo']}|{data['firstname']}|{data['email']}|"
        f"{data['udf1']}|{data['udf2']}|{data['udf3']}|{data['udf4']}|{data['udf5']}||||||"
        f"{settings.PAYU_MERCHANT_SALT}"
    )
    return hashlib.sha512(seq.encode()).hexdigest().lower()


def payu_salary_payment(request, payroll_id):

    payroll = get_object_or_404(MonthlyPayroll, id=payroll_id)
    employee = payroll.employee
    today = date.today()

    if payroll.is_paid and payroll.next_pay_date and payroll.next_pay_date > today:
        messages.error(
            request,
            f"❌ Salary already paid. Next payment allowed only after {payroll.next_pay_date}."
        )
        return redirect("payroll_list")
    
    if not employee.bank_holder_name or not employee.bank_account_number or not employee.bank_ifsc:
        messages.error(request, f"❌ {employee.emp_name} has no bank details added.")
        return redirect("employee_profile", emp_id=employee.id)

    
    txnid = f"TXN{random.randint(111111, 999999)}"
    amount = str(payroll.net_salary)

    posted = {
        "key": settings.PAYU_MERCHANT_KEY,
        "txnid": txnid,
        "amount": amount,
        "productinfo": "HRMS Salary",
        "firstname": employee.emp_name,
        "email": employee.emp_email,
        "phone": employee.emp_phone,
        "surl": request.build_absolute_uri("/payu/success/"),
        "furl": request.build_absolute_uri("/payu/fail/"),
        "udf1": payroll_id,   # send payroll id
        "udf2": "",
        "udf3": "",
        "udf4": "",
        "udf5": "",
    }

    posted["hash"] = payu_generate_hash(posted)

    # 🚀 Renders PayU redirect form → open give_salary_payu.html
    return render(request, "payu_redirect.html", {
        "posted": posted,
        "payu_url": settings.PAYU_URL
    })

def payu_salary_multiple(request):
    ids = request.GET.get("ids", "")
    id_list = [int(x) for x in ids.split(",") if x.isdigit()]
    payrolls = MonthlyPayroll.objects.filter(id__in=id_list)

    today = date.today()

    for p in payrolls:

        # Salary already paid?
        if p.is_paid and p.next_pay_date and p.next_pay_date > today:
            messages.error(
                request,
                f"❌ Salary for {p.employee.emp_name} can be paid only after {p.next_pay_date}."
            )
            return redirect("payroll_list")
        
        emp = p.employee
        if not emp.bank_holder_name or not emp.bank_account_number or not emp.bank_ifsc:
            messages.error(request, f"❌ {emp.emp_name} has no bank details added.")
            return redirect("employee_profile", emp_id=emp.id)
        
    total_amount = sum(float(p.net_salary) for p in payrolls)

    
    txnid = f"TXN_MULTI_{random.randint(111111, 999999)}"

    posted = {
        "key": settings.PAYU_MERCHANT_KEY,
        "txnid": txnid,
        "amount": str(total_amount),
        "productinfo": "HRMS Bulk Salary Payment",
        "firstname": "HR Admin",
        "email": "noreply@company.com",
        "phone": "9999999999",
        "surl": request.build_absolute_uri("/payu/success/?ids=" + ids),
        "furl": request.build_absolute_uri("/payu/fail/"),
        "udf1": ids,   # multiple IDs
        "udf2": "",
        "udf3": "",
        "udf4": "",
        "udf5": "",
    }

    posted["hash"] = payu_generate_hash(posted)

    return render(request, "payu_redirect.html", {
        "posted": posted,
        "payu_url": settings.PAYU_URL
    })


@csrf_exempt
def payu_success(request):

    txnid = request.POST.get("txnid")
    payroll_id = request.POST.get("udf1")

    if not payroll_id:
        return HttpResponse("Invalid Payment Response")


    if "," in payroll_id:
        ids = payroll_id.split(",")
        for pid in ids:
            payroll = MonthlyPayroll.objects.get(id=pid)
            payroll.mark_as_paid("PAYU", txnid,paid_by=request.user)
    else:

        payroll = MonthlyPayroll.objects.get(id=payroll_id)
        payroll.mark_as_paid("PAYU", txnid,paid_by=request.user)

    html = """
    <div style='text-align:center;margin-top:50px;font-family:Arial;'>
        <h2 style='color:green;'>✅ Salary Paid Successfully!</h2>
        <br>
        <a href='/payroll-list/' 
           style='padding:10px 20px;background:#0d6efd;color:white;border-radius:8px;text-decoration:none;'>
           ⬅ Back to Payroll List
        </a>
    </div>
    """
    return HttpResponse(mark_safe(html))    

@csrf_exempt
def payu_fail(request):
    html = """
    <div style='text-align:center;margin-top:50px;font-family:Arial;'>
        <h2 style='color:red;'>❌ Payment Failed</h2>
        <a href='/payroll-list/' 
           style='padding:10px 20px;background:#6c757d;color:white;border-radius:8px;text-decoration:none;'>
           ⬅ Back
        </a>
    </div>
    """
    return HttpResponse(mark_safe(html))

@csrf_exempt
def send_salary_bank_transfer(request, payroll_id):
   


    payroll = get_object_or_404(MonthlyPayroll, id=payroll_id)
    emp = payroll.employee

    # Validate demo bank data
    if not emp.bank_account_number or not emp.bank_ifsc:
        return JsonResponse({"status": "error",
                             "message": "Bank details missing. Please add them first."})

    # Fake payout
    transaction_id = f"DEMO-PAYOUT-{random.randint(10000,99999)}"

    payroll.mark_as_paid("BANK", transaction_id,paid_by=request.user)

    return JsonResponse({
        "status": "success",
        "message": f"Salary paid to {emp.emp_name} (Demo Mode)",
        "account_no": emp.bank_account_number,
        "ifsc": emp.bank_ifsc,
        "txn": transaction_id
    })

def can_pay_salary(payroll):
    """
    Salary can be paid only from the 1st of the FOLLOWING month.
    Example:
        Payroll month = January 2025 → Pay allowed from February 1, 2025
    """

    try:
        month_number = list(calendar.month_name).index(payroll.month)
    except:
        return False

    year = payroll.year

    if month_number == 12:
        next_month_date = datetime(year + 1, 1, 1)
    else:
        next_month_date = datetime(year, month_number + 1, 1)

    return timezone.now().date() >= next_month_date.date()


def reset_salary_if_new_month(payroll):
    """If month changed & salary not paid → recalc automatically."""
    if not payroll.is_paid:
        payroll.calculate_salary()
        payroll.save()

def payment_history(request):
    if 'hr_id' not in request.session:
        return redirect('login')

    hr = HRRegister.objects.get(id=request.session["hr_id"])

    payments = PaymentHistory.objects.filter(employee__hr=hr).order_by('-paid_on')

    return render(request, "paymenthistory.html", {
        "payments": payments
    })

def employee_payment_history(request):
    emp_id = request.session.get("emp_id")
    if not emp_id:
        return redirect("login")

    employee = get_object_or_404(Employee, id=emp_id)
    payments = PaymentHistory.objects.filter(employee=employee).order_by("-paid_on")

    return render(request, "employee_payment_history.html", {
        "payments": payments,
        "employee": employee,
    })


# ----------------------------------------------------------------------------------------------


def index(request):
    return render(request, 'index.html')

def registered_company_list(request):
    companies = HRRegister.objects.all().order_by('company_name')
    return render(request, 'registered_company_list.html', {'companies': companies})

# ✅ Email validation
def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

# ✅ Phone validation (10 digits)
def is_valid_phone(phone):
    return re.match(r'^\d{10}$', phone)

# ✅ Password validation (8 chars, 1 uppercase, 1 number)
def is_valid_password(password):
    return re.match(r'^(?=.*[A-Z])(?=.*\d).{8,}$', password)


# ---------------------------- HR Registration ----------------------------
def HRRegistration_page(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        company_email = request.POST.get('company_email')
        company_phone = request.POST.get('company_phone')
        company_document = request.FILES.get('company_document')
        company_address = request.POST.get('company_address')
        company_password = request.POST.get('company_password')

        # ✅ Validations
        if not is_valid_email(company_email):
            messages.error(request, "Invalid email format.")
            return redirect('HR_registration')

        if not is_valid_phone(company_phone):
            messages.error(request, "Phone must be 10 digits.")
            return redirect('HR_registration')

        if not is_valid_password(company_password):
            messages.error(request, "Password must be 8+ chars, include 1 uppercase & 1 number.")
            return redirect('HR_registration')

        if HRRegister.objects.filter(company_email=company_email).exists():
            messages.error(request, "Company email already registered.")
            return redirect('HR_registration')

        token = str(uuid.uuid4())

        HRRegister.objects.create(
            company_name=company_name,
            company_email=company_email,
            company_phone=company_phone,
            company_address=company_address,
            company_password=make_password(company_password),
            company_document=company_document,
            email_token=token,
            is_email_verified=False,
            is_approved=False
        )

        verify_link = request.build_absolute_uri(reverse("verify_email") + f"?token={token}")

        # ✅ Updated Email with login details
        send_email_safe(
            "HR Account Verification & Login Details",
            f"Welcome {company_name},\n\n"
            f"Your HR account has been registered.\n\n"
            f"✅ Login Email: {company_email}\n"
            f"✅ Password: {company_password}\n\n"
            f"Please verify your email:\n{verify_link}\n\n"
            f"Thank you!",
            settings.DEFAULT_FROM_EMAIL,
            [company_email],
        )

        messages.success(request, "Registration successful. Check email to verify!")
        return redirect('login')

    return render(request, 'HR_registration.html')


# ---------------------------- HR Email Verify ----------------------------
def verify_email(request):
    token = request.GET.get("token")
    user = HRRegister.objects.filter(email_token=token).first()

    if user:
        user.is_email_verified = True
        user.save()
        messages.success(request, "Email verified! Wait for admin approval.")
    else:
        messages.error(request, "Invalid verification link.")

    return redirect('login')


# ---------------------------- Login (Admin + HR + Employee) ----------------------------
def login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # ✅ ADMIN LOGIN
        if email == settings.DEFAULT_ADMIN_EMAIL and password == settings.DEFAULT_ADMIN_PASSWORD:
            request.session['is_default_admin'] = True
            request.session['user_role'] = "ADMIN"
            return redirect('main_admin_page')

        # ✅ HR LOGIN
        try:
            hr = HRRegister.objects.get(company_email=email)

            if not hr.is_email_verified:
                messages.error(request, "Please verify email.")
                return redirect('login')

            if not hr.is_approved:
                messages.error(request, "Admin approval pending.")
                return redirect('login')

            if check_password(password, hr.company_password):
                request.session['hr_id'] = hr.id
                request.session['user_role'] = "HR"
                return redirect('HR_page')
        except HRRegister.DoesNotExist:
            pass

        # ✅ EMPLOYEE LOGIN
        try:
            emp = Employee.objects.get(emp_email=email)

            if not emp.is_email_verified:
                messages.error(request, "Please verify your email before login.")
                return redirect('login')

            if check_password(password, emp.emp_password):
                request.session['emp_id'] = emp.id
                request.session['hr_id'] = emp.hr.id
                request.session['user_role'] = "EMPLOYEE"
                return redirect('employee_home')
            else:
                messages.error(request, "Wrong password.")
                return redirect('login')

        except Employee.DoesNotExist:
            messages.error(request, "Invalid login credentials.")
            return redirect('login')

    return render(request, 'login.html')


# ---------------------------- Admin Panel ----------------------------
def main_admin_page(request):
    if not request.session.get('is_default_admin'):
        return redirect('login')

    return render(request, 'mainadmin.html', {
        "pending_users": HRRegister.objects.filter(is_approved=False, is_email_verified=True),
        "approved_users": HRRegister.objects.filter(is_approved=True),
    })


def approve_hr(request, user_id):
    hr = HRRegister.objects.get(id=user_id)
    hr.is_approved = True
    hr.save()
    messages.success(request, "HR Approved.")
    return redirect('main_admin_page')


def delete_hr(request, user_id):
    HRRegister.objects.get(id=user_id).delete()
    messages.success(request, "HR Deleted.")
    return redirect('main_admin_page')


# ---------------------------- HR Dashboard ----------------------------

def HR_page(request):
    """HR Dashboard showing company overview, payrolls, leaves & holidays."""
    
    # 🔐 Check session authentication
    if 'hr_id' not in request.session:
        messages.error(request, "Access denied. Please log in as HR.")
        return redirect('login')

    # ✅ Fetch HR instance
    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])

    # ✅ Determine current month & year
    current_month = date.today().month
    current_year = date.today().year
    month_name = calendar.month_name[current_month]

    # ✅ Dashboard Metrics
    total_employees = Employee.objects.filter(hr=hr).count()

    pending_leaves = LeaveRequests.objects.filter(
        employee__hr=hr,
        status=LeaveRequests.STATUS_PENDING
    ).count()

    total_payrolls = MonthlyPayroll.objects.filter(
        employee__hr=hr,
        month=month_name,
        year=current_year
    ).count()

    total_holidays = CompanyHoliday.objects.filter(
        hr=hr,
        holiday_date__month=current_month,
        holiday_date__year=current_year
    ).count()

    # ✅ Render the dashboard with full context
    return render(request, 'HR.html', {
        "hr": hr,
        "total_employees": total_employees,
        "pending_leaves": pending_leaves,
        "total_payrolls": total_payrolls,
        "total_holidays": total_holidays,
        "now": now(),
    })

# ---------------------------- HR Profile ----------------------------

def HR_profile(request, hr_id):
    hr = get_object_or_404(HRRegister, id=hr_id)
    show_otp_prompt = False  # for inline OTP message

    # 🧹 Auto-clear expired OTP
    if hr.otp_expiry and timezone.now() > hr.otp_expiry:
        hr.otp_code = None
        hr.otp_expiry = None
        hr.save(update_fields=["otp_code", "otp_expiry"])
        messages.warning(request, "⚠️ Your previous OTP has expired.")

    # ✅ Step 0: Handle Cancel OTP (AJAX)
    if request.method == "POST" and request.headers.get("Content-Type") == "application/json":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        if data.get("cancel_verification"):
            restored_email = hr.previous_verified_email
            if restored_email:
                hr.additional_email = restored_email
                hr.otp_verified = True
                hr.otp_code = None
                hr.otp_expiry = None
                hr.save(update_fields=["additional_email", "otp_verified", "otp_code", "otp_expiry"])
                return JsonResponse({
                    "status": "success",
                    "restored_email": restored_email,
                    "message": "✅ Previous verified additional email restored successfully."
                })
            return JsonResponse({
                "status": "error",
                "message": "No previous verified email found."
            }, status=400)

    # ✅ Step 1: Update profile details & send OTP if email changed
    if request.method == "POST" and 'save_profile' in request.POST:
        hr.hr_name = request.POST.get("hr_name")
        hr.company_phone = request.POST.get("company_phone")
        hr.company_address = request.POST.get("company_address")
        hr.company_location = request.POST.get("company_location")
        new_additional_email = request.POST.get("additional_email")
        hr.company_type = request.POST.get("company_type")

        # 📧 If additional email changed → send OTP
        if new_additional_email and new_additional_email != hr.additional_email:
            # 🧩 Store previously verified additional email
            if hr.otp_verified and hr.additional_email:
                hr.previous_verified_email = hr.additional_email

            hr.additional_email = new_additional_email
            otp = hr.generate_otp()

            try:
                send_mail(
                    subject="HR Profile Email Verification OTP",
                    message=(
                        f"Dear {hr.hr_name or hr.company_name},\n\n"
                        f"Your OTP for email verification is: {otp}\n"
                        f"This code is valid for 2 minutes.\n\n"
                        f"Thank you,\nYour HR Portal"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[new_additional_email],
                    fail_silently=False,
                )
                hr.otp_verified = False
                hr.save(update_fields=[
                    "previous_verified_email",
                    "additional_email",
                    "otp_code",
                    "otp_expiry",
                    "otp_verified"
                ])
                show_otp_prompt = True
                messages.info(request, "📩 Please wait for OTP and check your mail to verify your new email address.")
            except Exception as e:
                messages.error(request, f"❌ Failed to send OTP: {e}")

            # Render directly (no redirect)
            return render(
                request,
                'HR_profile.html',
                {"hr": hr, "show_otp_prompt": show_otp_prompt, "verified_email": hr.previous_verified_email}
            )

        # 📸 Handle image upload
        if request.FILES.get("company_document"):
            hr.company_document = request.FILES["company_document"]
            hr.save(update_fields=["company_document"])

        # ✅ Normal update (no new email)
        hr.save()
        messages.success(request, "✅ Profile updated successfully.")
        return redirect('HR_profile', hr_id=hr.id)

    # ✅ Step 2: Resend OTP
    elif request.method == "POST" and 'resend_otp' in request.POST:
        if hr.additional_email:
            otp = hr.generate_otp()
            try:
                send_mail(
                    subject="Resend OTP - HR Email Verification",
                    message=(
                        f"Your new OTP is {otp}.\n"
                        f"This code is valid for 2 minutes.\n\n"
                        f"Thank you,\nYour HR Portal"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[hr.additional_email],
                    fail_silently=False,
                )
                messages.info(request, "📨 New OTP sent to your email.")
            except Exception as e:
                messages.error(request, f"❌ Failed to resend OTP: {e}")
        else:
            messages.error(request, "❌ No additional email found to resend OTP.")
        return redirect('HR_profile', hr_id=hr.id)

    # ✅ Step 3: Verify OTP
    elif request.method == "POST" and 'verify_otp' in request.POST:
        entered_otp = request.POST.get("otp")

        if not hr.is_otp_valid(entered_otp):
            messages.error(request, "⚠️ Invalid or expired OTP. Please resend a new one.")
        else:
            hr.otp_verified = True
            hr.otp_code = None
            hr.otp_expiry = None
            hr.save(update_fields=["otp_verified", "otp_code", "otp_expiry"])
            messages.success(request, "✅ Email verified successfully!")

        return redirect('HR_profile', hr_id=hr.id)

    # ✅ Default render
    return render(request, 'HR_profile.html', {
        "hr": hr,
        "verified_email": hr.previous_verified_email or (hr.additional_email if hr.otp_verified else "")
    })

        
# ---------------------------- Logout ----------------------------
def logout_view(request):
    request.session.flush()
    return redirect('login')

# ---------------------------- Employee Register ----------------------------

def generate_employee_code(hr):
    prefix = hr.company_name[:3].upper()

    # Get last employee of this HR only
    last_emp = Employee.objects.filter(hr=hr).order_by("-id").first()

    if last_emp:
        try:
            last_num = int(last_emp.emp_unique_id.split("-")[-1])
        except:
            last_num = 0
    else:
        last_num = 0

    new_num = last_num + 1
    return f"{prefix}-EMP-{new_num:03d}"

# ---------------------------- Employee Register ----------------------------


def employee_register(request):
    if "hr_id" not in request.session:
        messages.error(request, "Login as HR first.")
        return redirect('login')

    if request.method == "POST":

        hr = HRRegister.objects.get(id=request.session["hr_id"])

        name = request.POST.get("emp_name")
        email = request.POST.get("emp_email")
        phone = request.POST.get("emp_phone")
        address = request.POST.get("emp_address")
        position = request.POST.get("emp_position")
        password = request.POST.get("emp_password")
        work_start_time = request.POST.get("work_start_time")
        work_end_time = request.POST.get("work_end_time")

        basic_salary = Decimal(request.POST.get("basic_salary", 0))
        hra = Decimal(request.POST.get("hra", 0))
        allowances = Decimal(request.POST.get("allowances", 0))
        deductions = Decimal(request.POST.get("deductions", 0))

        # -------------------- VALIDATIONS --------------------
        if not is_valid_email(email):
            messages.error(request, "Invalid email format.")
            return redirect("employee_register")

        if not is_valid_phone(phone):
            messages.error(request, "Phone must be 10 digits.")
            return redirect("employee_register")

        if not is_valid_password(password):
            messages.error(request, "Password must be 8+ chars, include 1 uppercase & 1 number.")
            return redirect("employee_register")

        if Employee.objects.filter(emp_email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("employee_register")

        join_date_obj = now().date()

        try:
            start_time_obj = datetime.strptime(work_start_time, "%H:%M").time()
            end_time_obj = datetime.strptime(work_end_time, "%H:%M").time()
        except:
            messages.error(request, "❌ Invalid Date & time format.")
            return redirect("employee_register")

        # UNIQUE EMPLOYEE CODE
        emp_code = generate_employee_code(hr)
        token = str(uuid.uuid4())

        # ======================================================
        # 1️⃣ FIRST → SEND EMAIL BEFORE CREATING EMPLOYEE
        # ======================================================
        verify_link = request.build_absolute_uri(
            reverse("verify_employee_email") + f"?token={token}"
        )

        try:
            send_mail(
                "Employee Account Verification",
                f"Welcome {name},\n\nYour employee account has been created.\n\n"
                f"Login Email: {email}\n"
                f"Password: {password}\n\n"
                f"Verify here:\n{verify_link}\n\n"
                "Thank you!",
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
            email_sent = True    # ★ NEW CODE
        except Exception as e:
            email_sent = False   # ★ NEW CODE
            print("EMAIL ERROR:", e)

        # ======================================================
        #  If email sending fails → DO NOT ADD EMPLOYEE
        # ======================================================
        if not email_sent:   # ★ NEW CODE
            messages.error(
                request,
                "❌ Verification email could NOT be sent due to server time/date error. Employee was NOT added."  # ★ NEW CODE
            )
            return redirect("employee_register")    # ★ NEW CODE

        # ======================================================
        # 2️⃣ EMAIL SENT SUCCESSFULLY → NOW SAVE IN DATABASE
        # ======================================================
        try:
            with transaction.atomic():    # ★ NEW CODE

                employee = Employee.objects.create(
                    hr=hr,
                    emp_name=name,
                    emp_email=email,
                    emp_phone=phone,
                    emp_address=address,
                    emp_position=position,
                    emp_password=make_password(password),
                    emp_unique_id=emp_code,
                    emp_email_token=token,
                    work_start_time=start_time_obj,
                    work_end_time=end_time_obj,
                    joining_date=join_date_obj,
                    is_email_verified=False
                )

                SalaryStructure.objects.create(
                    employee=employee,
                    basic_salary=basic_salary,
                    hra=hra,
                    allowances=allowances,
                    deductions=deductions
                )

        except Exception as db_error:
            messages.error(request, f"Database Error: {db_error}")
            return redirect("employee_register")

        # ======================================================
        # SUCCESS MESSAGE
        # ======================================================
        messages.success(request, "✅ Employee added successfully! Verification email sent.")
        return redirect("employee_register")

    return render(request, "employee_register.html")


# ---------------------------- Employee Home ----------------------------
def employee_home(request):
    emp_id = request.session.get('emp_id')
    if not emp_id:
        return redirect('login')

    emp = get_object_or_404(Employee, id=emp_id)

    show_instructions = False
    missing_items = []


    if not emp.emp_address:
        missing_items.append("Add your address")

    if not emp.bank_holder_name:
        missing_items.append("Add bank account holder name")

    if not emp.bank_account_number:
        missing_items.append("Add bank account number")

    if not emp.bank_ifsc:
        missing_items.append("Add IFSC code")


    if missing_items:
        show_instructions = True

    try:
        salary = SalaryStructure.objects.get(employee=emp)
        gross = salary.basic_salary + salary.hra + salary.allowances
    except SalaryStructure.DoesNotExist:
        salary = None
        gross = 0

    context = {
        "emp_id": emp.id,
        "employee": emp,
        "employee_name": emp.emp_name,
        "emp_unique_id": emp.emp_unique_id,
        "emp_position": emp.emp_position,
        "emp_profile": emp.emp_profile,
        "company_name": emp.hr.company_name,
        "start_time": emp.work_start_time,
        "end_time": emp.work_end_time,

        "basic_salary": salary.basic_salary if salary else 0,
        "hra": salary.hra if salary else 0,
        "allowances": salary.allowances if salary else 0,
        "deductions": salary.deductions if salary else 0,
        "gross_salary": gross,

        "show_instructions": show_instructions,
        "missing_items": missing_items,
    }
    return render(request, "employee.html", context)


# ---------------------------- Employee Email Verify ----------------------------
def verify_employee_email(request):
    token = request.GET.get("token")
    emp = Employee.objects.filter(emp_email_token=token).first()

    if emp:
        emp.is_email_verified = True
        emp.save()
        messages.success(request, "Email verified! You can now login.")
    else:
        messages.error(request, "Invalid or expired verification link.")

    return redirect('login')

# ---------------------------- Employee List ----------------------------

def employee_list(request):
    if "hr_id" not in request.session:
        return redirect("login")

    hr = HRRegister.objects.get(id=request.session["hr_id"])
    
    # base queryset
    employees = Employee.objects.filter(hr=hr).select_related("salarystructure")

    # ✅ Get search and filter values
    search = request.GET.get("search", "")
    position_filter = request.GET.get("position", "")

    # ✅ Search filter
    if search:
        employees = employees.filter(
            Q(emp_name__icontains=search) |
            Q(emp_email__icontains=search) |
            Q(emp_unique_id__icontains=search)
        )

    # ✅ Position filter
    if position_filter:
        employees = employees.filter(emp_position=position_filter)

    # ✅ Unique positions for dropdown
    positions = Employee.objects.filter(hr=hr).values_list(
        "emp_position", flat=True
    ).distinct()

    return render(request, "hr_employee_list.html", {
        "employees": employees,
        "positions": positions,
        
    })


# ---------------------------- Delete Employee ----------------------------

def delete_employee(request, id):
    if "hr_id" not in request.session:
        return redirect("login")

    emp = Employee.objects.filter(id=id, hr_id=request.session["hr_id"]).first()
    
    if emp:
        emp.delete()
        messages.success(request, "Employee deleted successfully.")
    else:
        messages.error(request, "Employee not found!")

    return redirect("employee_list")

# ---------------------------- Edit Employee ----------------------------

def edit_employee(request, emp_id):
    hr_id = request.session.get("hr_id")
    if not hr_id:
        return redirect("login")

    employee = get_object_or_404(Employee, id=emp_id)
    salary, _ = SalaryStructure.objects.get_or_create(employee=employee)

    if request.method == "POST":
        # Update employee fields
        employee.emp_name = request.POST.get("name")
        employee.emp_email = request.POST.get("email")
        employee.emp_phone = request.POST.get("phone")
        employee.emp_address = request.POST.get("address")
        employee.emp_position = request.POST.get("position")

        # Work times
        work_start = request.POST.get('work_start_time')
        work_end = request.POST.get('work_end_time')

        employee.work_start_time = (
            datetime.strptime(work_start, '%H:%M').time() if work_start else None
        )
        employee.work_end_time = (
            datetime.strptime(work_end, '%H:%M').time() if work_end else None
        )

        employee.save()

        # SAFE SALARY UPDATE
        salary.basic_salary = safe_decimal(request.POST.get("basic_salary"))
        salary.hra = safe_decimal(request.POST.get("hra"))
        salary.allowances = safe_decimal(request.POST.get("allowances"))
        salary.deductions = safe_decimal(request.POST.get("deductions"))
        salary.save()

        messages.success(request, f"✅ {employee.emp_name}'s details and salary updated successfully.")
        return redirect("employee_list")

    return render(request, "edit_employee.html", {
        "employee": employee,
        "salary": salary
    })


def safe_decimal(value):
    try:
        if value in ["", None]:
            return Decimal("0")
        return Decimal(value)
    except:
        return Decimal("0")


# ----------------------------  Employee profile ----------------------------

def employee_profile(request, emp_id):
    employee = Employee.objects.get(id=emp_id)
    return render(request, "employee_profile.html", {"employee": employee})

# ----------------------------  Employee profile Edit ----------------------------

def edit_profile(request, emp_id):
    # Check if the user is logged in and authorized
    if 'emp_id' not in request.session or request.session['emp_id'] != emp_id:
        return redirect("login")

    # Get the employee object
    employee = Employee.objects.get(id=emp_id)

    if request.method == "POST":
        # Update fields from form
        employee.emp_address = request.POST.get("emp_address")
        employee.emp_qualification = request.POST.get("emp_qualification")
        employee.emp_experience = request.POST.get("emp_experience")

        dob = request.POST.get("emp_dob")
        if dob:
            employee.emp_dob = dob

        # Update profile image if uploaded
        if request.FILES.get("emp_profile"):
            employee.emp_profile = request.FILES["emp_profile"]

        employee.save()
        return redirect("employee_profile", emp_id=employee.id)

    # Pass both employee object and emp_id explicitly to avoid NoReverseMatch
    context = {
        "employee": employee,
        "emp_id": employee.id
    }

    return render(request, "employee_edit_profile.html", context)



# ----------------------------  Employee Password change ----------------------------

def change_password(request, emp_id):
    if 'emp_id' not in request.session or request.session['emp_id'] != emp_id:
        return redirect("login")

    employee = Employee.objects.get(id=emp_id)

    if request.method == "POST":
        old_pass = request.POST.get("old_password")
        new_pass = request.POST.get("new_password")

        if not check_password(old_pass, employee.emp_password):
            messages.error(request, "Old password is incorrect")
            return redirect("change_password", emp_id=emp_id)

        employee.emp_password = make_password(new_pass)
        employee.save()

        messages.success(request, "Password changed successfully")
        return redirect("employee_home")

    return render(request, "employee_change_password.html")


# ======================= Forgot Password =======================

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        # ✅ Check if email belongs to an Employee
        if Employee.objects.filter(emp_email=email).exists():
            otp = randint(100000, 999999)
            request.session['reset_email'] = email
            request.session['otp'] = otp

            # ✅ Send OTP to Employee Email
            send_mail(
                subject="Password Reset OTP",
                message=f"Your OTP for password reset is: {otp}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            messages.success(request, "✅ OTP sent to your email.")
            return redirect("verify_otp")

        # ✅ Check if email belongs to HR
        elif HRRegister.objects.filter(company_email=email).exists():
            otp = randint(100000, 999999)
            request.session['reset_email'] = email
            request.session['otp'] = otp

            # ✅ Send OTP to HR Email
            send_mail(
                subject="Password Reset OTP",
                message=f"Your OTP for password reset is: {otp}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            messages.success(request, "✅ OTP sent to your email.")
            return redirect("verify_otp")

        else:
            messages.error(request, "❌ Email not registered.")
            return redirect("forgot_password")

    return render(request, "forgot_password.html")

# ======================= OTP Verification =======================

def verify_otp(request):
    email = request.session.get("reset_email")
    otp_session = str(request.session.get("otp"))

    if not email:
        messages.error(request, "⚠️ Session expired. Please try again.")
        return redirect("forgot_password")

    if request.method == "POST":
        # 🔁 Handle Resend OTP
        if "resend_otp" in request.POST:
            otp = randint(100000, 999999)
            request.session["otp"] = otp

            send_mail(
                subject="Password Reset OTP (Resent)",
                message=f"Your new OTP for password reset is: {otp}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            messages.info(request, "📨 New OTP sent to your email.")
            return redirect("verify_otp")

        # ✅ Verify OTP
        entered_otp = request.POST.get("otp")
        if entered_otp == otp_session:
            messages.success(request, "✅ OTP Verified successfully.")
            return redirect("reset_password")
        else:
            messages.error(request, "❌ Invalid OTP. Please try again.")
            return redirect("verify_otp")

    return render(request, "verify_otp.html", {"email": email})

# ======================= Reset Password =======================

def reset_password(request):
    if request.method == "POST":
        new_pass = request.POST.get("password")
        confirm_pass = request.POST.get("confirm_password")
        email = request.session.get("reset_email")

        # ✅ Check passwords match
        if new_pass != confirm_pass:
            messages.error(request, "Passwords do not match ❌")
            return redirect("reset_password")

        # ✅ Validate password format again
        if not is_valid_password(new_pass):
            messages.error(request, "Password must be 8+ chars, include 1 uppercase & 1 number.")
            return redirect("reset_password")

        hashed_pass = make_password(new_pass)

        # ✅ Update Employee Password
        if Employee.objects.filter(emp_email=email).exists():
            emp = Employee.objects.get(emp_email=email)
            emp.emp_password = hashed_pass
            emp.save()

        # ✅ Update HR Password
        elif HRRegister.objects.filter(company_email=email).exists():
            hr = HRRegister.objects.get(company_email=email)
            hr.company_password = hashed_pass
            hr.save()

        # ✅ Clear session
        request.session.pop("otp", None)
        request.session.pop("reset_email", None)

        messages.success(request, "Password reset successfully ✅")
        return redirect("login")

    return render(request, "reset_password.html")

# ======================= Leave Apply =======================

# Employee Apply Leave
def apply_leave(request):
    if 'emp_id' not in request.session:
        return redirect("login")

    emp = Employee.objects.get(id=request.session.get("emp_id"))

    if request.method == "POST":
        from_date = request.POST.get("from_date")
        to_date = request.POST.get("to_date")

        # Validate date
        if datetime.strptime(from_date, "%Y-%m-%d") > datetime.strptime(to_date, "%Y-%m-%d"):
            messages.error(request, "To date must be after From date ❌")
            return redirect("apply_leave")

        LeaveRequests.objects.create(
            employee=emp,
            leave_type=request.POST.get("leave_type"),
            from_date=from_date,
            to_date=to_date,
            reason=request.POST.get("reason"),
            document=request.FILES.get("document"),
            status=LeaveRequests.STATUS_PENDING,
        )

        messages.success(request, "Leave request submitted ✅")
        return redirect("leave_status")

    return render(request, "apply_leave.html")

# Employee Leave Status
def leave_status(request):
    if 'emp_id' not in request.session:
        return redirect("login")

    emp = Employee.objects.get(id=request.session["emp_id"])
    leaves = LeaveRequests.objects.filter(employee=emp).order_by("-applied_at")
    return render(request, "leave_status.html", {"leaves": leaves})

# HR Panel - Leave Requests
def hr_leave_requests(request):
    if 'hr_id' not in request.session:
        return redirect("login")

    hr = get_object_or_404(HRRegister, id=request.session["hr_id"])
    leaves = LeaveRequests.objects.filter(employee__hr=hr).order_by("-applied_at")

    # Count statuses
    total_requests = leaves.count()
    pending_leaves = leaves.filter(status=LeaveRequests.STATUS_PENDING).count()
    approved_leaves = leaves.filter(status=LeaveRequests.STATUS_APPROVED).count()
    rejected_leaves = leaves.filter(status=LeaveRequests.STATUS_REJECTED).count()

    return render(
        request,
        "hr_leave_requests.html",
        {
            "leaves": leaves,
            "total_requests": total_requests,
            "pending_leaves": pending_leaves,
            "approved_leaves": approved_leaves,
            "rejected_leaves": rejected_leaves,
        }
    )


# Approve Leave
def approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequests, id=leave_id)
    leave.status = LeaveRequests.STATUS_APPROVED
    leave.save()
    messages.success(request, f"Leave approved for {leave.employee.emp_name} ✅")
    return redirect("hr_leave_requests")

# Approve Leave
def cancel_leave(request, leave_id):
    if 'emp_id' not in request.session:
        return redirect("login")

    leave = get_object_or_404(LeaveRequests, id=leave_id, employee_id=request.session['emp_id'])

    if leave.status == LeaveRequests.STATUS_PENDING:
        leave.status = LeaveRequests.STATUS_CANCELLED  # Optional: Add STATUS_CANCELLED in your model
        leave.save()
        messages.success(request, "Leave request cancelled successfully.")
    else:
        messages.error(request, "You cannot cancel this leave.")

    return redirect("leave_status")

# Reject Leave
def reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequests, id=leave_id)
    leave.status = LeaveRequests.STATUS_REJECTED
    leave.save()
    messages.error(request, f"Leave rejected for {leave.employee.emp_name} ❌")
    return redirect("hr_leave_requests")



# ================= Attendance Dashboard =================

def determine_status(start_time, end_time, check_in, check_out, date):
    """Correct status calculation with cross-midnight support"""

    # Convert to datetime same day
    start_dt = datetime.combine(date, start_time)
    end_dt = datetime.combine(date, end_time)
    ci_dt = datetime.combine(date, check_in)
    co_dt = datetime.combine(date, check_out)

    # Shift crosses midnight → end next day
    if end_time < start_time:
        end_dt += timedelta(days=1)

    # Check-out crosses midnight
    if co_dt < ci_dt:
        co_dt += timedelta(days=1)

    # Invalid sequence (checked out before shift starts)
    if co_dt <= start_dt:
        return "Absent"

    # Identify late/early cases
    late = ci_dt > start_dt
    early_exit = co_dt < end_dt

    if late and early_exit:
        return "Late / Early Exit"
    elif late:
        return "Late"
    elif early_exit:
        return "Early Exit"
    else:
        return "Present"


def attendance_mark(request):
    emp_id = request.session.get('emp_id')
    if not emp_id:
        return redirect('login')

    emp = get_object_or_404(Employee, id=emp_id)
    today = now().date()

    leave_exists = LeaveRequests.objects.filter(
        employee=emp,
        status="APPROVED",
        from_date__lte=today,
        to_date__gte=today
    ).exists()

    if leave_exists:
        messages.error(request, "❌ Today is an approved leave day. Attendance cannot be marked.")
        return render(request, "attendance_mark.html", {
            "employee": emp,
            "attendance": None,
            "emp_id": emp.id,
            "emp_profile": emp.emp_profile,
            "is_leave_day": True,
            "start_time": emp.work_start_time,
            "end_time": emp.work_end_time,
        })

    attendance, _ = Attendance.objects.get_or_create(employee=emp, date=today)

    start_time = emp.work_start_time
    end_time = emp.work_end_time

    now_dt = now()

    # Shift as datetime
    start_dt = datetime.combine(today, start_time)
    end_dt = datetime.combine(today, end_time)

    # Cross-midnight shift
    if end_time < start_time:
        end_dt += timedelta(days=1)

    # Allow check-in 1 hour before start
    allow_checkin_start = start_dt - timedelta(hours=1)

    # Allow check-out till 1 hour after end
    allow_checkout_end = end_dt + timedelta(hours=1)

    can_check_in = attendance.check_in is None and allow_checkin_start <= now_dt <= allow_checkout_end
    can_check_out = attendance.check_in is not None and attendance.check_out is None and now_dt <= allow_checkout_end

    # ---------------- POST ACTIONS ----------------
    if request.method == "POST":
        action = request.POST.get("action")
        current_time = now().time()

        # ----- CHECK-IN -----
        if action == "check_in":
            if can_check_in:
                attendance.check_in = current_time
                messages.success(request, "✅ Check-In successful!")
            else:
                messages.warning(request, "⚠️ Check-In not allowed at this time.")

        # ----- CHECK-OUT -----
        elif action == "check_out":
            if can_check_out:
                attendance.check_out = current_time

                messages.success(request, "✅ Check-Out successful!")
            else:
                messages.warning(request, "⚠️ Check-Out not allowed at this time.")

        attendance.save()
        return redirect("attendance_mark")

    return render(request, "attendance_mark.html", {
        "employee": emp,
        "attendance": attendance,
        "emp_id": emp.id,
        "emp_profile": emp.emp_profile,
        "can_check_in": can_check_in,
        "can_check_out": can_check_out,
        "start_time": start_time,
        "end_time": end_time,
        "is_leave_day": False, 
    })

# ================= Late / Early Exit Reports =================

def attendance_reports(request):
    if 'hr_id' not in request.session:
        return redirect("login")

    hr = HRRegister.objects.get(id=request.session["hr_id"])
    attendance_records = Attendance.objects.filter(employee__hr=hr).order_by('-date')

    return render(request, "attendance_reports.html", {
        "attendance_records": attendance_records
    })

# ================= Late / Early Exit Reports =================

def late_early_reports(request):
    emp_id = request.session.get('emp_id')
    if not emp_id:
        return redirect('login')

    emp = get_object_or_404(Employee, id=emp_id)
    records = Attendance.objects.filter(employee=emp).order_by('-date')

    context = {
        "records": records,
        "emp_profile": emp.emp_profile,
        "emp_id": emp.id,
    }
    return render(request, "late_early_reports.html", context)

def reports_analytics(request):
    # Ensure employee is logged in
    emp_id = request.session.get('emp_id')
    if not emp_id:
        return redirect('login')

    # Fetch employee
    emp = get_object_or_404(Employee, id=emp_id)

    # Get all attendance records
    records = Attendance.objects.filter(employee=emp)

    # === Attendance counts ===
    total_leaves = LeaveRequests.objects.filter(employee=emp, status="APPROVED").count()
    days_present = records.filter(status__iexact="Present").count()
    days_late = records.filter(status__iexact="Late").count()
    days_early_exit = records.filter(status__iexact="Early Exit").count()
    days_late_early = records.filter(status__iexact="Late / Early Exit").count()
    days_absent = records.filter(status__iexact="Absent").count()

    # Optional: total work days (for percentage display)
    total_days = (
        days_present + days_late + days_early_exit + days_late_early + days_absent + total_leaves
    )

    emp_profile = emp.emp_profile.url if emp.emp_profile else None

    context = {
        "emp_profile": emp_profile,
        "emp_id": emp.id,
        "total_leaves": total_leaves,
        "days_present": days_present,
        "days_late": days_late,
        "days_early_exit": days_early_exit,
        "days_late_early": days_late_early,
        "days_absent": days_absent,
        "total_days": total_days,
    }
    return render(request, "reports_analytics.html", context)

def hr_employee_attendance_list(request):
    if 'hr_id' not in request.session:
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])
    attendance_records = Attendance.objects.filter(employee__hr=hr).order_by('-date')

    return render(request, 'hr_employee_attendance_list.html', {
        "attendance_records": attendance_records
    })



def hr_late_early_exit(request):
    if 'hr_id' not in request.session:
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])

    # Include "Late", "Early Exit", "Late / Early Exit", and "Absent"
    attendance_records = Attendance.objects.filter(
        employee__hr=hr,
        status__in=["Late", "Early Exit", "Late / Early Exit", "Absent"]
    ).order_by('-date')

    return render(request, 'hr_late_early_exit.html', {
        "attendance_records": attendance_records
    })

def hr_reports_analytics(request):
    if 'hr_id' not in request.session:
        return redirect('login')

    hr_id = request.session['hr_id']
    employees = Employee.objects.filter(hr_id=hr_id)

    # ✅ Totals
    total_employees = employees.count()
    total_leaves = LeaveRequests.objects.filter(employee__hr_id=hr_id, status='APPROVED').count()

    attendance_records = Attendance.objects.filter(employee__hr_id=hr_id)

    total_present = attendance_records.filter(status="Present").count()
    total_late = attendance_records.filter(status="Late").count()
    total_early_exit = attendance_records.filter(status="Early Exit").count()
    total_late_early = attendance_records.filter(status="Late / Early Exit").count()
    total_absent = attendance_records.filter(status="Absent").count()

    # ✅ Chart data for each employee
    employee_names = []
    days_present = []
    days_late = []
    days_early_exit = []
    days_late_early_exit = []
    days_absent = []
    days_leave = []

    for emp in employees:
        employee_names.append(emp.emp_name)
        emp_attendance = Attendance.objects.filter(employee=emp)
        days_present.append(emp_attendance.filter(status='Present').count())
        days_late.append(emp_attendance.filter(status='Late').count())
        days_early_exit.append(emp_attendance.filter(status='Early Exit').count())
        days_late_early_exit.append(emp_attendance.filter(status='Late / Early Exit').count())
        days_absent.append(emp_attendance.filter(status='Absent').count())
        days_leave.append(LeaveRequests.objects.filter(employee=emp, status='APPROVED').count())

    context = {
        "total_employees": total_employees,
        "total_present": total_present,
        "total_late": total_late,
        "total_early_exit": total_early_exit,
        "total_late_early": total_late_early,
        "total_absent": total_absent,
        "total_leaves": total_leaves,
        "employee_names": json.dumps(employee_names),
        "days_present": json.dumps(days_present),
        "days_late": json.dumps(days_late),
        "days_early_exit": json.dumps(days_early_exit),
        "days_late_early_exit": json.dumps(days_late_early_exit),
        "days_absent": json.dumps(days_absent),
        "days_leave": json.dumps(days_leave),
    }

    return render(request, "hr_reports_analytics.html", context)


# -------------------------------------------------------------------------
# ✅ Generate payroll for a specific employee
# -------------------------------------------------------------------------

def generate_payroll(request, payroll_id):
    """
    Show payroll summary based on the EXACT payroll row clicked in payroll_list.
    - Recalculate ONLY when the payroll belongs to the current month and is not paid.
    - For past months, show the stored (frozen) values so summary matches payroll_list.
    """
    if 'hr_id' not in request.session:
        messages.error(request, "Access denied. Please log in as HR.")
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])

    # Load EXACT payroll entry by payroll_id
    payroll = get_object_or_404(
        MonthlyPayroll,
        id=payroll_id,
        employee__hr=hr
    )

    employee = payroll.employee
    today = date.today()

    # Recalculate only if this payroll is for the current month & not already paid
    current_month = today.strftime("%B")
    if payroll.month == current_month and payroll.year == today.year and not payroll.is_paid:
        payroll.calculate_salary()

    # Convert month name → number safely
    try:
        month_number = list(calendar.month_name).index(payroll.month)
    except ValueError:
        payroll.next_pay_date = None
        payroll.can_pay = False
        return render(request, "payroll_summary.html", {
            "employee": employee,
            "payroll": payroll,
            "today": today,
        })

    # Calculate 1st day of next month
    if month_number == 12:
        next_month_date = date(payroll.year + 1, 1, 1)
    else:
        next_month_date = date(payroll.year, month_number + 1, 1)

    payroll.next_pay_date = next_month_date   # runtime only (not saved)

    # Payment logic (same as payroll_list)
    if payroll.is_paid:
        payroll.can_pay = False
    else:
        # If current month => locked until next month 1st
        if payroll.month == current_month and payroll.year == today.year:
            payroll.can_pay = today >= next_month_date
        else:
            # previous month → allow late payment
            payroll.can_pay = True

    return render(request, "payroll_summary.html", {
        "employee": employee,
        "payroll": payroll,
        "today": today,
    })

# -------------------------------------------------------------------------
# ✅ Generate payroll for all employees (supports both normal & AJAX)
# -------------------------------------------------------------------------

def generate_all_payroll(request):
    """Generate payroll for ALL employees under this HR for the current month."""
    if 'hr_id' not in request.session:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"error": "Access denied"}, status=403)
        messages.error(request, "Access denied. Please log in as HR.")
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])
    employees = Employee.objects.filter(hr=hr)

    month = date.today().strftime("%B")
    year = date.today().year

    generated_count = 0

    for emp in employees:
        payroll, created = MonthlyPayroll.objects.get_or_create(
            employee=emp,
            month=month,
            year=year
        )
        if payroll.is_paid:
            continue

        payroll.calculate_salary()
        generated_count += 1

    # ✅ For AJAX: Return JSON response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            "success": True,
            "generated_count": generated_count,
            "month": month,
            "year": year
        }, status=200)

    # ✅ For normal access
    messages.success(request, f"✅ Payroll generated for {generated_count} employees ({month} {year})")
    return redirect("payroll_list")


# -------------------------------------------------------------------------
# ✅ Payroll list (filtered by HR + supports auto-refresh)
# -------------------------------------------------------------------------

def payroll_list(request):
    """
    Payroll list view (updated).
    - Auto-generate new month payroll when last-record month != current month.
    - Load BOTH current month and previous month payrolls (so late-pay is visible).
    - Recalculate salary ONLY for the current month (so new holidays reflect immediately).
    - Do NOT recalculate previous months (they remain frozen) to avoid retro changes.
    - Compute next_pay_date on the fly (do NOT persist here).
    - Set payroll.can_pay based on today's date vs next_pay_date (and is_paid).
    """

    if 'hr_id' not in request.session:
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])
    today = date.today()

    # -------------------------
    # 1) Auto-generate new month payroll when month changed
    # -------------------------
    latest = MonthlyPayroll.objects.filter(employee__hr=hr).order_by('-year', '-id').first()

    current_month = today.strftime("%B")
    current_year = today.year

    if latest:
        last_month = latest.month
        last_year = latest.year

        if last_month != current_month or last_year != current_year:
            # Create payrolls for the new month (if not already created)
            generate_monthly_payroll(hr)

    # -------------------------
    # 2) Load current month + previous month payrolls
    # -------------------------
    if today.month == 1:
        prev_month_number = 12
        prev_year = today.year - 1
    else:
        prev_month_number = today.month - 1
        prev_year = today.year

    prev_month_name = list(calendar.month_name)[prev_month_number]

    payrolls = MonthlyPayroll.objects.filter(
        employee__hr=hr
    ).filter(
        Q(month=prev_month_name, year=prev_year) | Q(month=current_month, year=current_year)
    ).select_related("employee").order_by('-year', '-id')

    # 2B) ENSURE EVERY ACTIVE EMPLOYEE HAS PAYROLL FOR CURRENT MONTH
    # ------------------------------------------------------------------
    employees = Employee.objects.filter(hr=hr)  # use your Employee model

    existing_emp_ids = payrolls.filter(
        month=current_month,
        year=current_year
    ).values_list("employee_id", flat=True)

    missing_employees = employees.exclude(id__in=existing_emp_ids)

    # Auto-create payroll for new employees added mid-month
    for emp in missing_employees:
        MonthlyPayroll.objects.create(
            employee=emp,
            month=current_month,
            year=current_year
        )

    # Reload payrolls AFTER creating missing rows
    payrolls = MonthlyPayroll.objects.filter(
        employee__hr=hr
    ).filter(
        Q(month=prev_month_name, year=prev_year) |
        Q(month=current_month, year=current_year)
    ).select_related("employee").order_by('-year', '-id')
    
    # -------------------------
    # 3) Set next_pay_date (runtime) and can_pay flag
    # -------------------------
    for p in payrolls:

        # Determine month number safely
        try:
            month_number = list(calendar.month_name).index(p.month)
        except ValueError:
            p.next_pay_date = None
            p.can_pay = False
            continue

        # next pay date: 1st day of month AFTER payroll.month (based on payroll.year)
        if month_number == 12:
            next_month_date = date(p.year + 1, 1, 1)
        else:
            next_month_date = date(p.year, month_number + 1, 1)

        # attach as runtime attribute (do NOT save automatically here)
        p.next_pay_date = next_month_date

        # If it's the CURRENT month (this payroll row belongs to current month/year),
        # recalculate so recent changes (holidays/attendance) reflect immediately.
        if p.month == current_month and p.year == current_year:
            # Recalculate only for current month and if payroll not paid
            if not p.is_paid:
                p.calculate_salary()
            # Payment allowed only after next_month_date
            p.can_pay = today >= next_month_date
            continue

        # For PREVIOUS months: DO NOT recalculate (freeze).
        # Keep DB values as they were when the payroll was created.
        if p.is_paid:
            p.can_pay = False
        else:
            # Allow late payment for previous months (HR rule)
            p.can_pay = True

    context = {
        "payrolls": payrolls,
        "month": current_month,
        "year": current_year,
        "today": today,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "partials/payroll_table.html", context)

    return render(request, "payroll_list.html", context)



# -------------------------------------------------------------------------
# ✅ Give salary (mark payroll as paid)
# -------------------------------------------------------------------------

def give_salary(request, payroll_id=None):

    if 'hr_id' not in request.session:
        return redirect('login')

    hr = HRRegister.objects.get(id=request.session["hr_id"])
    today = date.today()

    payroll_ids = request.GET.get("ids")

    # MULTIPLE EMPLOYEES
    if payroll_ids:
        id_list = [int(x) for x in payroll_ids.split(",") if x.isdigit()]
        payrolls = MonthlyPayroll.objects.filter(id__in=id_list, employee__hr=hr)
        multiple = True

        employee = None
        payroll = None

    else:
        # SINGLE EMPLOYEE
        payroll = get_object_or_404(MonthlyPayroll, id=payroll_id, employee__hr=hr)
        payrolls = [payroll]
        multiple = False
        employee = payroll.employee

    # ⭐ NEXT PAY DATE CHECK
    for p in payrolls:
        if p.is_paid and p.next_pay_date and p.next_pay_date > today:
            return render(request, "give_salary_payu.html", {
                "error": f"❌ Salary already paid. Next payment allowed only after {p.next_pay_date}.",
                "payrolls": payrolls,
                "multiple": multiple,
                "employee": employee,
                "payroll": payroll,
                "today": today,
            })

    # ⭐ BANK DETAILS CHECK
    for p in payrolls:
        emp = p.employee
        if not emp.bank_holder_name or not emp.bank_account_number or not emp.bank_ifsc:
            return render(request, "give_salary_payu.html", {
                "error": f"❌ {emp.emp_name} has no bank details added!",
                "payrolls": payrolls,
                "multiple": multiple,
                "employee": employee,
                "payroll": payroll,
                "today": today,
            })

    # ⭐ MULTIPLE TOTAL
    total_amount = sum(p.net_salary for p in payrolls)

    return render(request, "give_salary_payu.html", {
        "payrolls": payrolls,
        "multiple": multiple,
        "total_amount": total_amount,
        "employee": employee,
        "payroll": payroll,
        "today": today,
    })



# -------------------------------------------------------------------------
# 🏖️ Company Holiday Management
# -------------------------------------------------------------------------


def manage_holidays(request):
    """Add, view, and manage company holidays (HR only)."""
    if 'hr_id' not in request.session:
        messages.error(request, "Access denied. Please log in as HR.")
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])
    today = date.today()  

    # Handle form submission (add new holiday)
    if request.method == "POST":
        name = request.POST.get("holiday_name")
        date_str = request.POST.get("holiday_date")
        holiday_date = parse_date(date_str)

        if name and holiday_date:

            if holiday_date < today:
                messages.error(request, "❌ Cannot create holidays for past dates.")
                return redirect("manage_holidays")
            
            # Prevent duplicates
            exists = CompanyHoliday.objects.filter(hr=hr, holiday_date=holiday_date).exists()
            if exists:
                messages.warning(request, f"A holiday already exists on {holiday_date}.")
            else:
                CompanyHoliday.objects.create(hr=hr, holiday_name=name, holiday_date=holiday_date)
                messages.success(request, f"✅ Holiday '{name}' added for {holiday_date}.")
        else:
            messages.error(request, "Please fill in both name and date.")

        return redirect("manage_holidays")

    # Retrieve all holidays for the logged-in HR
    holidays = CompanyHoliday.objects.filter(hr=hr).order_by("holiday_date")

    return render(request, "manage_holidays.html", {
        "holidays": holidays
    })


def delete_holiday(request, holiday_id):
    """Delete a company holiday."""
    if 'hr_id' not in request.session:
        messages.error(request, "Access denied. Please log in as HR.")
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])
    holiday = get_object_or_404(CompanyHoliday, id=holiday_id, hr=hr)

    holiday.delete()
    messages.success(request, f"🗑️ Holiday '{holiday.holiday_name}' deleted successfully.")
    return redirect("manage_holidays")


# -------------------- SUNDAY OFF TOGGLE (FINAL WORKING VERSION) --------------------


def toggle_sunday_off(request):
    """Enable Sunday Off ONCE. After enabling, it becomes permanently locked."""

    if 'hr_id' not in request.session:
        messages.error(request, "Access denied. Please log in as HR.")
        return redirect('login')

    hr = get_object_or_404(HRRegister, id=request.session['hr_id'])

    # ❌ If Sunday Off is already ON -> Do NOT allow editing
    if hr.is_sunday_off:
        messages.error(request, "Sunday Off is permanently locked and cannot be edited.")
        return redirect('HR_page')

    # Checkbox sends "on" if checked
    is_on = request.POST.get("is_sunday_off") == "on"

    # ✔ When turning ON → lock forever
    if is_on:
        hr.is_sunday_off = True   # TURN ON
        hr.save()

        messages.success(request, "✅ Sunday Off enabled! It is now permanently locked.")
        return redirect('HR_page')

    else:
        # HR tried turning it OFF → but since first time OFF is default → Off is allowed ONLY before enabling
        messages.info(request, "Sunday Off remains disabled.")
        return redirect('HR_page')


def bank_details(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)

    if request.method == "POST":
        employee.bank_holder_name = request.POST.get("account_holder")
        employee.bank_account_number = request.POST.get("account_number")
        employee.bank_ifsc = request.POST.get("ifsc")
        employee.save()

        messages.success(request, "Bank details updated successfully!")
        return redirect("employee_profile", emp_id=emp_id)

    return render(request, "bank_details.html", {"employee": employee})


def view_payslip(request, payroll_id):
    payroll = get_object_or_404(MonthlyPayroll, id=payroll_id)

    if not payroll.is_paid:
        return HttpResponse("Payslip will be available after payment.")
    
    role = request.session.get("user_role", "")
    is_employee = (role == "EMPLOYEE")


    return render(request, "payslip.html", {
        "payroll": payroll,
        "employee": payroll.employee,
        "is_employee": is_employee
    })


def check_bank_details(request, emp_id):
    """AJAX check: Does employee have bank details?"""
    try:
        employee = Employee.objects.get(id=emp_id)
    except Employee.DoesNotExist:
        return JsonResponse({"status": "missing"})  # employee not found

    has_bank = (
        bool(employee.bank_holder_name) and
        bool(employee.bank_account_number) and
        bool(employee.bank_ifsc)
    )

    if has_bank:
        return JsonResponse({"status": "ok"})
    else:
        return JsonResponse({"status": "missing"})


from calendar import monthrange

def generate_monthly_payroll(hr):
    """
    OPTION-B:
    ✔ New month payroll generates on date 1
    ✔ Previous month remains visible
    ✔ Previous month can still be paid (late pay allowed)
    ✔ Payroll must NOT be recalculated after salary paid
    """

    today = date.today()
    month = today.strftime("%B")
    year = today.year

    # ❌ Already created → don't regenerate
    if MonthlyPayroll.objects.filter(employee__hr=hr, month=month, year=year).exists():
        return

    employees = Employee.objects.filter(hr=hr)

    total_days = monthrange(year, today.month)[1]  # days in new month

    for emp in employees:

        # -----------------------------------------
        # 1️⃣ Get LAST month's payroll (if exists)
        # -----------------------------------------
        last_payroll = MonthlyPayroll.objects.filter(
            employee=emp
        ).order_by('-year', '-id').first()

        # -----------------------------------------
        # 2️⃣ If last month unpaid → DO NOT recalc
        # Just copy the previous month numbers
        # -----------------------------------------
        if last_payroll and not last_payroll.is_paid:

            gross_salary = last_payroll.gross_salary
            deductions = last_payroll.deductions
            net_salary = last_payroll.net_salary

            present_days = last_payroll.total_present
            leave_days = last_payroll.total_leave
            absent_days = last_payroll.total_absent
            late_days = last_payroll.total_late
            late_early_days = last_payroll.total_late_early
            weekly_offs = last_payroll.weekly_offs
            holidays = last_payroll.holidays

        else:
            # -----------------------------------------
            # 3️⃣ Fresh calculation for new month only
            # -----------------------------------------
            gross_salary = emp.emp_salary if emp.emp_salary else 0

            present_days = Attendance.objects.filter(
                employee=emp, date__year=year, date__month=today.month, status="Present"
            ).count()

            leave_days = Attendance.objects.filter(
                employee=emp, date__year=year, date__month=today.month, status="Leave"
            ).count()

            absent_days = Attendance.objects.filter(
                employee=emp, date__year=year, date__month=today.month, status="Absent"
            ).count()

            late_days = emp.late_count
            late_early_days = emp.late_early_exit
            weekly_offs = 4 if hr.is_sunday_off else 0

            holidays = CompanyHoliday.objects.filter(
                hr=hr,
                holiday_date__year=year,
                holiday_date__month=today.month
            ).count()

            per_day = gross_salary / total_days
            deductions = absent_days * per_day
            net_salary = gross_salary - deductions

        # -----------------------------------------
        # 4️⃣ Next pay date = 1st of NEXT month
        # -----------------------------------------
        if today.month == 12:
            next_month_date = date(year + 1, 1, 1)
        else:
            next_month_date = date(year, today.month + 1, 1)

        # -----------------------------------------
        # 5️⃣ Create payroll for NEW MONTH
        # -----------------------------------------
        MonthlyPayroll.objects.create(
            employee=emp,
            month=month,
            year=year,
            total_present=present_days,
            total_leave=leave_days,
            total_absent=absent_days,
            total_late=late_days,
            total_late_early=late_early_days,
            holidays=holidays,
            weekly_offs=weekly_offs,
            gross_salary=gross_salary,
            deductions=round(deductions, 2),
            net_salary=round(net_salary, 2),
            next_pay_date=next_month_date,
            is_paid=False
        )
