import io

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.models import User, auth, Group
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models.functions import TruncMonth
from django.db import transaction
from django.template.loader import render_to_string
# from weasyprint import HTML
import tempfile

from django.template.loader import get_template
from xhtml2pdf import pisa
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from django.http import FileResponse
# from django.core.files.storage import FileSystemStorage
from itertools import chain
from django.urls import reverse
import plotly.express as px
import calendar
from django.db.models.functions import Cast, ExtractMonth, ExtractDay, ExtractYear
import csv
import time
import os
from django.utils.timezone import now
from django.core.exceptions import MultipleObjectsReturned
from django.db import IntegrityError, transaction
from .models import Vehicle, Profile, Unit, Coupons, Requests, Transaction, comment, CouponBatch, fueldump, UserGroup, \
    settings
from .models import activityReport
from .utils import render_to_pdf
from django.db.models import Count, F, Value, Sum, Q, Count, Max, CASCADE, Min, FloatField, Avg
from django.db.models.base import ObjectDoesNotExist
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import DateField, Subquery, OuterRef
from .forms import *
from plotly.offline import plot
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import datetime
from django.db.models.functions import Cast
from email.message import EmailMessage
from django.core.mail import EmailMultiAlternatives
from django.core import serializers
from flask import Flask
from django.template import RequestContext
from django.http import HttpResponseRedirect
import sys
from django.contrib.auth.decorators import login_required
import threading


# Create your views here.

# This def handles the data on the nav bar or the main template
@login_required(login_url='login')
def preloaddata(request):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    setting = settings.objects.all()
    server_url = settings.objects.values_list('appurl', flat=True)[0]
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), Q(ret=0) | Q(ret=1), requesterid=current_user)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), Q(ret=0) | Q(ret=1))
        msg_co = msg.count()

    # Diesel market current rate
    dcm = Transaction.objects.filter(marketrate__gt=0.1, ftype='Diesel').last()
    if dcm == None:
        dcurmark = None
    else:
        dcurmark = dcm
    # Petrol market current rate
    pcm = Transaction.objects.filter(marketrate__gt=0.1, ftype='Petrol').last()
    if pcm == None:
        pcurmark = None
    else:
        pcurmark = pcm
    # Stock for nav alerts center
    stck = Coupons.objects.annotate(current_balance=F('total') - F('transamount'))
    if stck == None:
        stocks = None
    else:
        stocks = stck

    context = {
        'server_url': server_url,
        'stocks': stocks,
        'setting': setting[0],
        'dcurmark': dcurmark,
        'pcurmark': pcurmark,
        'role': role[0],
        'user_p': user_p,
        'current_user': current_user,
        'current_user_id': current_user_id,
        'msg': msg,
        'msg_co': msg_co

    }
    return context


# This is the dashboard display data.
@login_required(login_url='login')
def dashboard(request):
    def scatter():
        try:
            reqlist = pd.DataFrame(list(Requests.objects.all().values().filter(Q(ret=0) | Q(ret=1))))
            current_year = datetime.datetime.now().year  # get current year
            reqlist['year'] = pd.DatetimeIndex(reqlist['datemodified']).year
            reql = reqlist[reqlist['year'] == current_year]
            temp = pd.DataFrame({'requesterid': reql['requesterid'].value_counts()})
            df = temp[temp.index != 'Unspecified']
            df = df.sort_values(by='requesterid', ascending=True)
            x1 = df.index
            y1 = df.requesterid
            trace = go.Bar(
                x=x1,
                y=y1
            )
            layout = dict(
                title='Number of Requests by Users in ' + str(current_year),
                yaxis=dict(range=[min(y1), max(y1)])
            )

            fig = go.Figure(data=[trace], layout=layout)
            plot_div = plot(fig, output_type='div', include_plotlyjs=False)
            return plot_div

        except KeyError:
            messages.info(request, "Some data missing!")

        except ValueError:
            messages.info(request, "Some data missing!")

    try:
        today = datetime.datetime.now()
        current_user = request.user.username
        current_user_id = request.user.id
        role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
        user_p = Profile.objects.get(user=current_user_id)
        vehnum = Requests.objects.values('vnum').filter(Q(ret=0) | Q(ret=1), created_at__year=today.year).annotate(
            vcount=Count('vnum'))

        # Area Chart Data
        month_req = Requests.objects.filter(Q(ret=0) | Q(ret=1), created_at__year=today.year) \
            .annotate(month=TruncMonth('created_at')) \
            .values('month') \
            .annotate(total_req=Count('month')).order_by('month')
        cuser = Requests.objects.filter(requesterid=current_user)
        if role[0] == "Driver":

            return redirect('inbox')
        else:

            pl = (Coupons.objects
                  .values('ftype', 'unit').filter(ftype='Petrol').annotate(maxcount=Max('cid'))
                  .order_by('unit').values_list('maxcount', flat=True)
                  )
            pid = pl
            petrol = (
                Coupons.objects.filter(cid__in=pid).annotate(totalp=Sum('total') - Sum('transamount')).values_list(
                    'totalp', flat=True)).aggregate(tpetrol=Sum('totalp'))

            dl = (Coupons.objects
                  .values('ftype', 'unit').filter(ftype='Diesel').annotate(maxcount=Max('cid'))
                  .order_by('unit').values_list('maxcount', flat=True)
                  )
            did = dl
            diesel = (
                Coupons.objects.filter(cid__in=did).annotate(totald=Sum('total') - Sum('transamount')).values_list(
                    'totald', flat=True)).aggregate(tdiesel=Sum('totald'))

            req = Requests.objects.filter(Q(status=1, ret=0) | Q(status=2, ret=0) | Q(status=1, ret=1)).aggregate(
                pen=Count('rid'))
            rreq = Requests.objects.filter(ret=0, created_at__year=today.year).order_by('-created_at')
            maintemp = preloaddata(request)
            context = {
                'diesel': diesel,
                'petrol': petrol,
                'req': req,
                'msg': maintemp['msg'],
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'stocks': maintemp['stocks'],
                'pcurmark': maintemp['pcurmark'],
                'msg_co': maintemp['msg_co'],
                'rreq': rreq,
                'plot1': scatter(),
                'user_p': user_p,
                'vehnum': vehnum,
                'month_req': month_req,
                'role': maintemp['role']

            }
            return render(request, 'dashboard.html', context)
    except AttributeError:
        current_user_id = request.user.id
        nav1 = Profile.objects.values_list('fname', flat=True).filter(user=current_user_id)
        nav2 = Profile.objects.values_list('lname', flat=True).filter(user=current_user_id)

        messages.info(request, "Some data missing!")
        req1 = 0
        context = {
            'req1': req1,
            'nav1': nav1[0],
            'nav2': nav2[0],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'diesel': diesel,
            'petrol': petrol,
            'user_p': user_p,
            'role': maintemp['role']

        }
        return render(request, 'dashboard.html', context)


# This is what will handle the registration
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        if password == password2:
            if User.objects.filter(email=email).exists():
                messages.info(request, 'Email Already Used')
                return redirect('register')
            elif User.objects.filter(username=username).exists():
                messages.info(request, ' Username Already Used')
                return redirect('register')
            else:
                user = User.objects.create_user(username=username, email=email, password=password)
                user.save();
                return redirect('login')
        else:
            messages.info(request, 'Password Not The Same')
            return redirect('register')

    else:
        return render(request, 'register.html')


def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = auth.authenticate(username=username, password=password)

        if user is not None:
            auth.login(request, user)
            current_user = request.user.id
            if Profile.objects.values_list('status', flat=True).filter(user_id=current_user)[0] == "active":
                return redirect('/')
            else:
                messages.info(request, "Your account is locked. Please contact your system Administration!")
                return redirect('logout')
        else:
            messages.info(request, 'Credentials Invalid')
            return redirect('login')
    else:
        return render(request, 'login.html')


# This is to send email at the background to improve performance of the app
class EmailThreading(threading.Thread):
    def __init__(self, msg):
        self.msg = msg
        threading.Thread.__init__(self)

    def run(self):
        self.msg.send(fail_silently=True)


@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    return redirect('/')

# This is what handles the stock.
@login_required(login_url='login')
def stock(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Driver":
        messages.info(request, "You don't have permission on this page")
        return redirect('404')
    elif maintemp['role'] == "":
        messages.info(request, "You don't have permission on this page")
        return redirect('404')
    else:

        if request.method == 'POST':
            id = request.POST.get('id')
            unit = request.POST.get('unit')
            cdimension = request.POST.get('cdimension')
            ftype = request.POST.get('ftype')
            camount = request.POST.get('camount')

            crdact = Coupons.objects.filter(unit=unit, cdimension=cdimension,
                                            ftype=ftype).last()
            # This is to help in for
            if crdact is None:
                crd = 0
                dbt = 0
            else:
                crd = crdact.credit
                dbt = crdact.debit
            bal = Coupons.objects.values_list('total', flat=True).filter(unit=unit, cdimension=cdimension,
                                                                         ftype=ftype).last()
            tran = Coupons.objects.values_list('transamount', flat=True).filter(unit=unit, cdimension=cdimension,
                                                                                ftype=ftype).last()
            try:
                CouponBatch.objects.filter(id=id).update(used=1)
                bid = CouponBatch.objects.values_list('bookref', flat=True).filter(id=id)[0]
                bls = fueldump.objects.filter(trans_id=0, book_id=bid, used=0).values_list('lnum', flat=True)
                for bl in bls:
                    fueldump.objects.filter(lnum=bl).update(trans_id=1)
                total = int(bal) + int(camount)
                # check if there is a credit activite balance if yes move the credit line else drop the credit line
                # Create new stock line with no credit value carry forward

                if (crd - dbt) == 0:
                    cstock = Coupons.objects.create(book_id=id, unit=unit, cdimension=cdimension,
                                                    ftype=ftype, camount=camount,
                                                    total=total, transamount=tran, stockopen=bal - tran)
                    cstock.save();

                # Create new stock line with credit value carry forward

                elif (crd - dbt) > 0:

                    cstock = Coupons.objects.create(book_id=id, unit=unit, cdimension=cdimension,
                                                    ftype=ftype, camount=camount, credit=crdact.credit,
                                                    debit=crdact.debit, note=crdact.note,
                                                    credit_from=crdact.credit_from, credit_status=crdact.credit_status,
                                                    total=total, transamount=tran, stockopen=bal - tran)
                    cstock.save();
                # This is to remove the old record after it's been populated on the new record.
                Coupons.objects.filter(unit=unit, cdimension=cdimension, ftype=ftype).first().delete()

                return redirect('stock')
            except TypeError or IntegrityError:

                total = int(camount)
                bal = int(camount)
                tran = 0
                CouponBatch.objects.filter(id=id, bdel=0).update(used=1)
                bid = CouponBatch.objects.values_list('bookref', flat=True).filter(id=id, bdel=0)[0]
                bls = fueldump.objects.filter(trans_id=0, book_id=bid, used=0).values_list('lnum', flat=True)
                for bl in bls:
                    fueldump.objects.filter(lnum=bl).update(trans_id=1)
                cstock = Coupons.objects.create(book_id=id, unit=unit, cdimension=cdimension, ftype=ftype,
                                                camount=camount,
                                                total=total, transamount=0, stockopen=bal - tran)
                cstock.save();
                return redirect('stock')
        else:

            # tra = Transaction.objects.values('unit','cdimension','ftype').annotate(camount = Sum('cnumber'))
            t = Coupons.objects.values('unit', 'cdimension', 'ftype').annotate(cid=Max('cid')).values_list('cid',
                                                                                                           flat=True)  # Get only the ids
            # Annotate debit balance or credit balance by subtracting debit from credit
            stocks = Coupons.objects.filter(
                cid__in=t).annotate(current_balance=F('total') - F('transamount'), credit_bal=F('credit') - F('debit'))

            js = CouponBatch.objects.values('id', 'unit', 'dim', 'ftype', 'totalAmount').filter(bdel=0)
            books = CouponBatch.objects.filter(used=0, bdel=0, hide=0).values()

            # books = serializers.serialize('json', qs)
            # srq = email_stock(request, id)

            context = {
                # 'disp':srq['disp'],
                'stocks': stocks,
                'books': books,
                'js': js,
                'dcurmark': maintemp['dcurmark'],
                'settings': maintemp['setting'],
                'pcurmark': maintemp['pcurmark'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co'],
                'user_p': maintemp['user_p'],
                'role': maintemp['role']
            }
            return render(request, 'stock.html', context)

@login_required(login_url='login')
def creditStock(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Issuer' or maintemp['role'] == 'Admin':
        if request.method == "POST":
            aunit = request.POST.get('aunit')  # This will be the listed item the operation is been conduct on
            funit = request.POST.get('funit')  # This is the account selected for the operation
            trans = request.POST.get('transaction')  # This is the kind of transaction, if debit or credit
            credit = request.POST.get('amount')  # This is the amount involved in the transaction
            ftype = request.POST.get('ftype')  # This is the fuel type
            cdimension = request.POST.get('cdimension')  # This is the dimension of the coupon
            current_balance = request.POST.get('current_balance')
            note = request.POST.get('note')
            # We should be able to create a new stock line with all the previous values but just the amount affected
            # Check if it's debit or credit

            if trans == "1":
                leaveUpdate = fueldump.objects.filter(unit=funit, dim=cdimension, ftype=ftype, used=0, trans_id=1)
                bookupdate = Coupons.objects.filter(unit=funit, cdimension=cdimension, ftype=ftype)
                if len(leaveUpdate) >= int(credit) and int(current_balance) <= \
                        bookupdate.values_list('camount', flat=True)[0]:
                    Coupons.objects.filter(cid=pk).update(credit=F('credit') + credit, total=F('total') + credit,
                                                          credit_status=trans, credit_from=funit, note=note)
                    # We should add to the debit account to match the books and stock link
                    Coupons.objects.filter(unit=funit, cdimension=cdimension, ftype=ftype). \
                        update(debit=F('debit') + credit, credit_status=2, total=F('total') - credit, credit_from=aunit,
                               note=note)
                    # We should be able to update the leaves or fueldumps with the new unit
                    ls = int(credit)
                    lus = leaveUpdate[0:ls]
                    for lu in lus:
                        lu.unit = aunit
                        lu.save()
                else:
                    messages.warning(request, 'The stock is not enough to conduct this transaction')
        return redirect('stock')
    else:
        return redirect(perm)

@login_required(login_url='login')
def requestlist(request):
    current_user_id = request.user.id
    user_p = Profile.objects.get(user=current_user_id)
    return render(request, 'requestlist.html', {'user_p': user_p})

@login_required(login_url='login')
def inbox(request):
    today = datetime.datetime.now()
    current_user = request.user.username
    maintemp = preloaddata(request)
    if maintemp['role'] == "":
        messages.info(request, "You don't have permission on this page")
        return redirect('404')
    elif maintemp['role'] == "Driver":
        unapprove = Requests.objects.filter(Q(status=1, ret=0) | Q(status=1, ret=1)).filter(requesterid=current_user)
        paginator_una = Paginator(unapprove, 10)  # Show 10 contacts per page.
        page_number_una = request.GET.get('page')
        page_obj_unap = paginator_una.get_page(page_number_una)

        approve = Requests.objects.filter(status=2, ret=0).filter(requesterid=current_user)
        paginator_app = Paginator(approve, 10)  # Show 10 contacts per page.
        page_number_app = request.GET.get('page')
        page_obj_app = paginator_app.get_page(page_number_app)
        issu = Transaction.objects.select_related('tid').annotate(amount=F('tid__amount'),
                                                                  approverid=F('tid__approverid'),
                                                                  issueid=F('tid__issueid'),
                                                                  requesterid=F('tid__requesterid'),
                                                                  rid=F('tid__rid'), vnum=F('tid__vnum'),
                                                                  reqdate=F('tid__created_at'),
                                                                  status=F('tid__status')). \
            values('amount', 'approverid', 'issueid', 'rid', 'vnum', 'marketrate', 'requesterid', 'ftype', 'reqdate',
                   'status', 'sign').filter(tid__status=3, tid__ret=0, tid__requesterid=current_user,
                                            created_at__year=today.year, created_at__month=today.month).order_by('sign',
                                                                                                                 '-reqdate')
        paginator_iss = Paginator(issu, 10)  # Show 10 contacts per page.
        page_number_iss = request.GET.get('page')
        page_obj_iss = paginator_iss.get_page(page_number_iss)

        context = {
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'page_obj_unap': page_obj_unap,
            'page_obj_app': page_obj_app,
            'page_obj_iss': page_obj_iss,
            'user_p': maintemp['user_p'],
            'role': maintemp['role']
        }
        return render(request, 'inbox.html', context)

    else:
        unapprove = Requests.objects.filter(Q(status=1, ret=0) | Q(status=1, ret=1))
        paginator_una = Paginator(unapprove, 10)  # Show 10 contacts per page.
        page_number_una = request.GET.get('page')
        page_obj_unap = paginator_una.get_page(page_number_una)

        approve = Requests.objects.filter(status=2, ret=0)
        paginator_app = Paginator(approve, 10)  # Show 10 contacts per page.
        page_number_app = request.GET.get('page')
        page_obj_app = paginator_app.get_page(page_number_app)

        issu = Transaction.objects.select_related('tid'). \
            annotate(amount=F('tid__amount'), approverid=F('tid__approverid'), issueid=F('tid__issueid'),
                     requesterid=F('tid__requesterid'),
                     rid=F('tid__rid'), vnum=F('tid__vnum'), reqdate=F('tid__created_at'), status=F('tid__status')). \
            values('amount', 'approverid', 'issueid', 'rid', 'vnum', 'marketrate', 'requesterid', 'ftype', 'reqdate',
                   'status', 'sign').filter(tid__status=3, tid__ret=0, created_at__year=today.year).order_by('sign',
                                                                                                             '-reqdate')
        paginator_iss = Paginator(issu, 10)  # Show 10 contacts per page.
        page_number_iss = request.GET.get('page')
        page_obj_iss = paginator_iss.get_page(page_number_iss)

        context = {
            'page_obj_unap': page_obj_unap,
            'page_obj_app': page_obj_app,
            'page_obj_iss': page_obj_iss,
            'dcurmark': maintemp['dcurmark'],
            'settings': maintemp['setting'],
            'pcurmark': maintemp['pcurmark'],
            'user_p': maintemp['user_p'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'role': maintemp['role']
        }
        return render(request, 'inbox.html', context)


@login_required(login_url='login')
def requester(request):
    current_user = request.user.username
    maintemp = preloaddata(request)
    vlist = Vehicle.objects.all()
    if maintemp['role'] == "Driver" or maintemp['role'] == "Admin":
        if request.method == 'POST':
            vnum = request.POST.get('vnum')
            comm = request.POST.get('comm')
            mread = request.POST.get('mread')
            # tankcat = request.POST.get('mread')


            stats = Requests.objects.values_list('status', flat=True).filter(Q(vnum=vnum), Q(ret=1) | Q(ret=0),
                                                                             Q(vnum=vnum)
                                                                             ).last()
            mileage = Requests.objects.values_list('mread', flat=True).filter(Q(vnum=vnum), Q(ret=1) | Q(ret=0),
                                                                              Q(vnum=vnum)
                                                                              ).last()
            inmileage = Vehicle.objects.values_list('imile', flat=True).filter(vnum=vnum)[0]
            incpm = Vehicle.objects.values_list('cpm', flat=True).filter(vnum=vnum)[0]
            # t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0] # Tank capacity

            tncat = int(mread) - int(mileage)

            # This is for tank status algorithm
            # if (t / (tncat * incpm)) <= 1:
            #     tankcat = "empty"
            # elif (t / (tncat * incpm)) > 1 and (t /  (tncat * incpm)) <= 2:
            #     tankcat = "half"
            # elif (t / (tncat * incpm)) > 2 and (t / (tncat * incpm)) <= 3:
            #     tankcat = "3quarter"
            # elif (t / (tncat * incpm)) > 3 and (t / (tncat * incpm)) <= 4:
            #     tankcat = "quarter"


            if stats == 3 or stats == None:

                if stats == 3 and int(mileage) < int(mread) or \
                        stats == None and int(inmileage) < int(mread):
                    tank = (tncat * incpm)
                        # tank = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    fuel = Vehicle.objects.filter(vnum=vnum)
                    req = Requests.objects.create(vnum=vnum, ftype=fuel.values_list('ftype', flat=True),
                                                      mread=mread, requesterid=current_user,
                                                      unit=fuel.values_list('asunit', flat=True),
                                                      amount=tank, comm=comm, status=1, ret=0)
                    req.save();
                    # if tankcat == 'empty':
                    #     tank = t
                    #     # tank = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    #     fuel = Vehicle.objects.filter(vnum=vnum)
                    #     req = Requests.objects.create(vnum=vnum, ftype=fuel.values_list('ftype', flat=True),
                    #                                   mread=mread, requesterid=current_user,
                    #                                   tankcat=tankcat, unit=fuel.values_list('asunit', flat=True),
                    #                                   amount=tank, comm=comm, status=1, ret=0)
                    #     req.save();
                    # # elif tankcat == 'quarter':
                    #     # t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    #     fuel = Vehicle.objects.filter(vnum=vnum)
                    #     tankmath = float(t) / 4
                    #     tank = t - tankmath
                    #     req = Requests.objects.create(vnum=vnum, ftype=fuel.values_list('ftype', flat=True),
                    #                                   mread=mread, requesterid=current_user,
                    #                                   tankcat=tankcat, unit=fuel.values_list('asunit', flat=True),
                    #                                   amount=tank, comm=comm, status=1, ret=0)
                    #     req.save();
                    # elif tankcat == 'half':
                    #     # t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    #     fuel = Vehicle.objects.filter(vnum=vnum)
                    #     tankmath = float(t) / 2
                    #     tank = t - tankmath
                    #     req = Requests.objects.create(vnum=vnum, ftype=fuel.values_list('ftype', flat=True),
                    #                                   mread=mread, requesterid=current_user,
                    #                                   tankcat=tankcat, unit=fuel.values_list('asunit', flat=True),
                    #                                   amount=tank, comm=comm, status=1, ret=0)
                    #     req.save();
                    # elif tankcat == '3quarter':
                    #     # t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    #     fuel = Vehicle.filter(vnum=vnum)
                    #     s = 3 / 4
                    #     tankmath = float(s) * float(t)
                    #     tank = t - tankmath
                    #     req = Requests.objects.create(vnum=vnum, ftype=fuel.values_list('ftype', flat=True),
                    #                                   mread=mread, requesterid=current_user,
                    #                                   tankcat=tankcat, unit=fuel.values_list('asunit', flat=True),
                    #                                   amount=tank, comm=comm, status=1, ret=0)
                    #     req.save();
                    email = \
                        Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(
                            user1=current_user, status='active') \
                            .values_list('email', flat=True)[0]
                    emial_group = Profile.objects.values_list('email', flat=True).filter(
                        Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
                    recipients = list(i for i in emial_group if bool(i))
                    try:

                        subject, from_email, to = 'New Request for Coupon add by ' + current_user, 'service.gm@undp.org', recipients
                        text_content = 'This is an important message.'
                        html_content = '<p>Coupon request for <strong>' + vnum + '</strong> go to the link below.' \
                                                                                 '<br>' \
                                                                                 f'<a href="{maintemp["server_url"]}/inbox">Request Item</a></p>' \
                                                                                 '<br> ' \
                                                                                 '<p> Thank you ???? </p>'
                        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
                        msg.attach_alternative(html_content, "text/html")
                        EmailThreading(msg).start()

                        subject, from_email, to = 'New Request for Coupon add by ' + current_user, 'service.gm@undp.org', email
                        text_content = 'This is an important message.'
                        html_content = '<p>Your coupon request for <strong>' + vnum + '</strong> was created, go to the link below.' \
                                                                                      '<br>' \
                                                                                      f'<a href="{maintemp["server_url"]}/inbox">Request Item</a></p>' \
                                                                                      '<br> ' \
                                                                                      '<p> Thank you ???? </p>'
                        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
                        msg.attach_alternative(html_content, "text/html")

                        EmailThreading(msg).start()
                        messages.success(request, 'Request Successfully Submitted!')
                        return redirect('inbox')
                    except TimeoutError:
                        messages.warning(request, 'Unable to send email but request created!!')
                        return redirect('inbox')


                else:
                    messages.warning(request, "The Mileage indicated is less than the last mileage!")
                    context = {
                        'vlist': vlist,
                        'msg': maintemp['msg'],
                        'settings': maintemp['setting'],
                        'dcurmark': maintemp['dcurmark'],
                        'pcurmark': maintemp['pcurmark'],
                        'msg_co': maintemp['msg_co'],
                        'user_p': maintemp['user_p'],
                        'role': maintemp['role']
                    }
                    return render(request, 'requester.html', context)
            else:
                messages.info(request, f"The Vehicle {vnum} already has a request in progress!")
                context = {
                    'vlist': vlist,
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'settings': maintemp['setting'],
                    'user_p': maintemp['user_p'],
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'role': maintemp['role']
                }
                return render(request, 'requester.html', context)
        else:
            context = {
                'vlist': vlist,
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                'user_p': maintemp['user_p'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co'],
                'role': maintemp['role']
            }
            return render(request, 'requester.html', context)
    else:
        return redirect('404')


@login_required(login_url='login')
def approve(request, pk):
    maintemp = preloaddata(request)
    current_user = request.user.username
    vnum = Requests.objects.values_list('vnum', flat=True).get(rid=pk)
    req = Requests.objects.values_list('requesterid', flat=True).get(rid=pk)
    emial_group = Profile.objects.values_list('email', flat=True).filter(
        Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
    recipients = list(i for i in emial_group if bool(i))
    email = \
        Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=req, status='active') \
            .values_list('email', flat=True)[0]
    if maintemp['role'] == "Approver":
        Requests.objects.filter(rid=pk, status=1).update(status=2,
                                                         ret=0, approverid=current_user)
        if request.method == "POST":
            message = request.POST.get('message')
            if len(message) != 0:
                mg = comment.objects.create(message=message, username=current_user, rid=pk)
                mg.save();

        try:
            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', recipients
            text_content = 'This is an important message.'
            html_content = '<p>Coupon requested by <strong>' + str(
                req) + '</strong> was approved, go to the link below.' \
                       '<br>' \
                       f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                       '<br> ' \
                       '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', email
            text_content = 'This is an important message.'
            html_content = '<p>Your coupon requested has been approved by <strong>' + current_user + \
                           '</strong> go to the link below.' \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                           '<br> ' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()
            return redirect('inbox')
        except TimeoutError:
            messages.warning(request, "Unable to send email but request Approved!!")
            return redirect('inbox')
    elif maintemp['role'] == "Admin":
        Requests.objects.filter(rid=pk).update(status=2, ret=0, approverid=current_user)
        if request.method == "POST":
            message = request.POST.get('message')
            if len(message) != 0:
                mg = comment.objects.create(message=message, sername=current_user, rid=pk)
                mg.save();
        try:
            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', recipients
            text_content = 'This is an important message.'
            html_content = '<p>Coupon requested by <strong>' + str(
                req) + '</strong> was approved, go to the link below.' \
                       '<br>' \
                       f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                       '<br> ' \
                       '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', email
            text_content = 'This is an important message.'
            html_content = '<p>Your coupon requested has been approved by <strong>' + current_user + \
                           '</strong> go to the link below.' \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                           '<br> ' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            return redirect('inbox')
        except TimeoutError:
            messages.warning(request, "Unable to send email but request Approved!!")
            return redirect('inbox')
    else:
        messages.warning(request, "You don't have permission on this page")
        return redirect('404')


@login_required(login_url='login')
def ret(request, pk):
    maintemp = preloaddata(request)
    current_user = request.user.username
    vnum = Requests.objects.values_list('vnum', flat=True).get(rid=pk)
    req = Requests.objects.values_list('requesterid', flat=True).get(rid=pk)
    email = \
        Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=req, status='active') \
            .values_list('email', flat=True)[0]
    email2 = \
        Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1 = maintemp['current_user'], status='active') \
            .values_list('email', flat=True)[0]

    if maintemp['role'] == "Approver":
        Requests.objects.filter(rid=pk).update(status=1, ret=1, retid=current_user)
        if request.method == "POST":
            message = request.POST.get('message')
            if len(message) != 0:
                mg = comment.objects.create(message=message, sername=current_user, rid=pk)
                mg.save();

        subject, from_email, to = 'Coupon requested for ' + str(
            vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = f'<p>Dear {req}, </p>' \
                       '&nbsp; &nbsp;'' &nbsp; &nbsp; Your coupon request was returned by Approver <strong>' + current_user + \
                       '</strong> go to the link below.' \
                       '<br>' \
                       f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                       '<p> Thank you ???? </p>'
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()
        if req != maintemp['current_user']:
            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Returned by ' + req, 'service.gm@undp.org', email2
            text_content = 'This is an important message.'
            html_content = f'<p>Dear {req}, </p>' \
                           f'&nbsp; &nbsp;'f' &nbsp; &nbsp; {req} coupon request was returned by Approver <strong>' + current_user + \
                           '</strong> go to the link below.' \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

        return redirect('inbox')
    elif maintemp['role'] == "Issuer":
        Requests.objects.filter(rid=pk).update(status=1, ret=1, retid=current_user)
        if request.method == "POST":
            message = request.POST.get('message')
            if len(message) != 0:
                mg = comment.objects.create(message=message, sername=current_user, rid=pk)
                mg.save();

        subject, from_email, to = 'Coupon requested for ' + str(
            vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = f'<p>Dear {req}, </p>' \
                       '&nbsp; &nbsp;'' &nbsp; &nbsp; Your coupon request was returned by Issuer <strong>' + current_user + \
                       '</strong> go to the link below.' \
                       '<br>' \
                       f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                       '<p> Thank you ???? </p>'
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()

        if req != maintemp['current_user']:
            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email2
            text_content = 'This is an important message.'
            html_content = f'<p>Dear {current_user}, </p>' \
                           '&nbsp; &nbsp;'f' &nbsp; &nbsp; {req} coupon request was returned by Issuer <strong> {current_user}' \
                           '</strong> go to the link below.' \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

        return redirect('inbox')
    elif maintemp['role'] == "Admin":
        Requests.objects.filter(rid=pk).update(status=1, ret=1, retid=current_user)
        if request.method == "POST":
            message = request.POST.get('message')
            if len(message) != 0:
                mg = comment.objects.create(message=message, username=current_user, rid=pk)
                mg.save();

        subject, from_email, to = 'Coupon requested for ' + str(
            vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = f'<p>Dear {req}, </p>' \
                       '&nbsp; &nbsp;'f' &nbsp; &nbsp; Your coupon request was returned by <strong>{current_user}' \
                       '</strong> go to the link below.' \
                       '<br>' \
                       f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                       '<p> Thank you ???? </p>'
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()

        if req != maintemp['current_user']:
            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email2
            text_content = 'This is an important message.'
            html_content = f'<p>Dear {current_user}, </p>' \
                           '&nbsp; &nbsp;'f' &nbsp; &nbsp; {req} coupon request was returned by <strong> {current_user}' \
                           '</strong> go to the link below.' \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

        return redirect('inbox')
    else:
        messages.warning(request, "You don't have permission on this page")
        return redirect('404')


@login_required(login_url='login')
def delete(request, pk):
    try:
        current_user = request.user.username
        current_user_id = request.user.id
        role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
        dreq = Requests.objects.filter(rid=pk, requesterid=current_user).values('requesterid')[0]['requesterid']
        if dreq == current_user:
            Requests.objects.filter(rid=pk).update(ret=2)
            messages.success(request, 'Successfully deleted')
            return redirect('inbox')

        elif role[0] == "Admin":
            Requests.objects.filter(rid=pk).update(ret=2)
            messages.success(request, 'Successfully deleted')
            return redirect('inbox')

    except IndexError:
        messages.warning(request, "You can't delete items created by other users")
        return redirect('inbox')


@login_required(login_url='login')
def approvalflow(request, pk):
    try:
        current_user_id = request.user.id
        current_user = request.user.username
        role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
        maintemp = preloaddata(request)
        t = Requests.objects.values_list('status', flat=True).filter(rid=pk)
        psign = Requests.objects.values_list('requesterid', flat=True).filter(rid=pk)
        sig = Transaction.objects.values_list('sign', flat=True).filter(tid=pk)
        markt = Transaction.objects.values_list('marketrate', flat=True).filter(tid=pk)
        fileup = Transaction.objects.values_list('uploadedFile', flat=True).filter(tid=pk)

        if request.method == 'POST' and len(request.FILES) != 0:
            receipt = Transaction.objects.get(tid=pk)
            try:
                if len(receipt.uploadedFile) > 0:
                    os.remove(receipt.uploadedFile.path)
                receipt.uploadedFile = request.FILES['uploadedFile']
                receipt.save()
                return redirect('approvalflow', str(pk))
            except FileNotFoundError:
                receipt.uploadedFile = request.FILES['uploadedFile']
                receipt.save()
                return redirect('approvalflow', str(pk))

        elif request.method == 'POST' and t[0] == 3 and sig[0] == "0" and markt[0] == 0 and role[0] != 'Driver':
            Transaction.objects.filter(tid=pk).update(marketrate=request.POST.get('marketrate'))
            req = Requests.objects.filter(rid=pk)
            us = User.objects.filter(username=req.values_list('requesterid', flat=True)[0])
            pf = Profile.objects.filter(user=us.values_list('id', flat=True)[0])
            vnum = req.values_list('vnum', flat=True)[0]
            email = pf.values_list('email', flat=True)[0]

            subject, from_email, to = 'Coupon market rate added by ' + current_user, 'service.gm@undp.org', [email]
            text_content = 'This is an important message.'
            html_content = '<p> The market price for <strong>' + vnum + 'Coupon' \
                                                                        '</strong> was added by <strong>' + current_user + '</strong> go to the link below.' \
                                                                                                                           '<br>' \
                                                                                                                           f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                                                                                                                           '<br> ' \
                                                                                                                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            return redirect('approvalflow', str(pk))

        elif request.method == 'POST' and t[0] == 3 and sig[0] == "0" and markt[0] != 0 and len(fileup[0]) > 2 and \
                psign[0] == request.user.username:
            Transaction.objects.filter(tid=pk).update(sign=request.POST.get('sign'))
            activityReport.objects.filter(tid=pk).update(sign=request.POST.get('sign'))

            req = Requests.objects.filter(rid=pk)
            us = User.objects.filter(username=req.values_list('issueid', flat=True)[0])
            pf = Profile.objects.filter(user=us.values_list('id', flat=True)[0])
            vnum = req.values_list('vnum', flat=True)[0]
            email = pf.values_list('email', flat=True)[0]

            subject, from_email, to = 'Coupon signed by ' + current_user, 'service.gm@undp.org', [email]
            text_content = 'This is an important message.'
            html_content = '<p> The Coupon for <strong>' + vnum + \
                           '</strong> was signed by <strong>' + current_user + '</strong> go to the link below.' \
                                                                               '<br>' \
                                                                               f'<a href="{maintemp["server_url"]}/approvalflow/{pk}">Request Item</a></p>' \
                                                                               '<br> ' \
                                                                               '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            return redirect('approvalflow', str(pk))


        elif Requests.objects.filter(Q(status=1) | Q(status=2), rid=pk):
            aflow = Requests.objects.get(rid=pk)
            comm = comment.objects.values_list('rid', flat=True).filter(rid=pk)[0]
            context = {
                'aflow': aflow,
                'comm': comm,
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co'],
                'user_p': maintemp['user_p'],
                'psign': psign,
                'role': maintemp['role']
            }
            return render(request, 'approvalflow.html', context)
        elif Requests.objects.filter(status=3, rid=pk):
            aflow = Requests.objects.get(rid=pk)
            rflow = Transaction.objects.get(tid=pk)
            comm = comment.objects.values_list('rid', flat=True).filter(rid=pk)[0]

            if Transaction.objects.values_list('marketrate', flat=True).get(tid=pk) != 0:
                lit = Transaction.objects.annotate(makrate=F('totalamount') / F('marketrate')).get(tid=pk)
                context = {
                    'aflow': aflow,
                    'rflow': rflow,
                    'lit': lit,
                    'settings': maintemp['setting'],
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'comm': comm,
                    'user_p': maintemp['user_p'],
                    'role': maintemp['role']
                }
                return render(request, 'approvalflow.html', context)
            else:
                lit = float(0.0)
                context = {
                    'aflow': aflow,
                    'rflow': rflow,
                    'lit': lit,
                    'comm': comm,
                    'settings': maintemp['setting'],
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'user_p': maintemp['user_p'],
                    'role': maintemp['role']
                }
                return render(request, 'approvalflow.html', context)

    except ObjectDoesNotExist:
        messages.warning(request, ' This is record does not exist! Please contact your system Administrator')
        return redirect('inbox')

    except MultipleObjectsReturned:
        messages.warning(request, ' This is a duplicate record! Please contact your system Administrator')
        return redirect('inbox')

    except IntegrityError:
        messages.warning(request, ' Please sign or enter the current fuel market rate, Contact the Issuer')
        return redirect('approvalflow', pk)
    except IndexError:
        try:
            current_user_id = request.user.id
            role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
            t = Requests.objects.values_list('status', flat=True).filter(rid=pk)
            psign = Requests.objects.values_list('requesterid', flat=True).filter(rid=pk)
            sig = Transaction.objects.values_list('sign', flat=True).filter(tid=pk)
            markt = Transaction.objects.values_list('marketrate', flat=True).filter(tid=pk)
            maintemp = preloaddata(request)

            if request.method == 'POST' and t[0] == 3 and sig[0] == "0" and markt[0] == 0 and role[0] != 'Driver':
                Transaction.objects.filter(tid=pk).update(marketrate=request.POST.get('marketrate'))
                return redirect('approvalflow', str(pk))

            elif request.method == 'POST' and t[0] == 3 and sig[0] == "0" and markt[0] != 0 and psign[
                0] == request.user.username:
                Transaction.objects.filter(tid=pk).update(sign=request.POST.get('sign'))
                return redirect('approvalflow', str(pk))

            elif Requests.objects.filter(Q(status=1) | Q(status=2), rid=pk):
                aflow = Requests.objects.get(rid=pk)
                context = {
                    'aflow': aflow,
                    'settings': maintemp['setting'],
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'user_p': maintemp['user_p'],
                    'psign': psign,
                    'role': maintemp['role']
                }
                return render(request, 'approvalflow.html', context)

            elif Requests.objects.filter(status=3, rid=pk):
                aflow = Requests.objects.get(rid=pk)
                rflow = Transaction.objects.get(tid=pk)

                if Transaction.objects.values_list('marketrate', flat=True).get(tid=pk) != 0:
                    lit = Transaction.objects.annotate(makrate=F('totalamount') / F('marketrate')).get(tid=pk)
                    context = {
                        'aflow': aflow,
                        'rflow': rflow,
                        'settings': maintemp['setting'],
                        'dcurmark': maintemp['dcurmark'],
                        'pcurmark': maintemp['pcurmark'],
                        'msg': maintemp['msg'],
                        'msg_co': maintemp['msg_co'],
                        'lit': lit,
                        'user_p': maintemp['user_p'],
                        'role': maintemp['role']
                    }
                    return render(request, 'approvalflow.html', context)

                else:
                    lit = float(0.0)
                    context = {
                        'aflow': aflow,
                        'rflow': rflow,
                        'settings': maintemp['setting'],
                        'dcurmark': maintemp['dcurmark'],
                        'pcurmark': maintemp['pcurmark'],
                        'msg': maintemp['msg'],
                        'msg_co': maintemp['msg_co'],
                        'lit': lit,
                        'user_p': maintemp['user_p'],
                        'role': maintemp['role']
                    }
                    return render(request, 'approvalflow.html', context)
        except ObjectDoesNotExist:
            return redirect('inbox')
        except MultipleObjectsReturned:
            messages.warning(request, ' This is a duplicate record! Please contact your system Administrator')
            return redirect('inbox')
        except ValueError:
            return redirect('inbox')
        except IntegrityError:
            messages.info(request, ' Please browse and upload a file. Your have not selected a file.')
            return redirect('approvalflow', pk)


@login_required(login_url='login')
def requests(request):
    current_user = request.user.username
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    maintemp = preloaddata(request)
    if role[0] == "Driver":

        r = Requests.objects.filter(Q(status=1, ret=0) |
                                    Q(status=1, ret=1) |
                                    Q(status=2, ret=0) |
                                    Q(status=3, ret=0)).filter(requesterid=current_user).order_by('-datemodified')
        context = {
            'requests': r,
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'user_p': maintemp['user_p'],
            'role': maintemp['role']
        }
        return render(request, 'requests.html', context)
    else:
        r = Requests.objects.filter(
            Q(status=1, ret=0) |
            Q(status=1, ret=1) |
            Q(status=2, ret=0) |
            Q(status=3, ret=0)).order_by('-datemodified')
        context = {
            'requests': r,
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'user_p': maintemp['user_p'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'role': maintemp['role']
        }
        return render(request, 'requests.html', context)


@login_required(login_url='login')
def perm(request):
    maintemp = preloaddata(request)
    current_user_id = request.user.id
    user_p = Profile.objects.get(user=current_user_id)
    context = {
        'user_p': user_p,
        'settings': maintemp['setting'],
        'dcurmark': maintemp['dcurmark'],
        'pcurmark': maintemp['pcurmark'],
        'msg': maintemp['msg'],
        'msg_co': maintemp['msg_co'],
        'role': maintemp['role']
    }
    return render(request, '404.html', context)


@login_required(login_url='login')
def nav(request):
    current_user_id = request.user.id
    nav1 = Profile.objects.values_list('fname', flat=True).filter(user=current_user_id)
    nav2 = Profile.objects.values_list('lname', flat=True).filter(user=current_user_id)
    context = {
        'nav': nav1,
        'nav': nav2
    }
    return render(request, 'nav.html', context)

@login_required(login_url='login')
def comments(request):
    current_user = request.user.username
    maintemp = preloaddata(request)
    if request.method == 'POST':
        rid = request.POST.get('rid')
        message = request.POST.get('message')
        comm = comment.objects.create(rid=rid, username=current_user, message=message)
        comm.save();
        messages.info(request, ' Successfully Submitted!')
        requestid = Requests.objects.values_list('requesterid', flat=True).filter(rid=rid)
        email = Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=requestid[0],
                                                                                                     status='active') \
            .values_list('email', flat=True)[0]
        email2 = \
            Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=current_user,
                                                                                                 status='active') \
                .values_list('email', flat=True)[0]

        subject, from_email, to = ' Comment by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = f'{message} <br> <p> go to the link below.' \
                                 '<br>' \
                                 f'<a href="{maintemp["server_url"]}/comments">Request Item</a></p>' \
                                 '<br> ' \
                                 '<p> Thank you ???? </p>'
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()
        if requestid[0] != maintemp['current_user']:
            subject, from_email, to = f' Comment by  {current_user}', 'service.gm@undp.org', email2
            text_content = 'This is an important message.'
            html_content = f'{message} <br> <p> go to the link below.' \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/comments">Request Item</a></p>' \
                           '<br> ' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

        return redirect('comments')
    elif maintemp['role'] == "Driver":

        req = Requests.objects.filter(Q(ret=0) | Q(ret=1),
                                      Q(status=1) | Q(status=2),
                                      requesterid=current_user)
        ir = comment.objects.filter(rid__in=req.values('rid'))
        imgid = []
        for i in ir:
            uid = User.objects.values_list('id', flat=True).filter(username=i.username)[0]
            prof = Profile.objects.values('pic').filter(user=uid)
            img = comment.objects.filter(id=i.id, rid__in=req). \
                annotate(pic=prof, requ=Subquery(req.filter(rid=OuterRef('rid')).values('vnum')[:1])).values('id',
                                                                                                             'rid',
                                                                                                             'username',
                                                                                                             'message',
                                                                                                             'pic',
                                                                                                             'requ',
                                                                                                             'created_at')[
                0]
            imgid.append(img)
        comm = imgid
        requests = Requests.objects.filter(Q(status=1, ret=0) | Q(status=1, ret=1) | Q(status=2, ret=0),
                                           requesterid=current_user)
        context = {
            'comm': comm,
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'user_p': maintemp['user_p'],
            'role': maintemp['role'],
            'requests': requests
        }
        return render(request, 'comment.html', context)
    else:
        req = Requests.objects.values('rid').filter(Q(ret=0) | Q(ret=1),
                                                    Q(status=1) | Q(status=2))

        ir = comment.objects.filter(rid__in=req).all()
        imgid = []
        for i in ir:
            uid = User.objects.values_list('id', flat=True).filter(username=i.username)[0]
            prof = Profile.objects.values('pic').filter(user=uid)
            img = comment.objects.filter(id=i.id).annotate(pic=prof,
                                                           requ=Subquery(req.filter(rid=OuterRef('rid')). \
                                                                         values('vnum')[:1])). \
                values('id', 'rid', 'username', 'message', 'pic', 'requ', 'created_at')[0]
            imgid.append(img)

        requests = Requests.objects.filter(Q(status=1, ret=0) | Q(status=1, ret=1) | Q(status=2, ret=0))
        comm = imgid

        context = {
            'comm': comm,
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'user_p': maintemp['user_p'],
            'role': maintemp['role'],
            'requests': requests
        }
        return render(request, 'comment.html', context)

@login_required(login_url='login')
def itemcomment(request, pk):
    maintemp = preloaddata(request)
    imgid = []
    req = Requests.objects.filter(Q(ret=0) | Q(ret=1))
    ir = comment.objects.filter(rid=pk).all()
    for i in ir:
        uid = User.objects.values_list('id', flat=True).filter(username=i.username)[0]
        prof = Profile.objects.values('pic').filter(user=uid)
        img = comment.objects.filter(id=i.id, rid=pk). \
            annotate(pic=prof, requ=req.values_list('vnum', flat=True).filter(rid=pk)). \
            values('id', 'rid', 'username', 'message', 'pic', 'requ', 'created_at')[0]

        imgid.append(img)
    comm = imgid
    context = {
        'comm': comm,
        'settings': maintemp['setting'],
        'dcurmark': maintemp['dcurmark'],
        'pcurmark': maintemp['pcurmark'],
        'msg': maintemp['msg'],
        'msg_co': maintemp['msg_co'],
        'user_p': maintemp['user_p'],
        'role': maintemp['role']
    }
    return render(request, 'itemcomment.html', context)


@login_required(login_url='login')
def vehicles(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        if request.method == 'POST':
            vnum = request.POST.get('vnum')
            ftype = request.POST.get('ftype')
            vtype = request.POST.get('vtype')
            imile = request.POST.get('imile')
            asunit = request.POST.get('asunit')
            driver = request.POST.get('driver')
            tankcap = request.POST.get('tankcap')
            cpm = request.POST.get('cpm') # Consumption per miles
            veh = Vehicle.objects.create(vnum=vnum, ftype=ftype,
                                         vtype=vtype, imile=imile, asunit=asunit,
                                         driver_id=driver, tankcap=tankcap, cpm=cpm)
            veh.save();
            messages.success(request, 'Request Successfully Submitted!')
            return redirect('vehicles')

        else:
            vlist = Vehicle.objects.all()
            ulist = Unit.objects.all()
            plist = Profile.objects.filter(role='Driver', status='active')

            context = {
                'vlist': vlist,
                'ulist': ulist,
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co'],
                'plist': plist,
                'user_p': maintemp['user_p'],
                'role': maintemp['role']
            }
            return render(request, 'vehicles.html', context)
    else:
        messages.warning(request, "You don't have permission on this page")
        return redirect('404')


@login_required(login_url='login')
def vehedit(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin":
        if request.method == "POST":
            vnum = request.POST.get('vnum')
            ftype = request.POST.get('ftype')
            vtype = request.POST.get('vtype')
            imile = request.POST.get('imile')
            asunit = request.POST.get('asunit')
            driver = request.POST.get('driver')
            tankcap = request.POST.get('tankcap')
            cpm = request.POST.get('cpm')
            Vehicle.objects.filter(vid=pk).update(vnum=vnum, ftype=ftype,
                                                  vtype=vtype, imile=imile, asunit=asunit, driver=driver,
                                                  tankcap=tankcap, cpm=cpm)
            return redirect('vehicles')

    else:
        return redirect('perm')


@login_required(login_url='login')
def vehdel(request, pk):
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == 'Admin':
        Vehicle.objects.filter(vid=pk).delete()
        return redirect('vehicles')
    else:
        return redirect('404')


@login_required(login_url='login')
def delstock(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin' or maintemp['role'] == 'Issuer' or maintemp['role'] == 'Issuer':
        dellist = Coupons.objects.all()
        context = {
            'dellist': dellist,
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'user_p': maintemp['user_p'],
            'role': maintemp['role']
        }
        return render(request, 'delstock.html', context)
    else:
        return redirect('404')


@login_required(login_url='login')
def delst(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        Coupons.objects.filter(cid=pk).delete()
        return redirect('delstock')
    else:
        return redirect('404')


@login_required(login_url='login')
def unit(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        if request.method == 'POST':
            uname = request.POST.get('uname')
            uhead = request.POST.get('uhead')
            capprover = request.POST.get('capprover')
            un = Unit.objects.create(uname=uname, uhead=uhead, capprover=capprover, aptype=0)
            un.save();
            return redirect('unit')
        else:
            units = Unit.objects.all()

            appv = Profile.objects.all().filter(role="Approver", status="active")
            context = {
                'units': units,
                'appv': appv,
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                'user_p': maintemp['user_p'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co'],
                'role': maintemp['role']
            }

            return render(request, 'unit.html', context)
    else:
        messages.warning(request, "You don't have permission on this page")
        return redirect('404')


@login_required(login_url='login')
def unitedit(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        if request.method == 'POST':
            uname = request.POST.get('uname')
            uhead = request.POST.get('uhead')
            capprover = request.POST.get('capprover')
            Unit.objects.filter(uid=pk).update(uname=uname, uhead=uhead, capprover=capprover, aptype=0)
            return redirect('unit')
    else:
        messages.warning(request, "You don't have permission on this page")
        return redirect('404')


@login_required(login_url='login')
def unitdel(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        Unit.objects.filter(uid=pk).delete()
        return redirect('unit')
    else:
        return redirect('404')


@login_required(login_url='login')
def profile(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        prof = Profile.objects.all()
        context = {
            'prof': prof,
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'user_p': maintemp['user_p'],
            'role': maintemp['role']
        }
        return render(request, 'profile.html', context)
    else:
        return redirect('404')


@login_required(login_url='login')
def userGroup(request):
    maintemp = preloaddata(request)

    if maintemp['role'] == "Admin":
        if request.method == "POST":
            groupname = request.POST.get('groupname')
            desc = request.POST.get('desc')
            group = UserGroup.objects.create(groupname=groupname, desc=desc)
            group.save();
            return redirect('userGroup')
        else:
            ug = UserGroup.objects.all()
            context = {
                'ug': ug,
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co'],
                'user_p': maintemp['user_p'],
                'role': maintemp['role']
            }

            return render(request, 'usergroup.html', context)
    else:
        return redirect('404')


@login_required(login_url='login')
def groupedit(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin":
        if request.method == "POST":
            groupname = request.POST.get('groupname')
            desc = request.POST.get('desc')
            group = UserGroup.objects.filter(id=pk).update(groupname=groupname, desc=desc)
            return redirect('userGroup')


@login_required(login_url='login')
def groupdel(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        UserGroup.objects.filter(id=pk).delete()
        return redirect('userGroup')
    else:
        return redirect('404')


# This function handles the transaction. It updates the coupon leaves, create transaction and update the request item
@login_required(login_url='login')
def transac(request, pk):
    current_user = request.user.username
    maintemp = preloaddata(request)
    role = maintemp['role']

    try:
        if role == "Issuer" or role == "Admin":
            if request.method == 'POST':
                cdimension = request.POST.get('cdimension')  # This is for coupon dimension
                ftype = request.POST.get('ftype')  # This is for coupon type
                cnumber = request.POST.get('cnumber')  # This is for number of coupons
                rate = request.POST.get('rate')  # This is for rate per litre of fuel in dalasi
                unit = request.POST.get('unit')  # This is the Unit the vehicles belongs to
                note = request.POST.get('note')  # This is for if there is note like COA etc...
                tid = int(request.POST.get('tid'))
                totalamount = int(cdimension) * int(cnumber)
                quantity = float(totalamount) / float(rate)
                trana = Coupons.objects.values_list('transamount', flat=True).filter(unit=unit, cdimension=cdimension,
                                                                                     ftype=ftype).last()

                if trana:
                    total = Coupons.objects.values_list('total', flat=True).filter(unit=unit, cdimension=cdimension,
                                                                                   ftype=ftype).last()
                    trancheck = int(trana) + int(cnumber)
                    comp = total - trancheck + 1

                else:
                    try:
                        total = Coupons.objects.values_list('total', flat=True).filter(unit=unit, cdimension=cdimension,
                                                                                       ftype=ftype)[0]
                        comp = total - int(cnumber) + 1
                    except IndexError:
                        messages.warning(request, "There is no stock for this unit to issue this amount of Coupon/s")
                        return redirect('transac', str(tid))

                # This needs to be resolve later because if there is no record in the database shows zero even if there is stock.(resolved)
                if comp <= 0:
                    messages.warning(request, "The stock is not enough to issue this amount of Coupon/s")
                    return redirect('transac', str(tid))
                #

                else:
                    bupdate = fueldump.objects.filter(used=0, unit=unit, ftype=ftype, dim=cdimension,
                                                      trans_id=1).all().order_by('lnum')
                    e = int(cnumber)
                    bc = bupdate[:e]
                    c = bc.values_list('lnum', flat=True)
                    cp = Coupons.objects.annotate(am=F('total') - F('transamount')).values_list('am', flat=True). \
                        filter(unit=unit, ftype=ftype, cdimension=cdimension).last()
                    lbu = len(bupdate)
                    # This will check if the transaction doesn't exist and if the book issued is equal to the stock
                    if len(Transaction.objects.filter(tid=tid)) == 0 and cp == lbu:
                        tran = Transaction.objects.create(tid_id=tid, cdimension=cdimension, totalamount=totalamount,
                                                          ftype=ftype,
                                                          cnumber=cnumber, quantity=quantity, rate=rate, marketrate=0,
                                                          sign=0,
                                                          unit=unit, uploadedFile="0", note=note, serialno=min(c),
                                                          maxserialno=max(c))
                        tran.save();

                        Requests.objects.filter(rid=tid).update(status=3,
                                                                ret=0, issueid=str(current_user))

                        t = Coupons.objects.filter(unit=unit, cdimension=cdimension, ftype=ftype).annotate(
                            id=Max('cid')) \
                            .values_list('cid', flat=True)  # Get only the last id of this category.

                        # This is the stock update
                        Coupons.objects.filter(
                            cid__in=t).update(transamount=F('transamount') + int(cnumber))

                        # Update book status rbal
                        for bu in bc:
                            for bu2 in CouponBatch.objects.filter(bookref=bu.book_id):
                                bu2.rbal += 1
                                bu2.save()

                        # This is handling the book update.
                        for i in sorted(c):
                            fueldump.objects.filter(lnum=i).update(used=1, transac=tid, issuer=str(current_user),
                                                                   datemodified=datetime.datetime.now())

                        # This will update the book status
                        bookstat = CouponBatch.objects.filter(status=0, hide=0, bdel=0)

                        for i in bookstat:
                            if len(fueldump.objects.filter(used=0, book_id=i.bookref)) <= 0:
                                CouponBatch.objects.filter(bookref=i.bookref).update(status=1,
                                                                                     rbal=(i.totalAmount) / (i.dim))

                        # calculate fuel consumption by vehicle
                        rq = Requests.objects.filter(rid=tid)
                        cmill = rq.values_list('mread', flat=True)[0]  # Current Milleage
                        clitre = rq.values_list('amount', flat=True)[0]  # Current Litre
                        lmill = activityReport.objects.filter(vnum=rq.values_list('vnum', flat=True)[0]).values_list(
                            'mread', flat=True).last()  # The last millage of this vehicle

                        if lmill:
                            fconsumption = round((cmill - lmill) / clitre, 2)
                        else:
                            lastmill = Vehicle.objects.values_list('imile', flat=True)[0]
                            fconsumption = round((cmill - lastmill) / clitre, 2)

                        # This is handling the Report logs for the monthly and annual fuel usage report
                        fd_s = fueldump.objects.filter(lnum=min(c))
                        fd_e = fueldump.objects.filter(lnum=max(c))
                        if len(comment.objects.filter(rid=tid)) > 0:
                            comm = 1
                        else:
                            comm = 0

                        acreort = activityReport.objects.create(tid=tid, totalamount=totalamount, litre=quantity,
                                                                vnum=rq.values_list('vnum', flat=True),
                                                                mread=rq.values_list('mread', flat=True),
                                                                unit=unit,
                                                                requesterid=rq.values_list('requesterid', flat=True),
                                                                approverid=rq.values_list('approverid', flat=True),
                                                                issueid=rq.values_list('issueid', flat=True),
                                                                serial_start=min(c),
                                                                serial_end=max(c), ftype=ftype,
                                                                bookref_s=fd_s.values_list('book_id', flat=True),
                                                                bookref=fd_e.values_list('book_id', flat=True),
                                                                note=note, comm=comm, cdimension=cdimension,
                                                                fconsumption=fconsumption)
                        acreort.save();

                    else:
                        messages.warning(request,
                                         "The stock and the books are not tally Please contact the Administrator!!!")
                        return redirect('approvalflow', str(tid))

                    emial_group = Profile.objects.values_list('email', flat=True).filter(
                        Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
                    recipients = list(i for i in emial_group if bool(i))
                    req = Requests.objects.values_list('requesterid', flat=True).get(rid=tid)
                    email = \
                        Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=req,
                                                                                                             status='active') \
                            .values_list('email', flat=True)[0]

                    try:
                        subject, from_email, to = 'Coupon requested Issued by ' + current_user, 'service.gm@undp.org', email
                        text_content = 'This is an important message.'
                        html_content = '<p>Your coupon request has been issued by <strong>' + current_user + \
                                       '</strong> go to the link below.' \
                                       '<br>' \
                                       f'<a href="{maintemp["server_url"]}/approvalflow/{tid}">Request Item</a></p>' \
                                       '<br> ' \
                                       '<p> Thank you ???? </p>'
                        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
                        msg.attach_alternative(html_content, "text/html")
                        EmailThreading(msg).start()

                        subject, from_email, to = 'Coupon requested Issued by ' + current_user, 'service.gm@undp.org', recipients
                        text_content = 'This is an important message.'
                        html_content = '<p> Coupon requested by <strong>' + str(req) + \
                                       '</strong> has been issued by <strong>' + current_user + '</strong> go to the link below.' \
                                                                                                '<br>' \
                                                                                                f'<a href="{maintemp["server_url"]}/approvalflow/{tid}">Request Item</a></p>' \
                                                                                                '<br> ' \
                                                                                                '<p> Thank you ???? </p>'
                        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
                        msg.attach_alternative(html_content, "text/html")
                        EmailThreading(msg).start()

                        return redirect('approvalflow', str(tid))

                    except TypeError:
                        messages.warning(request, "Unable to send email but you request is issued!!!")
                        return redirect('approvalflow', str(tid))

            else:
                issue = Requests.objects.get(rid=pk)
                ulist = Unit.objects.all()
                context = {
                    'issue': issue,
                    'settings': maintemp['setting'],
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'ulist': ulist,
                    'user_p': maintemp['user_p'],
                    'role': maintemp['role']
                }
                return render(request, 'issued.html', context)

        else:
            messages.warning(request, "You don't have permission on this page")
            return redirect('404')

    except TimeoutError:
        messages.warning(request, "The stock  does not exit for this coupon dimension")
        return redirect('stock')


@login_required(login_url='login')
def invoice(request, pk):
    return render(request, 'invoice.html')


@login_required(login_url='login')
def user_profile(request, pk):
    current_user_id = request.user.id
    current_user = request.user.username
    maintemp = preloaddata(request)
    role = maintemp['role']
    if role == "Admin":
        try:
            if request.method == 'POST' and len(request.FILES) > 0:
                prof = Profile.objects.get(id=pk)
                if len(prof.pic) > 0:
                    os.remove(prof.pic.path)
                prof.pic = request.FILES['pic']
                prof.save()
                return redirect('user_profile', str(pk))
            elif request.method == 'POST':
                fname = request.POST.get('fname')
                lname = request.POST.get('lname')
                unit = request.POST.get('unit')
                role = request.POST.get('role')
                email = request.POST.get('email')
                status = request.POST.get('status')
                Profile.objects.filter(id=pk).update(fname=fname, lname=lname, unit=unit, role=role, email=email,
                                                     status=status)
                return redirect('user_profile', str(pk))

            else:
                prof_us = Profile.objects.select_related('user_id'). \
                    annotate(email1=F('user_id__email'), user1=F('user_id__username')). \
                    values('email1', 'id', 'fname', 'lname', 'role', 'unit', 'status', 'user_id', 'user1', 'pic',
                           'email').get(
                    id=pk)

                rl = Profile.objects.values_list('role', flat=True).get(id=pk)
                pic = Profile.objects.get(id=pk)
                ug = UserGroup.objects.exclude(groupname=rl)

                tranam = activityReport.objects.filter(requesterid=pic).count()
                tranlast = activityReport.objects.filter(requesterid=pic).last()
                tranpen = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=pic, ret=0).count()
                trantotal = activityReport.objects.values_list('totalamount', flat=True).filter(
                    requesterid=pic).aggregate(total=Sum('totalamount'))

                context = {
                    'prof': prof_us,
                    'ug': ug,
                    'trantotal': trantotal,
                    'tranam': tranam,
                    'tranlast': tranlast,
                    'tranpen': tranpen,
                    'settings': maintemp['setting'],
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'pic': pic,
                    'user_p': maintemp['user_p'],
                    'role': maintemp['role']
                }
                return render(request, 'user_profile.html', context)
        except IntegrityError:
            return redirect('user_profile', pk)

    elif role != "Admin":
        try:
            if request.method == 'POST' and len(request.FILES) > 0:
                prof = Profile.objects.get(id=pk)
                if len(prof.pic) > 0:
                    os.remove(prof.pic.path)
                prof.pic = request.FILES['pic']
                prof.save()
                return redirect('user_profile', str(pk))
            elif request.method == 'POST':
                fname = request.POST.get('fname')
                lname = request.POST.get('lname')
                unit = request.POST.get('unit')
                role = request.POST.get('role')
                email = request.POST.get('email')
                status = request.POST.get('status')
                Profile.objects.filter(id=pk).update(fname=fname, lname=lname, unit=unit, role=role, email=email,
                                                     status=status)
                return redirect('user_profile', str(pk))

            else:
                prof_us = Profile.objects.select_related('user_id'). \
                    annotate(email1=F('user_id__email'), user1=F('user_id__username')). \
                    values('email1', 'id', 'fname', 'lname', 'role', 'unit', 'status', 'user_id', 'user1', 'pic',
                           'email').get(
                    user=current_user_id)

                rl = Profile.objects.values_list('role', flat=True).get(user=current_user_id)
                pic = Profile.objects.get(user=current_user_id)
                ug = UserGroup.objects.exclude(groupname=rl)
                tranam = Requests.objects.filter(requesterid=current_user, ret=0).count()
                try:
                     vehdetail = Vehicle.objects.filter(driver__user=current_user_id).all()[0]  # ForeignKey relationship

                except IndexError:
                    vehdetail = "NA"

                tranlast = Requests.objects.filter(requesterid=current_user, ret=0).last()
                tranpen = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0).count()
                trantotal = activityReport.objects.values_list('totalamount', flat=True).filter(
                    requesterid=pic).aggregate(total=Sum('totalamount'))

                context = {
                    'prof': prof_us,
                    'ug': ug,
                    'vehdetail': vehdetail,
                    'trantotal': trantotal,
                    'tranam': tranam,
                    'tranlast': tranlast,
                    'tranpen': tranpen,
                    'settings': maintemp['setting'],
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'pic': pic,
                    'user_p': maintemp['user_p'],
                    'role': maintemp['role']
                }
                return render(request, 'user_profile.html', context)
        except IntegrityError:
            return redirect('user_profile', pk)
        except ValueError:
            return redirect('user_profile', pk)

    else:
        return redirect('404')

@login_required(login_url='login')
def user_pic(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] != "Driver":
        if request.method == 'POST':
            pic = request.FILES('pic')
            pic1 = Profile.objects.filter(id=pk).update(pic=pic)
            pic1.save()
            return redirect('user_profile', str(pk))
    else:
        return redirect('404')

@login_required(login_url='login')
def login404(request):
    return render(request, '404login.html')


@login_required(login_url='login')
def passwordreset(request, pk):
    current_user = request.user.username
    u = User.objects.get(username__exact=current_user)
    maintemp = preloaddata(request)
    if request.method == 'POST':
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        passwordold = request.POST.get('passwordold')

        if u.check_password(passwordold):
            if password == password_confirm:
                u.set_password(password)
                u.save()
                return redirect('passwordreset', str(pk))
            else:
                messages.info(request, "Password mismatch. Please try again!")
                return render(request, 'passwordreset.html', {'role': maintemp['role'], 'settings': maintemp['setting'],
                                                              'dcurmark': maintemp['dcurmark'],
                                                              'pcurmark': maintemp['pcurmark'],
                                                              'user_p': maintemp['user_p'], 'msg': maintemp['msg'],
                                                              'msg_co': maintemp['msg_co']})
        else:
            messages.info(request, "Incorrect current password. Please try again!")
            return render(request, 'passwordreset.html',
                          {'role': maintemp['role'], 'settings': maintemp['setting'], 'dcurmark': maintemp['dcurmark'],
                           'pcurmark': maintemp['pcurmark'], 'user_p': maintemp['user_p'], 'msg': maintemp['msg'],
                           'msg_co': maintemp['msg_co']})

    else:
        return render(request, 'passwordreset.html',
                      {'role': maintemp['role'], 'settings': maintemp['setting'], 'dcurmark': maintemp['dcurmark'],
                       'pcurmark': maintemp['pcurmark'], 'user_p': maintemp['user_p'], 'msg': maintemp['msg'],
                       'msg_co': maintemp['msg_co']})


@login_required(login_url='login')
def getfile(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        response = HttpResponse(content_type='text/csv')
        now = time.strftime('%d-%m-%Y %H:%M:%S')
        response['Content-Disposition'] = f'attachment; filename="report {now}.csv"'
        stocks = Coupons.objects.all()
        writer = csv.writer(response)
        writer.writerow(['Unit', 'Dimension', 'Fuel Type', 'Stock Amount',
                         'Opening Stock', 'Current Balance', 'Credit', 'Note', 'Date created'])
        for stock in stocks:
            writer.writerow([stock.unit, stock.cdimension, stock.ftype, stock.camount,
                             stock.stockopen, stock.total - stock.transamount, stock.credit - stock.debit,
                             stock.note, stock.created_at])
        return response


@login_required(login_url='login')
def bookreport(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        response = HttpResponse(content_type='text/csv')
        now = time.strftime('%d-%m-%Y %H:%M:%S')
        response['Content-Disposition'] = f'attachment; filename="bookreport {now}.csv"'
        book = CouponBatch.objects.values_list('bookref').filter(id=pk, bdel=0)[0][0]
        bk = book
        leaves = fueldump.objects.all().annotate(vnum=Subquery(
            Requests.objects.filter(rid=OuterRef('transac')).values('vnum').order_by('vnum')[:1]),
            requester=Subquery(
                Requests.objects.filter(rid=OuterRef('transac')).values('requesterid')[:1]
            ),
            approver=Subquery(
                Requests.objects.filter(rid=OuterRef('transac')).values('approverid')[:1]
            )).filter(book_id=bk, used=1).order_by('lnum')

        writer = csv.writer(response)
        writer.writerow(['Book', 'Leave No', 'Fuel Type', 'Used',
                         'Book serial', 'Allocated stock', 'Dimension', 'Requester', 'Approver', 'Issuer', 'Vehicle',
                         'Unit', 'Date modified'])
        for leave in leaves:
            writer.writerow([leave.book, leave.lnum, leave.ftype, leave.used,
                             leave.book_id, leave.trans_id, leave.dim, leave.requester, leave.approver, leave.issuer,
                             leave.vnum, leave.unit, leave.datemodified])
        return response


@login_required(login_url='login')
def couponbooksreport(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        response = HttpResponse(content_type='text/csv')
        now = time.strftime('%d-%m-%Y %H:%M:%S')
        response['Content-Disposition'] = f'attachment; filename="couponbooksreport {now}.csv"'
        books = CouponBatch.objects.all().annotate(quan=Count(Subquery(
            fueldump.objects.filter(book_id=OuterRef('bookref')).values('book_id').filter(used=0)[:1])),
            fmin=Min(Subquery(
                fueldump.objects.filter(book_id=OuterRef('bookref')).values('lnum').filter(used=0)[:1])),
        ).filter(bdel=0, hide=0)
        writer = csv.writer(response)
        writer.writerow(['Book', 'Start Serial', 'End Serial', 'Quantity', 'Fuel Type', 'Unit'])
        for book in books:
            if book.quan == 1:
                writer.writerow([book.book_id, book.fmin, book.serial_end,
                                 int(book.serial_end) + 1 - book.fmin, book.ftype, book.unit])
        return response


@login_required(login_url='login')
def fuelconsreport(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        responsed = HttpResponse(content_type='text/csv')
        now = time.strftime('%d-%m-%Y %H:%M:%S')
        responsed['Content-Disposition'] = f'attachment; filename="fuelconsreport {now}.csv"'
        writer = csv.writer(responsed)
        result = Transaction.objects.select_related('tid').annotate(vehicle=F('tid__vnum')).order_by('vehicle')
        writer.writerow(['Vehicle', 'Fuel Type', 'Litres consume', 'Unit', 'Date created'])
        for res in result:
            writer.writerow([res.vehicle, res.ftype, res.quantity, res.unit, res.created_at])
        return responsed


@login_required(login_url='login')
def translog(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Driver":
        return redirect('404')
    else:

        context = {
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'role': maintemp['role'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'user_p': maintemp['user_p']
        }
        return render(request, 'translog.html', context)


# ------ This is to genrate a unique ID for the books------
import uuid

@login_required(login_url='login')
def couponBatch(request):
    current_user = request.user.username
    try:
        maintemp = preloaddata(request)
        role = maintemp['role']

        if role == "Driver" or role == "Approver":
            return redirect('404')
        else:
            if request.method == "POST":
                if maintemp['role'] == 'Admin' or maintemp['role'] == 'Owner':
                    book_id = request.POST.get('book_id')
                    serial_start = request.POST.get('serial_start')
                    serial_end = request.POST.get('serial_end')
                    dim = request.POST.get('dim')
                    ftype = request.POST.get('ftype')
                    unit = request.POST.get('unit')
                    bookref = uuid.uuid4().hex[:6].upper()
                    ex = CouponBatch.objects.filter(serial_start=serial_start, serial_end=serial_end, bdel=0)
                    ux = CouponBatch.objects.filter(bookref=bookref)
                    if ex:
                        messages.info(request, f"This book exit! book - {serial_start}")
                        return redirect('couponBatch')
                    elif ux:
                        messages.info(request, f"This book is not unique (Hash collision!) {bookref} ")
                        return redirect('couponBatch')
                    else:
                        tx = int(serial_start) - 1  # This is to create the exact number of coupon leaves
                        tm = int(serial_end) - tx  # This creates the number of leaves to be created.
                        totalamount = tm * int(dim)  # This is the amount in cash
                        b = []
                        d = int(serial_start)
                        for i in range(tm):
                            b.append(i + d)

                        # This is what creates the book
                        book = CouponBatch.objects.create(book_id=book_id, serial_start=serial_start, serial_end=serial_end,
                                                          dim=dim, ftype=ftype, unit=unit, totalAmount=totalamount, used=0,
                                                          bdel=0,
                                                          hide=1, rbal=0, status=0, creator=current_user, bookref=bookref)

                        book.save();

                        # This is what create the leaves on the fuel dump table
                        fueldump.objects.bulk_create(
                            [fueldump(lnum=e, book_id=bookref, book=book_id, unit=unit, ftype=ftype,
                                      dim=dim, used=0, trans_id=0, transac=0) for e in b])
                        return redirect("couponNew")

            # elif role == "Owner" or role == "Admin":
            #     # now = datetime.datetime.now()
            #     # one_month_ago = datetime.datetime(now.year, now.month - 1, 1)
            #     # month_end = datetime.datetime(now.year, now.month, 1) - datetime.timedelta(seconds=1)
            #     # two_month_end = datetime.datetime(now.year, now.month, 2) - datetime.timedelta(seconds=1)
            #
            #     # # This is what is handling the book render.
            #     books = CouponBatch.objects.annotate(quan=(F('totalAmount') / F('dim')) - (F('rbal')),
            #                                          percent=100 - (F('rbal') * 100) / (
            #                                                  F('totalAmount') / (F('dim')))).filter(bdel=0). \
            #         all()
            #
            #     # This is for calculating months
            #
            #     ulist = Unit.objects.all()
            #     context = {
            #         'role': maintemp['role'],
            #         'settings': maintemp['setting'],
            #         'dcurmark': maintemp['dcurmark'],
            #         'pcurmark': maintemp['pcurmark'],
            #         'books': books,
            #         'msg': maintemp['msg'],
            #         'msg_co': maintemp['msg_co'],
            #         'ulist': ulist,
            #         'user_p': maintemp['user_p']
            #     }
            #     return render(request, 'couponbatch.html', context)

            # elif role == "Issuer":
            elif role == "Issuer" or role == "Owner" or role == "Admin":
                # This is for calculating months
                # now = datetime.datetime.now()
                # one_month_ago = datetime.datetime(now.year, now.month - 1, 1)
                # month_end = datetime.datetime(now.year, now.month, 1) - datetime.timedelta(seconds=1)

                # This is what is handling the book render.
                books = CouponBatch.objects.annotate(quan=(F('totalAmount') / F('dim')) - (F('rbal')),
                                                     percent=100 - (F('rbal') * 100) / (
                                                             F('totalAmount') / (F('dim')))).filter(used=1, bdel=0). \
                    all()

                ulist = Unit.objects.all()
                context = {
                    'role': maintemp['role'],
                    'settings': maintemp['setting'],
                    'dcurmark': maintemp['dcurmark'],
                    'pcurmark': maintemp['pcurmark'],
                    'books': books,
                    'msg': maintemp['msg'],
                    'msg_co': maintemp['msg_co'],
                    'ulist': ulist,
                    'user_p': maintemp['user_p']
                }
                return render(request, 'couponbatch.html', context)
            else:
                return redirect(perm)
    except IndexError:
        return redirect('couponBatch')

@login_required(login_url='login')
def couponNew(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Owner":
        books = CouponBatch.objects.annotate(quan=(F('totalAmount') / F('dim')) - (F('rbal')),
                                             percent=100 - (F('rbal') * 100) / (
                                                     F('totalAmount') / (F('dim')))).filter(used=0, bdel=0). \
            all()

        ulist = Unit.objects.all()
        context = {
            'role': maintemp['role'],
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'books': books,
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'ulist': ulist,
            'user_p': maintemp['user_p']
        }
        return render(request, 'couponbatch.html', context)

@login_required(login_url='login')
def coupondetail(request, pk):
    try:
        maintemp = preloaddata(request)
        role = maintemp['role']
        if role == "Driver" or role == "Approver":
            return redirect('404')
        else:

            book = CouponBatch.objects.get(Q(bdel=0) | Q(bdel=2), id=pk)
            b = CouponBatch.objects.values_list('bookref', flat=True).filter(id=pk, bdel=0)[0]
            leaves = fueldump.objects.filter(book_id=b).order_by('lnum')
            used = fueldump.objects.filter(book_id=b, used=1).annotate(cn=Count('used')).values_list('cn', flat=True)
            notused = fueldump.objects.filter(book_id=b, used=0).annotate(cn=Count('used')).values_list('cn', flat=True)
            total = fueldump.objects.filter(book_id=b).annotate(cn=Count('used')).values_list('cn', flat=True)
            lastu = fueldump.objects.filter(book_id=b, used=1).annotate(lastmod=Subquery(
                Transaction.objects.filter(tid=OuterRef('transac')).values('created_at')[:1])).order_by(
                'lastmod').last()

            context = {
                'role': maintemp['role'],
                'book': book,
                'used': used,
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co'],
                'lastu': lastu,
                'notused': notused,
                'leaves': leaves,
                'total': total,
                'user_p': maintemp['user_p']
            }
            return render(request, 'coupondetail.html', context)
    except ObjectDoesNotExist:
        return redirect('couponBatch')

@login_required(login_url='login')
def couponprint(request, pk):
    maintemp = preloaddata(request)
    bkid = CouponBatch.objects.filter(id=pk)[0]
    coupleaves = fueldump.objects.filter(book_id=bkid.bookref)
    context ={
        'leaves':coupleaves,
        'bookurl':f"{maintemp['setting'].appurl}/coupondetail/{pk}",
        'bkid':bkid
    }
    return render(request, 'coupons_for_fuel.html',context)

# This is to soft delete a book with it's leave
@login_required(login_url='login')
def deletebook(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Owner":
        b = CouponBatch.objects.filter(id=pk, used=0).values_list('bookref', flat=True)[0]
        lid = fueldump.objects.filter(book_id=b).values_list('lnum', flat=True)
        for i in lid:
            fueldump.objects.filter(lnum=i, used=0).delete()
        CouponBatch.objects.filter(id=pk, used=0).update(bdel=1)
        return redirect('couponBatch')

# This is for issuing or retrieving books
@login_required(login_url='login')
def hidebook(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Owner":
        if CouponBatch.objects.filter(id=pk, used=0, hide=1):
            CouponBatch.objects.filter(id=pk).update(hide=0)
            book = CouponBatch.objects.filter(id=pk, used=0, hide=0)
            email = Profile.objects.filter(role='Issuer',
                status='active').values_list('email', flat=True)[0]
            email2 = Profile.objects.filter(role='Admin', status='active').values_list(
                'email', flat=True)[0]

            subject, from_email, to = ' Book issued by ' + maintemp['current_user'], 'service.gm@undp.org', email
            text_content = 'This is an important message.'
            html_content = f"<p> The book number <strong>{book.values_list('book_id', flat=True)[0]}</strong> has been issued with <strong>{int(book.values_list('serial_end', flat=True)[0]) - int(book.values_list('serial_start', flat=True)[0])+1 }</strong> Leaves. Access the platform from the link below." \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/">Coupon Management system</a></p>' \
                           '<br> ' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            subject, from_email, to = ' Book issued by ' + maintemp['current_user'], 'service.gm@undp.org', email2
            text_content = 'This is an important message.'
            html_content = f"<p> The book number <strong>{book.values_list('book_id', flat=True)[0]}</strong> has been issued with <strong>{int(book.values_list('serial_end', flat=True)[0]) - int(book.values_list('serial_start', flat=True)[0])+1 }</strong> Leaves. Access the platform from the link below." \
                           '<br>' \
                           f'<a href="{maintemp["server_url"]}/">Coupon Management system</a></p>' \
                           '<br> ' \
                           '<p> Thank you ???? </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()


        else:
            CouponBatch.objects.filter(id=pk, used=0, hide=0).update(hide=1)

        return redirect('coupondetail', pk)

# This is for the search
@login_required(login_url='login')
def search(request):
    maintemp = preloaddata(request)
    role = maintemp['role']

    if role == "Driver":
        if request.method == 'POST':
            sear = request.POST.get('sear')

        lst = Requests.objects.filter(Q(vnum__icontains=sear) | Q(requesterid__icontains=sear) |
                                      Q(created_at__icontains=sear), requesterid=request.user.username).order_by(
            '-created_at')[:23]
        context = {
            'settings': maintemp['setting'],
            'role': maintemp['role'],
            'lst': lst,
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'user_p': maintemp['user_p']

        }
        return render(request, 'search.html', context)
    else:
        if request.method == 'POST':
            sear = request.POST.get('sear')

        lst = Requests.objects.filter(Q(vnum__icontains=sear) | Q(requesterid__icontains=sear) |
                                      Q(created_at__icontains=sear)).order_by('-created_at')[:23]
        context = {
            'settings': maintemp['setting'],
            'role': maintemp['role'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co'],
            'lst': lst,
            'user_p': maintemp['user_p']

        }
        return render(request, 'search.html', context)


# This is not in use because the sign function is handle at the transaction logic
@login_required(login_url='login')
def signed(request):
    current_user = request.user
    sign = request.POST.get('sign')
    tid = request.POST.get('tid')
    userid = request.POST.get('userid')

    if request.method == 'POST' and current_user == userid:
        Transaction.objects.filter(tid=tid).update(sign=sign)
        activityReport.objects.filter(tid=tid).update(sign=sign)
        return redirect('approvalflow.html', tid)


@login_required(login_url='login')
def reportpdf(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        today = datetime.datetime.now()  # This is to generate the date today.
        template_name = "report.html"  # This is the template to generate pdf

        # This is for the request
        logs = activityReport.objects.filter(created_at__year=today.year, created_at__month=today.month).order_by(
            "ftype", "-created_at")

        # Report on transaction per request.
        damount = activityReport.objects. \
            filter(created_at__year=today.year, created_at__month=today.month). \
            values('ftype').annotate(asum=Sum('totalamount'), lt=Sum('litre'))

        usr = request.user.username

        # Report on book Balance
        books = CouponBatch.objects.all().annotate(quan=Count(Subquery(
            fueldump.objects.filter(book_id=OuterRef('bookref')).values('book_id').filter(used=0)[:1])),
            fmin=Min(Subquery(
                fueldump.objects.filter(book_id=OuterRef('bookref')).values('lnum').filter(used=0)[:1])),
        ).filter(bdel=0, hide=0)

        # This is the monthly fuel consumption by vehicle report for PDF generator.
        vamount = activityReport.objects. \
            filter(created_at__year=today.year, created_at__month=today.month). \
            values('vnum').order_by('vnum').annotate(lt=Sum('litre'), asum=Sum('totalamount'),
                                                     consum=Avg('fconsumption'))

        # This is the querset that creates the dictionary
        bamount = CouponBatch.objects.values('ftype', 'unit', 'bookref', 'serial_end', 'dim').annotate(
            quan=Count(Subquery(
                fueldump.objects.filter(book_id=OuterRef('bookref')).values('book_id').filter(used=0)[:1])),
            minlnum=Min(Subquery(
                fueldump.objects.filter(book_id=OuterRef('bookref')).values('lnum').filter(used=0)[0:1])),
        ).filter(bdel=0, hide=0)

        # This is for the coupon book total calculations for leaves and cost. Should be improve in the future.
        diesel = 0
        dieselam = 0
        petrolam = 0
        petrol = 0
        for i in bamount:
            if i['quan'] == 1 and i['ftype'] == 'Diesel':
                d = int(i['serial_end']) - i['minlnum']
                da = i['dim'] * (d + 1)
                diesel += d + 1
                dieselam += da
            elif i['quan'] == 1 and i['ftype'] == 'Petrol':
                p = int(i['serial_end']) - i['minlnum']
                pa = i['dim'] * (p + 1)
                petrol += p + 1
                petrolam += pa

        # This for the borrowed coupon report.
        borcoupon = Coupons.objects.annotate(
            credit_debit=F('credit') - F('debit')).order_by('unit', 'ftype',
                                                            'cdimension')

        ce = Coupons.objects.filter(credit__gte=1).last()
        if len(ce.ftype) > 0:
            chckempty = 1
        else:
            chckempty = 0

        return render_to_pdf(
            template_name,
            {
                "logs": logs,
                "borrowed": borcoupon,
                "chckempty": chckempty,
                "usr": usr,
                'settings': maintemp['setting'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                "books": books,
                "diesel": diesel,
                "petrol": petrol,
                "dieselam": dieselam,
                "petrolam": petrolam,
                "vamount": vamount,
                "damount": damount,
            },
        )


# This is for top messages. This is not in use.
@login_required(login_url='login')
def msgtop(request):
    uname = request.user.username
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.get(requesterid=uname)
        # if msg.status != 3:
        #     popmsg = msg

    context = {
        'popmsg': msg
    }
    return render(request, 'nav.html', context)


@login_required(login_url='login')
def requestEdit(request, pk):
    current_user = request.user.username
    maintemp = preloaddata(request)
    if request.method == 'POST':
        rid = request.POST.get('rid')
        mread = request.POST.get('mread')
        vnum = request.POST.get('vnum')
        comm = request.POST.get('comm')
        # This is for the comment section
        message = request.POST.get('message')
        if len(message) != 0:
            mg = comment.objects.create(message=message, username=current_user, rid=rid)
            mg.save();
        # The comment section ends here!!

        stats = Requests.objects.values_list('status', flat=True).filter(Q(ret=0),
                                                                         Q(vnum=vnum), ~Q(rid=rid)
                                                                         ).last()
        mileage = Requests.objects.values_list('mread', flat=True).filter(Q(ret=0),
                                                                          Q(vnum=vnum), ~Q(rid=rid)
                                                                          ).last()
        inmileage = Vehicle.objects.values_list('imile', flat=True).filter(vnum=vnum)[0]
        incpm = Vehicle.objects.values_list('cpm', flat=True).filter(vnum=vnum)[0]
        if mileage == None:
            tncat = int(mread) - int(inmileage)
        else:
            tncat = int(mread) - int(mileage)

        if stats == 3 or stats == None:

            if stats == 3 and int(mileage) < int(mread) or \
                    stats == None and int(inmileage) < int(mread):
                tank = (tncat * incpm)
                Requests.objects.filter(status=1, requesterid=current_user, ret=1, rid=rid).update(mread=mread,
                                                                                                   amount=float(
                                                                                                       tank), comm=comm,
                                                                                                   ret=0)
                emial_group = Profile.objects.values_list('email', flat=True).filter(
                    Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
                recipients = list(i for i in emial_group if bool(i))
                subject, from_email, to = 'Request for Coupon was returned by ' + current_user, 'service.gm@undp.org', recipients
                text_content = 'This is an important message.'
                html_content = '<p>Coupon request for <strong>' + vnum + '</strong> go to the link below.' \
                                                                         '<br>' \
                                                                         f'<a href="{maintemp["server_url"]}/approvalflow/{rid}">Request Item</a></p>' \
                                                                         '<br> ' \
                                                                         '<p> Thank you ???? </p>'
                msg = EmailMultiAlternatives(subject, text_content, from_email, to)
                msg.attach_alternative(html_content, "text/html")
                EmailThreading(msg).start()

            return redirect('approvalflow', rid)

        # try:
        #     if mileage == None:
        #         tncat = int(mread) - int(inmileage)
        #     else:
        #         tncat = int(mread) - int(mileage)
        #
        #     if stats == 3 or stats == None:
        #
        #         if stats == 3 and int(mileage) < int(mread) or \
        #                 stats == None and int(inmileage) < int(mread):
        #
        #             tank = (tncat * incpm)
        #             Requests.objects.filter(status=1, requesterid=current_user, ret=1, rid=rid).update(mread=mread,
        #                                                                                                amount=float(
        #                                                                                                    tank), comm=comm, ret=0)
        #             emial_group = Profile.objects.values_list('email', flat=True).filter(
        #                 Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
        #             recipients = list(i for i in emial_group if bool(i))
        #             subject, from_email, to = 'Request for Coupon was returned by ' + current_user, 'service.gm@undp.org', recipients
        #             text_content = 'This is an important message.'
        #             html_content = '<p>Coupon request for <strong>' + vnum + '</strong> go to the link below.' \
        #                                                                      '<br>' \
        #                                                                      f'<a href="{maintemp["server_url"]}/approvalflow/{rid}">Request Item</a></p>' \
        #                                                                      '<br> ' \
        #                                                                      '<p> Thank you ???? </p>'
        #             msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        #             msg.attach_alternative(html_content, "text/html")
        #             EmailThreading(msg).start()
        #
        #         return redirect('approvalflow', rid)


        # except TypeError:
        #       messages.warning(request, "Unable to send email but you request is issued!!!")
        # return redirect('requestEdit', rid)


    else:
        rq = Requests.objects.get(rid=pk)
        context = {
            'rq': rq,
            'settings': maintemp['setting'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'role': maintemp['role'],
            'user_p': maintemp['user_p'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co']

        }
        return render(request, 'requester_edit.html', context)


@login_required(login_url='login')
def activityreport(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        logs = activityReport.objects.all().order_by("-created_at")
        casham = activityReport.objects.aggregate(Sum('totalamount'))

        context = {
            'settings': maintemp['setting'],
            'role': maintemp['role'],
            'logs': logs,
            'casham': casham,
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'user_p': maintemp['user_p'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co']

        }
        return render(request, 'activityreport.html', context)


@login_required(login_url='login')
def activityDetail(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        activitydtl = activityReport.objects.all().filter(id=pk)[0]
        actlist = activityReport.objects.filter(vnum=activitydtl.vnum)
        actchart = activityReport.objects.filter(vnum=activitydtl.vnum).\
            annotate(month=TruncMonth('created_at')).\
            values('month').\
            annotate(total_litre=Sum('litre')).order_by('month')
        totallit = activityReport.objects.filter(vnum=activitydtl.vnum).\
            aggregate(total_litre=Sum('litre'))
        context = {
            'activitydetail': activitydtl,
            'totallit': totallit,
            'actlist': actlist,
            'actchart': actchart,
            'settings': maintemp['setting'],
            'role': maintemp['role'],
            'dcurmark': maintemp['dcurmark'],
            'pcurmark': maintemp['pcurmark'],
            'user_p': maintemp['user_p'],
            'msg': maintemp['msg'],
            'msg_co': maintemp['msg_co']
        }
        return render(request, 'activitydetail.html', context)

@login_required(login_url='login')
def activitiesExport(request, pk):
    maintemp = preloaddata(request)
    if maintemp['role'] == "Admin" or maintemp['role'] == "Issuer" or maintemp['role'] == "Owner":
        responsed = HttpResponse(content_type='text/csv')
        now = time.strftime('%d-%m-%Y %H:%M:%S')
        responsed['Content-Disposition'] = f'attachment; filename="Activities_Report_{now}.csv"'
        writer = csv.writer(responsed)
        activitydtl = activityReport.objects.all().filter(id=pk)[0]
        result = activityReport.objects.all().filter(vnum=activitydtl.vnum).order_by('created_at')
        writer.writerow(['Serial no', 'Litre', 'Mileage', 'Consumption', 'Unit','Requester','Approver','Issuer',
                         'Comment','Sign', 'Dimension', f"Cost({maintemp['setting'].currency})", 'note','Date'])
        for r in result:
            writer.writerow([f'{r.serial_start} - {r.serial_end}', round(r.litre,2), r.mread, r.fconsumption,
                             r.unit, r.requesterid, r.approverid, r.issueid,
                             r.comm, r.sign, r.cdimension, r.totalamount, r.note, r.created_at.strftime('%Y-%m-%d')])
        return responsed

@login_required(login_url='login')
def vehicle_detail(request, pk):
    maintemp = preloaddata(request)

    context = {
        'settings': maintemp['setting'],
        'role': maintemp['role'],
        'dcurmark': maintemp['dcurmark'],
        'pcurmark': maintemp['pcurmark'],
        'user_p': maintemp['user_p'],
        'msg': maintemp['msg'],
        'msg_co': maintemp['msg_co']

    }
    return render(request, 'vehicle_detail.html', context)


# This is what is handling the stock requesting email.
@login_required(login_url='login')
def email_stock(request, pk):
    current_user = request.user.username
    rstock = Coupons.objects.filter(cid=pk)
    if request.method == 'POST':
        unit = rstock.values_list('unit', flat=True)[0]
        dim = rstock.values_list('cdimension', flat=True)[0]
        ftype = rstock.values_list('ftype', flat=True)[0]
        current_balance = request.POST.get('current_balance')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        emial_group = Profile.objects.values_list('email', flat=True).filter(
            Q(role='Admin') | Q(role='Owner') | Q(role='Issuer') | Q(role='Approver'), status='active').distinct()
        recipients = list(i for i in emial_group if bool(i))
        subject, from_email, to = subject + ' from ' + current_user, 'service.gm@undp.org', recipients
        text_content = 'This is an important message.'
        html_content = '<p>Stock request:' \
                       '<br>' \
                       f'Unit: <strong>{unit}</strong>' \
                       '<br> ' \
                       f'Dimension: <strong>{dim}</strong>' \
                       '<br> ' \
                       f'Fuel Type: <strong>{ftype}</strong>' \
                       '<br> ' \
                       f'Balance: <strong>{current_balance}</strong>' \
                       '<br> ' \
                       f'{message}' \
                       '<br> ' \
                       '<p> Thank you ???? </p>'

        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()

        return redirect('stock')


@login_required(login_url='login')
def setupconfig(request):
    maintemp = preloaddata(request)
    if maintemp['role'] == 'Admin':
        if request.method == 'POST' and len(maintemp['setting'].country) == 0:
            country = request.POST.get('country')
            city = request.POST.get('city')
            currency = request.POST.get('currency')
            address = request.POST.get('address')
            company = request.POST.get('company')
            phone = request.POST.get('phone')
            appurl = request.POST.get('appurl')
            description = request.POST.get('description')
            # logo = request.FILES['logo']
            stup = settings.objects.create(country=country, city=city, currency=currency,
                                           address=address, phone=phone, description=description, company=company,
                                           appurl=appurl)
            stup.save()
            return redirect('setupconfig')
        elif request.method == 'POST' and len(maintemp['setting'].country) > 0:
            country = request.POST.get('country')
            city = request.POST.get('city')
            currency = request.POST.get('currency')
            address = request.POST.get('address')
            company = request.POST.get('company')
            phone = request.POST.get('phone')
            appurl = request.POST.get('appurl')
            description = request.POST.get('description')
            # logo = request.FILES['logo']
            settings.objects.update(country=country, city=city, currency=currency,
                                    address=address, phone=phone, description=description, company=company,
                                    appurl=appurl)
            return redirect('setupconfig')
        else:
            appurl = settings.objects.values_list('appurl', flat=True)
            context = {
                'appurl': appurl,
                'settings': maintemp['setting'],
                'role': maintemp['role'],
                'dcurmark': maintemp['dcurmark'],
                'pcurmark': maintemp['pcurmark'],
                'user_p': maintemp['user_p'],
                'msg': maintemp['msg'],
                'msg_co': maintemp['msg_co']

            }
            return render(request, 'settings.html', context)
