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
from .models import Vehicle, Profile, Unit, Coupons, Requests, Transaction, comment, CouponBatch, fueldump, UserGroup
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
# import gi
# gi.require_version("Gtk", "3.0")
# from gi.repository import Gtk

# Create your views here.
@login_required(login_url='login')
def dashboard(request):
    current_user = request.user
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
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
        vehnum = Requests.objects.values('vnum').filter(Q(ret=0) | Q(ret=1), created_at__year=today.year).annotate(vcount = Count('vnum'))

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
            rreq = Requests.objects.filter(ret=0,  created_at__year=today.year).order_by('-created_at')[:10]
            context = {
                'diesel': diesel,
                'petrol': petrol,
                'req': req,
                'msg': msg,
                'msg_co': msg_co,
                'rreq': rreq,
                'plot1': scatter(),
                'user_p': user_p,
                'vehnum': vehnum,
                'month_req': month_req,
                'role': role[0]

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
            'msg': msg,
            'msg_co': msg_co,
            'diesel': diesel,
            'petrol': petrol,
            'user_p': user_p,
            'role': role[0]

        }
        return render(request, 'dashboard.html', context)

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

@login_required(login_url='login')
def stock(request):
    current_user = request.user
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if role[0] == "Driver":
        messages.info(request, "You don't have permission on this page")
        return redirect('404')
    elif role[0] == "":
        messages.info(request, "You don't have permission on this page")
        return redirect('404')
    else:

        if request.method == 'POST':
            id = request.POST.get('id')
            unit = request.POST.get('unit')
            cdimension = request.POST.get('cdimension')
            ftype = request.POST.get('ftype')
            camount = request.POST.get('camount')
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
                cstock = Coupons.objects.create(book_id=id, unit=unit, cdimension=cdimension, ftype=ftype, camount=camount,
                                                total=total, transamount=tran, stockopen=bal - tran)
                cstock.save();

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
                cstock = Coupons.objects.create(book_id=id, unit=unit, cdimension=cdimension, ftype=ftype, camount=camount,
                                                total=total, transamount=0, stockopen=bal - tran)
                cstock.save();
                return redirect('stock')
        else:

            # tra = Transaction.objects.values('unit','cdimension','ftype').annotate(camount = Sum('cnumber'))
            t = Coupons.objects.values('unit', 'cdimension', 'ftype').annotate(cid=Max('cid')).values_list('cid',
                                                                                                           flat=True)  # Get only the ids
            stocks = (Coupons.objects.values('unit', 'cdimension', 'ftype', 'total', 'camount', 'stockopen').filter(
                cid__in=t)).annotate(current_balance=F('total') - F('transamount'))

            js = CouponBatch.objects.values('id', 'unit','dim','ftype','totalAmount').filter(bdel=0)
            books = CouponBatch.objects.filter(used=0, bdel=0, hide=0).values()

            # books = serializers.serialize('json', qs)

            context = {
                'stocks': stocks,
                'books': books,
                'js': js,
                'msg': msg,
                'msg_co': msg_co,
                'user_p': user_p,
                'role': role[0]
            }
            return render(request, 'stock.html', context)

@login_required(login_url='login')
def requestlist(request):
    current_user_id = request.user.id
    user_p = Profile.objects.get(user=current_user_id)
    return render(request, 'requestlist.html', {'user_p': user_p})

@login_required(login_url='login')
def inbox(request):
    today = datetime.datetime.now()
    current_user = request.user.username
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "":
        messages.info(request, "You don't have permission on this page")
        return redirect('404')
    elif role[0] == "Driver":
        unapprove = Requests.objects.filter(Q(status=1, ret=0) | Q(status=1, ret=1)).filter(requesterid=current_user)
        paginator_una = Paginator(unapprove, 10)  # Show 10 contacts per page.
        page_number_una = request.GET.get('page')
        page_obj_unap = paginator_una.get_page(page_number_una)

        approve = Requests.objects.filter(status=2, ret=0).filter(requesterid=current_user)
        paginator_app = Paginator(approve, 10)  # Show 10 contacts per page.
        page_number_app = request.GET.get('page')
        page_obj_app = paginator_app.get_page(page_number_app)
        issu = Transaction.objects.select_related('tid').annotate(amount=F('tid__amount'), approverid=F('tid__approverid'), issueid=F('tid__issueid'),
                     requesterid=F('tid__requesterid'),
                     rid=F('tid__rid'), vnum=F('tid__vnum'), reqdate=F('tid__created_at'), status=F('tid__status')). \
            values('amount', 'approverid', 'issueid', 'rid', 'vnum', 'marketrate', 'requesterid', 'ftype', 'reqdate',
                   'status', 'sign').filter(tid__status=3, tid__ret=0 ,tid__requesterid=current_user, created_at__year=today.year, created_at__month=today.month).order_by('sign','-reqdate')
        paginator_iss = Paginator(issu, 10)  # Show 10 contacts per page.
        page_number_iss = request.GET.get('page')
        page_obj_iss = paginator_iss.get_page(page_number_iss)
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()
        context = {
            'msg': msg,
            'msg_co': msg_co,
            'page_obj_unap': page_obj_unap,
            'page_obj_app': page_obj_app,
            'page_obj_iss': page_obj_iss,
            'user_p': user_p,
            'role': role[0]
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
                   'status', 'sign').filter(tid__status=3, tid__ret=0, created_at__year=today.year).order_by('sign','-reqdate')
        paginator_iss = Paginator(issu, 10)  # Show 10 contacts per page.
        page_number_iss = request.GET.get('page')
        page_obj_iss = paginator_iss.get_page(page_number_iss)
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()
        context = {
            'page_obj_unap': page_obj_unap,
            'page_obj_app': page_obj_app,
            'page_obj_iss': page_obj_iss,
            'user_p': user_p,
            'msg': msg,
            'msg_co': msg_co,
            'role': role[0]
        }
        return render(request, 'inbox.html', context)

@login_required(login_url='login')
def requester(request):
    current_user = request.user.username
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()

    vlist = Vehicle.objects.values('vnum', 'ftype')
    if role[0] == "Driver" or role[0] == "Admin":
        if request.method == 'POST':
            vnum = request.POST.get('vnum')
            comm = request.POST.get('comm')
            mread = request.POST.get('mread')
            tankcat = request.POST.get('tankcat')

            stats = Requests.objects.values_list('status', flat=True).filter(Q(vnum=vnum), Q(ret=1) | Q(ret=0), Q(vnum=vnum)
                                                                             ).last()
            mileage = Requests.objects.values_list('mread', flat=True).filter(Q(vnum=vnum), Q(ret=1) | Q(ret=0), Q(vnum=vnum)
                                                                             ).last()
            inmileage = Vehicle.objects.values_list('imile', flat=True).filter(vnum=vnum)[0]
            if stats == 3 or stats == None:

                if stats == 3 and int(mileage) < int(mread) or \
                        stats == None and int(inmileage) < int(mread):

                    if tankcat == 'empty':
                        tank = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                        fuel = Vehicle.objects.values_list('ftype', flat=True).filter(vnum=vnum)[0]
                        req = Requests.objects.create(vnum=vnum, ftype=fuel, mread=mread, requesterid=current_user,
                                                      tankcat=tankcat, amount=float(tank), comm=comm, status=1, ret=0)
                        req.save();
                    elif tankcat == 'quarter':
                        t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                        fuel = Vehicle.objects.values_list('ftype', flat=True).filter(vnum=vnum)[0]
                        tankmath = float(t) / 4
                        tank = t - tankmath
                        req = Requests.objects.create(vnum=vnum, ftype=fuel, mread=mread, requesterid=current_user,
                                                      tankcat=tankcat, amount=tank, comm=comm, status=1, ret=0)
                        req.save();
                    elif tankcat == 'half':
                        t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                        fuel = Vehicle.objects.values_list('ftype', flat=True).filter(vnum=vnum)[0]
                        tankmath = float(t) / 2
                        tank = t - tankmath
                        req = Requests.objects.create(vnum=vnum, ftype=fuel, mread=mread, requesterid=current_user,
                                                      tankcat=tankcat, amount=tank, comm=comm, status=1, ret=0)
                        req.save();
                    elif tankcat == '3quarter':
                        t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                        fuel = Vehicle.objects.values_list('ftype', flat=True).filter(vnum=vnum)[0]
                        s = 3 / 4
                        tankmath = float(s) * float(t)
                        tank = t - tankmath
                        req = Requests.objects.create(vnum=vnum, ftype=fuel, mread=mread, requesterid=current_user,
                                                      tankcat=tankcat, amount=tank, comm=comm, status=1, ret=0)
                        req.save();
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
                                                                                 f'<a href="http://127.0.0.1:8000/inbox">Request Item</a></p>' \
                                                                                 '<br> ' \
                                                                                 '<p> Thank you 😊 </p>'
                        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
                        msg.attach_alternative(html_content, "text/html")
                        EmailThreading(msg).start()

                        subject, from_email, to = 'New Request for Coupon add by ' + current_user, 'service.gm@undp.org', email
                        text_content = 'This is an important message.'
                        html_content = '<p>Your coupon request for <strong>' + vnum + '</strong> was created, go to the link below.' \
                                                                                 '<br>' \
                                                                                 f'<a href="http://127.0.0.1:8000/inbox">Request Item</a></p>' \
                                                                                 '<br> ' \
                                                                                 '<p> Thank you 😊 </p>'
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
                         'msg': msg,
                         'msg_co': msg_co,
                         'user_p': user_p,
                         'role': role[0]
                     }
                     return render(request, 'requester.html', context)
            else:
                messages.info(request, f"The Vehicle {vnum} already has a request in progress!")
                context = {
                    'vlist': vlist,
                    'user_p': user_p,
                    'msg': msg,
                    'msg_co': msg_co,
                    'role': role[0]
                }
                return render(request, 'requester.html', context)
        else:
            context = {
                'vlist': vlist,
                'user_p': user_p,
                'msg': msg,
                'msg_co': msg_co,
                'role': role[0]
            }
            return render(request, 'requester.html', context)
    else:
        return redirect('404')

@login_required(login_url='login')
def approve(request, pk):
    current_user = request.user.username
    vnum = Requests.objects.values_list('vnum', flat=True).get(rid=pk)
    req = Requests.objects.values_list('requesterid', flat=True).get(rid=pk)
    emial_group = Profile.objects.values_list('email', flat=True).filter(
        Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
    recipients = list(i for i in emial_group if bool(i))
    email = Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=req, status='active') \
        .values_list('email', flat=True)[0]
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == "Approver":
        Requests.objects.filter(rid=pk, status=1).update(status=2,
                                               ret=0, approverid=current_user)
        try:
            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', recipients
            text_content = 'This is an important message.'
            html_content = '<p>Coupon requested by <strong>' + str(
                req) + '</strong> was approved, go to the link below.' \
                       '<br>' \
                       f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                       '<br> ' \
                       '<p> Thank you 😊 </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', email
            text_content = 'This is an important message.'
            html_content = '<p>Your coupon requested has been approved by <strong>' + current_user + \
                           '</strong> go to the link below.' \
                           '<br>' \
                           f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                           '<br> ' \
                           '<p> Thank you 😊 </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()
            return redirect('inbox')
        except TimeoutError:
            messages.warning(request, "Unable to send email but request Approved!!")
            return redirect('inbox')
    elif role[0] == "Admin":
        Requests.objects.filter(rid=pk).update(status=2, ret=0, approverid=current_user)
        try:
            subject, from_email, to = 'Coupon requested for ' + str(vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', recipients
            text_content = 'This is an important message.'
            html_content = '<p>Coupon requested by <strong>' + str(req) + '</strong> was approved, go to the link below.' \
                                                                          '<br>' \
                                                                          f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                                                                          '<br> ' \
                                                                          '<p> Thank you 😊 </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            subject, from_email, to = 'Coupon requested for ' + str(
                vnum) + ' Approved by ' + current_user, 'service.gm@undp.org', email
            text_content = 'This is an important message.'
            html_content = '<p>Your coupon requested has been approved by <strong>' + current_user +\
                           '</strong> go to the link below.' \
                       '<br>' \
                       f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                       '<br> ' \
                       '<p> Thank you 😊 </p>'
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
    current_user = request.user.username
    vnum = Requests.objects.values_list('vnum', flat=True).get(rid=pk)
    req = Requests.objects.values_list('requesterid', flat=True).get(rid=pk)
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    email = Profile.objects.select_related('user').annotate(user1 = F('user_id__username')).filter(user1 = req, status='active')\
        .values_list('email', flat=True)[0]
    if role[0] == "Approver":
        Requests.objects.filter(rid=pk).update(status=1, ret=1, retid=current_user)

        subject, from_email, to = 'Coupon requested for ' + str(
            vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = f'<p>Dear {req}, </p>'\
                                              '&nbsp; &nbsp;'' &nbsp; &nbsp; Your coupon request was returned by <strong>' + current_user + \
                       '</strong> go to the link below.' \
                       '<br>' \
                       f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                       '<p> Thank you 😊 </p>'
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()

        return redirect('inbox')
    elif role[0] == "Issuer":
        Requests.objects.filter(rid=pk).update(status=1, ret=1, retid=current_user)

        subject, from_email, to = 'Coupon requested for ' + str(
            vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = f'<p>Dear {req}, </p>' \
                       '&nbsp; &nbsp;'' &nbsp; &nbsp; Your coupon request was returned by <strong>' + current_user + \
                       '</strong> go to the link below.' \
                       '<br>' \
                       f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                       '<p> Thank you 😊 </p>'
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()

        return redirect('inbox')
    elif role[0] == "Admin":
        Requests.objects.filter(rid=pk).update(status=1, ret=1, retid=current_user)

        subject, from_email, to = 'Coupon requested for ' + str(
            vnum) + ' Returned by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = f'<p>Dear {req}, </p>' \
                       '&nbsp; &nbsp;'' &nbsp; &nbsp; Your coupon request was returned by <strong>' + current_user + \
                       '</strong> go to the link below.' \
                       '<br>' \
                       f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                       '<p> Thank you 😊 </p>'
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
        user_p = Profile.objects.get(user=current_user_id)
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()
        t = Requests.objects.values_list('status', flat=True).filter(rid=pk)
        psign = Requests.objects.values_list('requesterid', flat=True).filter(rid=pk)
        sig = Transaction.objects.values_list('sign', flat=True).filter(tid=pk)
        markt = Transaction.objects.values_list('marketrate', flat=True).filter(tid=pk)
        fileup = Transaction.objects.values_list('uploadedFile', flat=True).filter(tid=pk)

        if request.method == 'POST' and len(request.FILES) != 0:
            receipt = Transaction.objects.get(tid=pk)
            try:
                if len(receipt.uploadedFile) > 0 :
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
            html_content = '<p> The market price for <strong>' + vnum +  'Coupon'\
                           '</strong> was added by <strong>' + current_user + '</strong> go to the link below.' \
                                                                                    '<br>' \
                                                                                    f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                                                                                    '<br> ' \
                                                                                    '<p> Thank you 😊 </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            return redirect('approvalflow', str(pk))

        elif request.method == 'POST' and t[0] == 3 and sig[0] == "0" and markt[0] != 0 and len(fileup[0]) > 2 and psign[0] == request.user.username:
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
                                                                                                                           f'<a href="http://127.0.0.1:8000/approvalflow/{pk}">Request Item</a></p>' \
                                                                                                                           '<br> ' \
                                                                                                                           '<p> Thank you 😊 </p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            EmailThreading(msg).start()

            return redirect('approvalflow', str(pk))


        #     fss.save(upload.name, upload)
        #     # Saving the information in the database
        #     # Transaction.objects.filter(tid=pk).update(uploadedFile=uploadedFile)


        elif Requests.objects.filter(Q(status=1) | Q(status=2), rid=pk):
            aflow = Requests.objects.get(rid=pk)
            comm = comment.objects.values_list('rid', flat=True).filter(rid=pk)[0]
            context = {
                    'aflow': aflow,
                    'comm': comm,
                    'msg': msg,
                    'msg_co': msg_co,
                    'user_p': user_p,
                    'psign': psign,
                    'role': role[0]
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
                    'msg': msg,
                    'msg_co': msg_co,
                    'comm': comm,
                    'user_p': user_p,
                    'role': role[0]
                }
                return render(request, 'approvalflow.html', context)
            else:
                lit = float(0.0)
                context = {
                    'aflow': aflow,
                    'rflow': rflow,
                    'lit': lit,
                    'comm': comm,
                    'msg': msg,
                    'msg_co': msg_co,
                    'user_p': user_p,
                    'role': role[0]
                }
                return render(request, 'approvalflow.html', context)

    except ObjectDoesNotExist:
        messages.warning(request, ' This is record does not exist! Please contact your system Administrator')
        return redirect('inbox')

    except MultipleObjectsReturned:
        messages.warning(request, ' This is a duplicate record! Please contact your system Administrator')
        return redirect('inbox')
    # except ValueError:
    #     messages.warning(request, ' This is record contain an input error! Please contact your system Administrator')
    #     return redirect('inbox')

    except IntegrityError:
        messages.warning(request, ' Please sign or enter the current fuel market rate, Contact the Issuer')
        return redirect('approvalflow', pk)
    except IndexError:
        try:
            current_user_id = request.user.id
            current_user = request.user.username
            role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
            user_p = Profile.objects.get(user=current_user_id)
            t = Requests.objects.values_list('status', flat=True).filter(rid=pk)
            psign = Requests.objects.values_list('requesterid', flat=True).filter(rid=pk)
            sig = Transaction.objects.values_list('sign', flat=True).filter(tid=pk)
            markt = Transaction.objects.values_list('marketrate', flat=True).filter(tid=pk)
            if role[0] == "Driver":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
                msg_co = msg.filter().count()
            elif role[0] == "Approver":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.filter(status=1).count()
            elif role[0] == "Issuer":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.filter(status=2).count()
            else:
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.count()

            if request.method == 'POST' and t[0] == 3 and sig[0] == "0" and markt[0] == 0 and role[0] != 'Driver':
                Transaction.objects.filter(tid=pk).update(marketrate=request.POST.get('marketrate'))
                return redirect('approvalflow', str(pk))

            elif request.method == 'POST' and t[0] == 3 and sig[0] == "0" and markt[0] != 0 and psign[0] == request.user.username:
                Transaction.objects.filter(tid=pk).update(sign=request.POST.get('sign'))
                return redirect('approvalflow', str(pk))

            elif Requests.objects.filter(Q(status=1) | Q(status=2), rid=pk):
                aflow = Requests.objects.get(rid=pk)
                # comm = comment.objects.values_list('rid', flat=True).filter(rid=pk)[0]
                context = {
                    'aflow': aflow,
                    # 'comm': comm,
                    'msg': msg,
                    'msg_co': msg_co,
                    'user_p': user_p,
                    'psign': psign,
                    'role': role[0]
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
                        'msg': msg,
                        'msg_co': msg_co,
                        'lit': lit,
                        'user_p': user_p,
                        'role': role[0]
                    }
                    return render(request, 'approvalflow.html', context)

                else:
                    lit = float(0.0)
                    context = {
                        'aflow': aflow,
                        'rflow': rflow,
                        'msg': msg,
                        'msg_co': msg_co,
                        'lit': lit,
                        'user_p': user_p,
                        'role': role[0]
                    }
                    return render(request, 'approvalflow.html', context)
        except ObjectDoesNotExist:
            return redirect('inbox')
        except MultipleObjectsReturned:
            messages.warning(request, ' This is a duplicate record! Please contact your system Administrator')
            return redirect('inbox')
        except ValueError:
            return redirect('inbox')

@login_required(login_url='login')
def requests(request):
    current_user = request.user.username
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)

    if role[0] == "Driver":
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()

        r = Requests.objects.filter(Q(status=1, ret=0) |
                                    Q(status=1, ret=1) | Q(status=2, ret=0) |
                                    Q(status=3, ret=0)).filter(requesterid=current_user).order_by('-created_at')
        context = {
            'requests': r,
            'msg': msg,
            'msg_co': msg_co,
            'user_p': user_p,
            'role': role[0]
        }
        return render(request, 'requests.html', context)
    else:
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()
        r = Requests.objects.filter(
            Q(status=1, ret=0) | Q(status=1, ret=1) | Q(status=2, ret=0) | Q(status=3, ret=0)).order_by('-created_at')
        context = {
            'requests': r,
            'user_p': user_p,
            'msg': msg,
            'msg_co': msg_co,
            'role': role[0]
        }
        return render(request, 'requests.html', context)

@login_required(login_url='login')
def perm(request):
    current_user = request.user.username
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    context = {
        'user_p': user_p,
        'msg': msg,
        'msg_co': msg_co,
        'role': role[0]
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
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if request.method == 'POST':
        rid = request.POST.get('rid')
        message = request.POST.get('message')
        comm = comment.objects.create(rid=rid, username=current_user, message=message)
        comm.save();
        messages.info(request, ' Successfully Submitted!')
        # cmm = Requests.objects.values_list('requesterid', flat=True).filter(rid=rid)[0]
        requestid = Requests.objects.values_list('requesterid', flat=True).filter(rid = rid)
        email = Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=requestid[0], status='active') \
            .values_list('email', flat=True)[0]
        email2 = Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=current_user, status='active') \
            .values_list('email', flat=True)[0]

        subject, from_email, to = ' Comment by ' + current_user, 'service.gm@undp.org', email
        text_content = 'This is an important message.'
        html_content = message + '<p> go to the link below.' \
                       '<br>' \
                       '<a href="http://127.0.0.1:8000/comments">Request Item</a></p>' \
                       '<br> ' \
                       '<p> Thank you 😊 </p>'
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        EmailThreading(msg).start()

        return redirect('comments')
    elif role[0] == "Driver":

        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()

        req = Requests.objects.values('rid').filter(Q(ret=0) | Q(ret=1),
                                                    Q(status=1) | Q(status=2),
                                                    requesterid=current_user)
        ir = comment.objects.values_list('username', flat=True).filter(rid__in=req)
        imgid = []
        for i in ir:
            uid = User.objects.values_list('id', flat=True).filter(username=i)[0]
            prof = Profile.objects.values('pic').filter(user=uid)
            img = comment.objects.filter(username=i, rid__in=req).annotate(pic=prof).values('id', 'rid', 'username',
                                                                                            'message', 'pic',
                                                                                            'created_at')[0]
            imgid.append(img)
        comm = imgid
        requests = Requests.objects.filter(Q(status=1, ret=0) | Q(status=1, ret=1) | Q(status=2, ret=0),
                                           requesterid=current_user)
        context = {
            'comm': comm,
            'msg': msg,
            'msg_co': msg_co,
            'user_p': user_p,
            'role': role[0],
            'requests': requests
        }
        return render(request, 'comment.html', context)
    else:
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()
        req = Requests.objects.values('rid').filter(Q(ret=0) | Q(ret=1),
                                                    Q(status=1) | Q(status=2))

        ir = comment.objects.values_list('username', flat=True).filter(rid__in=req)
        imgid=[]
        for i in ir:
            uid = User.objects.values_list('id', flat=True).filter(username=i)[0]
            prof = Profile.objects.values('pic').filter(user=uid)
            img = comment.objects.filter(username=i, rid__in=req).annotate(pic=prof).values('id','rid', 'username', 'message', 'pic', 'created_at')[0]
            imgid.append(img)


        requests = Requests.objects.filter(Q(status=1, ret=0) | Q(status=1, ret=1) | Q(status=2, ret=0))
        # comm = comment.objects.filter(rid__in=req).annotate(user=imgid).values('id', 'rid', 'username', 'message', 'created_at', 'user')
        comm = imgid



        context = {
            'comm': comm,
            'msg': msg,
            'msg_co': msg_co,
            'user_p': user_p,
            'role': role[0],
            'requests': requests
        }
        return render(request, 'comment.html', context)

@login_required(login_url='login')
def itemcomment(request, pk):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    imgid = []
    ir = comment.objects.values_list('username', flat=True).filter(rid=pk)
    for i in ir:
        uid = User.objects.values_list('id', flat=True).filter(username=i)[0]
        prof = Profile.objects.values('pic').filter(user=uid)
        img = comment.objects.filter(username=i, rid=pk).annotate(pic=prof).values('id', 'rid', 'username',
                                                                                        'message', 'pic',
                                                                                        'created_at')[0]
        imgid.append(img)
    comm = imgid
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    context = {
        'comm': comm,
        'msg': msg,
        'msg_co': msg_co,
        'user_p': user_p,
        'role': role[0]
    }
    return render(request, 'itemcomment.html', context)

@login_required(login_url='login')
def vehicles(request):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == 'Admin' or role[0] == 'Issuer':
        if request.method == 'POST':
            vnum = request.POST.get('vnum')
            ftype = request.POST.get('ftype')
            vtype = request.POST.get('vtype')
            imile = request.POST.get('imile')
            asunit = request.POST.get('asunit')
            driver = request.POST.get('driver')
            tankcap = request.POST.get('tankcap')
            veh = Vehicle.objects.create(vnum=vnum, ftype=ftype,
                                         vtype=vtype, imile=imile, asunit=asunit, driver_id=driver, tankcap=tankcap)
            veh.save();
            messages.success(request, 'Request Successfully Submitted!')
            return redirect('vehicles')

        else:
            vlist = Vehicle.objects.all()
            ulist = Unit.objects.all()
            plist = Profile.objects.filter(role='Driver')
            if role[0] == "Driver":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
                msg_co = msg.filter().count()
            elif role[0] == "Approver":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.filter(status=1).count()
            elif role[0] == "Issuer":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.filter(status=2).count()
            else:
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.count()
            context = {
                'vlist': vlist,
                'ulist': ulist,
                'msg': msg,
                'msg_co': msg_co,
                'plist': plist,
                'user_p': user_p,
                'role': role[0]
            }
            return render(request, 'vehicles.html', context)
    else:
        messages.warning(request, "You don't have permission on this page")
        return redirect('404')

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
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if role[0] == 'Admin' or role[0] == 'Issuer' or role[0] == 'Issuer':
        dellist = Coupons.objects.all()
        context = {
            'dellist': dellist,
            'msg': msg,
            'msg_co': msg_co,
            'user_p': user_p,
            'role': role[0]
        }
        return render(request, 'delstock.html', context)
    else:
        return redirect('404')

@login_required(login_url='login')
def delst(request, pk):
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == 'Admin' or role[0] == 'Issuer':
        Coupons.objects.filter(cid=pk).delete()
        return redirect('delstock')
    else:
        return redirect('404')

@login_required(login_url='login')
def unit(request):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == 'Admin':
        if request.method == 'POST':
            uname = request.POST.get('uname')
            uhead = request.POST.get('uhead')
            capprover = request.POST.get('capprover')
            un = Unit.objects.create(uname=uname, uhead=uhead, capprover=capprover, aptype=0)
            un.save();
            return redirect('unit')
        else:
            if role[0] == "Driver":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
                msg_co = msg.filter().count()
            elif role[0] == "Approver":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.filter(status=1).count()
            elif role[0] == "Issuer":
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.filter(status=2).count()
            else:
                msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                msg_co = msg.count()
            units = Unit.objects.all()
            context = {
                'units': units,
                'user_p': user_p,
                'msg': msg,
                'msg_co': msg_co,
                'role': role[0]
            }

            return render(request, 'unit.html', context)
    else:
        messages.warning(request, "You don't have permission on this page")
        return redirect('404')

@login_required(login_url='login')
def unitdel(request, pk):
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == 'Admin':
        Unit.objects.filter(uid=pk).delete()
        return redirect('unit')
    else:
        return redirect('404')

@login_required(login_url='login')
def profile(request):
    current_user_id = request.user.id
    current_user = request.user
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if role[0] == 'Admin':
        prof = Profile.objects.all()
        context = {
            'prof': prof,
            'msg': msg,
            'msg_co': msg_co,
            'user_p': user_p,
            'role': role[0]
        }
        return render(request, 'profile.html', context)
    else:
        return redirect('404')

@login_required(login_url='login')
def userGroup(request):
    current_user = request.user.username
    current_user_id = request.user.id
    user_p = Profile.objects.get(user=current_user_id)
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()

    if role[0]=="Admin":
        if request.method == "POST":
            groupname = request.POST.get('groupname')
            desc = request.POST.get('desc')
            group = UserGroup.objects.create(groupname=groupname, desc=desc)
            group.save();
            return redirect('userGroup')
        else:
            ug = UserGroup.objects.all()
            context ={
                'ug': ug,
                'msg': msg,
                'msg_co': msg_co,
                'user_p': user_p,
                'role': role[0]
            }

            return render(request, 'usergroup.html', context)
    else:
        return redirect('404')

@login_required(login_url='login')
def groupdel(request, pk):
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    if role[0] == 'Admin':
        UserGroup.objects.filter(id=pk).delete()
        return redirect('userGroup')
    else:
        return redirect('404')

# This function handles the transaction. It updates the coupon leaves, create transaction and update the request item
@login_required(login_url='login')
def transac(request, pk):
    current_user = request.user.username
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)

    try:
        if role[0] == "Issuer" or role[0] == "Admin":
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
                        comp = total - int(cnumber)+1
                    except IndexError:
                        messages.warning(request, "There is no stock for this unit to issue this amount of Coupon/s")
                        return redirect('transac', str(tid))

                # This needs to be resolve later because if there is no record in the data base shows zero even if there is stock.
                if comp <= 0:
                    messages.warning(request, "The stock is not enough to issue this amount of Coupon/s")
                    return redirect('transac', str(tid))

                else:
                    bupdate = fueldump.objects.filter(used=0, unit=unit, ftype=ftype, dim=cdimension,
                                                      trans_id=1).all().order_by('lnum')
                    e = int(cnumber)
                    bc = bupdate[:e]
                    c =bc.values_list('lnum', flat=True)
                    p = bc.values_list('book_id', flat=True)

                    if len(Transaction.objects.filter(tid=tid))==0:

                        tran = Transaction.objects.create(tid_id=tid, cdimension=cdimension, totalamount=totalamount,
                                                          ftype=ftype,
                                                          cnumber=cnumber, quantity=quantity, rate=rate, marketrate=0, sign=0,
                                                          unit=unit, uploadedFile="0", note=note, serialno=min(c), maxserialno=max(c))
                        tran.save();

                        Requests.objects.filter(rid=tid).update(status=3,
                                                                ret=0, issueid=str(current_user))

                        t = Coupons.objects.filter(unit=unit, cdimension=cdimension, ftype=ftype).annotate(id = Max('cid'))\
                            .values_list('cid', flat=True)  # Get only the last id of this category.

                        # This is the stock update
                        Coupons.objects.filter(
                            cid__in=t).update(transamount=F('transamount') + int(cnumber))

                        # This is handling the book update.
                        for i in sorted(c):
                            fueldump.objects.filter(lnum=i).update(used=1, transac= tid, issuer=str(current_user))


                        # Update rbal for the remaining leaves on the book.
                        for bu in p:
                            cbu = CouponBatch.objects.get(bookref=bu)
                            cbu.rbal += 1
                            cbu.save()



                       # calculate fuel consumption by vehicle
                        rq = Requests.objects.filter(rid=tid)
                        cmill = rq.values_list('mread', flat=True)[0] #Current Milleage
                        clitre = rq.values_list('amount', flat=True)[0] #Current Litre
                        lmill = activityReport.objects.filter(vnum=rq.values_list('vnum', flat=True)[0]).values_list(
                            'mread', flat=True).last() # The last millage of this vehicle

                        if lmill:
                            fconsumption = round((cmill-lmill)/clitre, 2)
                        else:
                            lastmill = Vehicle.objects.values_list('imile', flat=True)[0]
                            fconsumption = round((cmill - lastmill) / clitre, 2)

                        # This is handling the Report logs for the monthly and annual fuel usage report
                        fd_s = fueldump.objects.filter(lnum = min(c))
                        fd_e = fueldump.objects.filter(lnum = max(c))
                        if len(comment.objects.filter(rid=tid))>0:
                            comm = 1
                        else:
                            comm = 0

                        acreort = activityReport.objects.create(tid=tid, totalamount=totalamount, litre=quantity, vnum=rq.values_list('vnum', flat=True),
                                                               mread = rq.values_list('mread', flat=True),
                                                               unit = unit, requesterid = rq.values_list('requesterid', flat=True),
                                                               approverid = rq.values_list('approverid', flat=True),
                                                               issueid = rq.values_list('issueid', flat=True),
                                                               serial_start = min(c),
                                                               serial_end = max(c), ftype=ftype,
                                                                bookref_s =fd_s.values_list('book_id',flat=True) ,
                                                                bookref = fd_e.values_list('book_id',flat=True),
                                                                note=note, comm = comm ,cdimension=cdimension, fconsumption=fconsumption)
                        acreort.save();



                    emial_group = Profile.objects.values_list('email', flat=True).filter(
                        Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
                    recipients = list(i for i in emial_group if bool(i))
                    req = Requests.objects.values_list('requesterid', flat=True).get(rid=tid)
                    email = \
                    Profile.objects.select_related('user').annotate(user1=F('user_id__username')).filter(user1=req, status='active') \
                        .values_list('email', flat=True)[0]

                    try:
                        subject, from_email, to = 'Coupon requested Issued by ' + current_user, 'service.gm@undp.org', email
                        text_content = 'This is an important message.'
                        html_content = '<p>Your coupon request has been issued by <strong>' + current_user + \
                                       '</strong> go to the link below.' \
                                       '<br>' \
                                       f'<a href="http://127.0.0.1:8000/approvalflow/{tid}">Request Item</a></p>' \
                                       '<br> ' \
                                       '<p> Thank you 😊 </p>'
                        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
                        msg.attach_alternative(html_content, "text/html")
                        EmailThreading(msg).start()

                        subject, from_email, to = 'Coupon requested Issued by ' + current_user, 'service.gm@undp.org', recipients
                        text_content = 'This is an important message.'
                        html_content = '<p> Coupon requested by <strong>' + str(req) + \
                                       '</strong> has been issued by <strong>' + current_user + '</strong> go to the link below.' \
                                       '<br>' \
                                       f'<a href="http://127.0.0.1:8000/approvalflow/{tid}">Request Item</a></p>' \
                                       '<br> ' \
                                       '<p> Thank you 😊 </p>'
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
                if role[0] == "Driver":
                    msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
                    msg_co = msg.filter().count()
                elif role[0] == "Approver":
                    msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                    msg_co = msg.filter(status=1).count()
                elif role[0] == "Issuer":
                    msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                    msg_co = msg.filter(status=2).count()
                else:
                    msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
                    msg_co = msg.count()
                context = {
                    'issue': issue,
                    'msg': msg,
                    'msg_co': msg_co,
                    'ulist': ulist,
                    'user_p': user_p,
                    'role': role[0]
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
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if role[0] == "Admin":
        try:
            if request.method == 'POST' and len(request.FILES)>0:
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
                    values('email1', 'id', 'fname', 'lname', 'role', 'unit', 'status', 'user_id', 'user1', 'pic', 'email').get(
                    id=pk)

                rl = Profile.objects.values_list('role', flat=True).get(id=pk)
                pic =Profile.objects.get(id=pk)
                ug = UserGroup.objects.exclude(groupname=rl)
                tranam = activityReport.objects.filter(requesterid=pic).count()
                tranlast = activityReport.objects.filter(requesterid=pic).last()
                tranpen = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=pic, ret=0).count()
                trantotal = activityReport.objects.values_list('totalamount', flat=True).filter(requesterid=pic).aggregate(total = Sum('totalamount'))

                context = {
                    'prof': prof_us,
                    'ug': ug,
                    'trantotal': trantotal,
                    'tranam': tranam,
                    'tranlast': tranlast,
                    'tranpen': tranpen,
                    'msg': msg,
                    'msg_co': msg_co,
                    'pic': pic,
                    'user_p': user_p,
                    'role': role[0]
                }
                return render(request, 'user_profile.html', context)
        except IntegrityError:
            return redirect('user_profile', pk)

    elif role[0] != "Admin":
        try:
            if request.method == 'POST' and len(request.FILES)>0:
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
                    values('email1', 'id', 'fname', 'lname', 'role', 'unit', 'status', 'user_id', 'user1', 'pic', 'email').get(
                    user=current_user_id)

                rl = Profile.objects.values_list('role', flat=True).get(user=current_user_id)
                pic =Profile.objects.get(user=current_user_id)
                ug = UserGroup.objects.exclude(groupname=rl)
                tranam = Requests.objects.filter(requesterid=current_user, ret=0).count()
                tranlast = Requests.objects.filter(requesterid=current_user, ret=0).last()
                tranpen = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0).count()
                trantotal = activityReport.objects.values_list('totalamount', flat=True).filter(
                    requesterid=pic).aggregate(total=Sum('totalamount'))

                context = {
                    'prof': prof_us,
                    'ug': ug,
                    'trantotal': trantotal,
                    'tranam': tranam,
                    'tranlast': tranlast,
                    'tranpen': tranpen,
                    'msg': msg,
                    'msg_co': msg_co,
                    'pic': pic,
                    'user_p': user_p,
                    'role': role[0]
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
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    # user_p = Profile.objects.get(user=current_user_id)
    if role[0] != "Driver":
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
    current_user_id = request.user.id
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    u = User.objects.get(username__exact=current_user)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
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
                return render(request, 'passwordreset.html',{'role': role[0], 'user_p':user_p, 'msg': msg, 'msg_co': msg_co })
        else:
            messages.info(request, "Incorrect current password. Please try again!")
            return render(request, 'passwordreset.html', {'role': role[0], 'user_p':user_p, 'msg': msg, 'msg_co': msg_co})

    else:
        return render(request, 'passwordreset.html', {'role':role[0], 'user_p': user_p, 'msg':msg, 'msg_co': msg_co})

@login_required(login_url='login')
def getfile(request):
    response = HttpResponse(content_type='text/csv')
    now = time.strftime('%d-%m-%Y %H:%M:%S')
    response['Content-Disposition'] = 'attachment; filename="report"'+ now +'".csv"'
    stocks = Coupons.objects.all()
    writer = csv.writer(response)
    writer.writerow(['ID', 'Dimension', 'Fuel Type', 'Stock Amount',
                     'Total', 'Opening Stock', 'Amount of Transactions', 'Unit', 'Date created'])
    for stock in stocks:
        writer.writerow([stock.cid, stock.cdimension, stock.ftype, stock.camount,
                         stock.total, stock.stockopen, stock.transamount, stock.unit, stock.created_at])
    return response

@login_required(login_url='login')
def bookreport(request, pk):
    response = HttpResponse(content_type='text/csv')
    now = time.strftime('%d-%m-%Y %H:%M:%S')
    response['Content-Disposition'] = 'attachment; filename="report"'+ now +'".csv"'
    book = CouponBatch.objects.values_list('bookref').filter(id=pk, bdel=0)[0][0]
    bk = book
    leaves = fueldump.objects.all().annotate(vnum =Subquery(
        Requests.objects.filter(rid=OuterRef('transac')).values('vnum').order_by('vnum')[:1]),
    requester = Subquery(
        Requests.objects.filter(rid=OuterRef('transac')).values('requesterid')[:1]
    ),
        approver = Subquery(
        Requests.objects.filter(rid=OuterRef('transac')).values('approverid')[:1]
    )).filter(book_id= bk, used=1).order_by('lnum')

    # Store.objects.annotate(timezone=Subquery(
    #     StoreInformation.objects.filter(store_number=OuterRef('store_number')).values('store_timezone')[:1]
    # ))

    writer = csv.writer(response)
    writer.writerow(['Book', 'Leave No', 'Fuel Type', 'Used',
                     'Book serial', 'Allocated stock', 'Dimension', 'Requester', 'Approver', 'Issuer', 'Vehicle',  'Unit', 'Date modified'])
    for leave in leaves:
        writer.writerow([leave.book, leave.lnum, leave.ftype, leave.used,
                         leave.book_id, leave.trans_id, leave.dim, leave.requester, leave.approver, leave.issuer,  leave.vnum,  leave.unit, leave.datemodified])
    return response

@login_required(login_url='login')
def couponbooksreport(request):
    response = HttpResponse(content_type='text/csv')
    now = time.strftime('%d-%m-%Y %H:%M:%S')
    response['Content-Disposition'] = 'attachment; filename="report"' + now + '".csv"'
    books = CouponBatch.objects.all().annotate(quan = Count(Subquery(
        fueldump.objects.filter(book_id=OuterRef('bookref')).values('book_id').filter(used = 0)[:1])),
        fmin = Min(Subquery(
        fueldump.objects.filter(book_id=OuterRef('bookref')).values('lnum').filter(used = 0)[:1])),
    ).filter(bdel=0, hide=0)
    writer = csv.writer(response)
    writer.writerow(['Book','Start Serial', 'End Serial', 'Quantity','Fuel Type', 'Unit'])
    for book in books:
        if book.quan == 1:
            writer.writerow([book.book_id, book.fmin, book.serial_end,int(book.serial_end)+1-book.fmin, book.ftype, book.unit])
    return response

@login_required(login_url='login')
def fuelconsreport(request):
    response = HttpResponse(content_type='text/csv')
    now = time.strftime('%d-%m-%Y %H:%M:%S')
    response['Content-Disposition'] = 'attachment; filename="report"' + now + '".csv"'
    writer = csv.writer(response)
    result = Transaction.objects.select_related('tid').annotate(vehicle = F('tid__vnum')).order_by('vehicle')
    writer.writerow(['Vehicle', 'Fuel Type', 'Litres consume', 'Unit', 'Date created'])
    for res in result:
        writer.writerow([res.vehicle, res.ftype, res.quantity, res.unit, res.created_at])
    return response

@login_required(login_url='login')
def translog(request):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if role[0] =="Driver":
        return redirect('404')
    else:

        context = {
            'role': role[0],
            'msg': msg,
            'msg_co': msg_co,
            'user_p': user_p
        }
        return render(request, 'translog.html', context)

#------ This is to genrate a unique ID ------
import uuid
@login_required(login_url='login')
def couponBatch(request):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if role[0] =="Driver" or role[0] =="Approver":
        return redirect('404')
    else:
        if request.method == "POST":
            book_id = request.POST.get('book_id')
            serial_start = request.POST.get('serial_start')
            serial_end = request.POST.get('serial_end')
            dim = request.POST.get('dim')
            ftype = request.POST.get('ftype')
            unit = request.POST.get('unit')
            bookref = uuid.uuid4().hex[:6].upper()
            ex = CouponBatch.objects.filter(serial_start = serial_start, serial_end = serial_end, bdel=0)
            ux = CouponBatch.objects.filter(bookref=bookref)
            if ex:
                messages.info(request,f"This book exit! book - {serial_start}")
                return redirect('couponBatch')
            elif ux:
                messages.info(request,f"This book is not unique (Hash collision!) {bookref} ")
                return redirect('couponBatch')
            else:
                tx = int(serial_start) -1 # This is to create the exact number of coupon leaves
                tm = int(serial_end) - tx # This creates the number of leaves to be created.
                totalamount = tm * int(dim) # This is the amount in cash
                b = []
                d = int(serial_start)
                for i in range(tm):
                    b.append(i+d)

                # This is what creates the book
                book = CouponBatch.objects.create(book_id=book_id, serial_start=serial_start, serial_end=serial_end,
                                           dim=dim, ftype=ftype, unit=unit, totalAmount=totalamount, used=0, bdel=0,
                                                  hide=1, rbal=0, creator=current_user, bookref=bookref)

                book.save();

                # This is what create the leaves on the fuel dump table
                fueldump.objects.bulk_create([fueldump(lnum=e, book_id=bookref, book=book_id, unit=unit, ftype=ftype,
                                                       dim=dim, used=0, trans_id=0, transac=0) for e in b])
                return redirect("couponBatch")

        elif role[0] == "Owner" or role[0] == "Admin":
            # This is what is handling the book render.
            #quan=(F('totalAmount')/F('dim')) - F('rbal')
            # The function that increment rbal increment it x2 always so to see the correct output you need to divide it by 2
            books = CouponBatch.objects.annotate(quan=(F('totalAmount')/F('dim')) - (F('rbal')),
                                                 percent =  100 - (F('rbal')*100)/(F('totalAmount')/(F('dim')))).filter(bdel=0).\
                all()

            ulist = Unit.objects.all()
            context = {
                    'role': role[0],
                    'books': books,
                    'msg': msg,
                    'msg_co': msg_co,
                    'ulist': ulist,
                    'user_p': user_p
                }
            return render(request, 'couponbatch.html', context)

        elif role[0] == "Issuer":
            books = CouponBatch.objects.annotate(quan=(F('totalAmount') / F('dim')) - F('rbal'),
                                                 percent=100 - (F('rbal') * 100) / (
                                                             F('totalAmount') / F('dim'))).filter(used=1, bdel=0). \
                all()
            ulist = Unit.objects.all()
            context = {
                'role': role[0],
                'books': books,
                'msg': msg,
                'msg_co': msg_co,
                'ulist': ulist,
                'user_p': user_p
            }
            return render(request, 'couponbatch.html', context)
        else:
            redirect(perm)


@login_required(login_url='login')
def coupondetail(request, pk):
    try:
        current_user_id = request.user.id
        current_user = request.user.username
        role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
        user_p = Profile.objects.get(user=current_user_id)
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":

            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()
        if role[0] =="Driver" or role[0] =="Issuer" or role[0] =="Approver":
            return redirect('404')
        else:

            book = CouponBatch.objects.get(Q(bdel=0) |  Q(bdel = 2), id=pk)
            b = CouponBatch.objects.values_list('bookref', flat=True).filter(id=pk, bdel=0)[0]
            leaves = fueldump.objects.filter(book_id = b).order_by('lnum')
            used = fueldump.objects.filter(book_id = b, used=1).annotate(cn=Count('used')).values_list('cn', flat=True)
            notused = fueldump.objects.filter(book_id=b, used=0).annotate(cn=Count('used')).values_list('cn', flat=True)
            total = fueldump.objects.filter(book_id=b).annotate(cn=Count('used')).values_list('cn', flat=True)
            lastu = fueldump.objects.filter(book_id=b, used=1).annotate(lastmod = Subquery(
            Transaction.objects.filter(tid=OuterRef('transac')).values('created_at')[:1])).order_by('lastmod').last()

            context = {
                'role': role[0],
                'book': book,
                'used': used,
                'msg': msg,
                'msg_co': msg_co,
                'lastu': lastu,
                'notused': notused,
                'leaves': leaves,
                'total': total,
                'user_p': user_p
            }
            return render(request, 'coupondetail.html', context)
    except ObjectDoesNotExist:
        return redirect('couponBatch')

# This is to soft delete a book with it's leave
@login_required(login_url='login')
def deletebook(request, pk):
    b = CouponBatch.objects.filter(id=pk, used=0).values_list('bookref', flat=True)[0]
    lid = fueldump.objects.filter(book_id=b).values_list('lnum', flat=True)
    for i in lid:
        # fueldump.objects.filter(lnum = i, used=0, ldel=0).update(ldel= 1)
        fueldump.objects.filter(lnum = i, used=0).delete()
    CouponBatch.objects.filter(id=pk, used=0).update(bdel=1)
    return redirect('couponBatch')


@login_required(login_url='login')
def hidebook(request, pk):
    if CouponBatch.objects.filter(id=pk, used=0, hide=0):
        CouponBatch.objects.filter(id=pk).update(hide=1)
        return redirect('coupondetail', pk)
    else:
        CouponBatch.objects.filter(id=pk, used=0, hide=1).update(hide=0)
        return redirect('coupondetail', pk)

# This is for the search
@login_required(login_url='login')
def search(request):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if role[0] == "Driver":
        if request.method=='POST':
            sear = request.POST.get('sear')

        lst = Requests.objects.filter(Q(vnum__icontains=sear) | Q(requesterid__icontains=sear) |
                                      Q(created_at__icontains=sear), requesterid = request.user.username).order_by('-created_at')[:23]
        context = {
            'role':role,
            'lst':lst,
            'msg':msg,
            'msg_co':msg_co,
            'user_p':user_p

        }
        return render(request, 'search.html', context)
    else:
        if role[0] == "Driver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
            msg_co = msg.filter().count()
        elif role[0] == "Approver":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=1).count()
        elif role[0] == "Issuer":
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.filter(status=2).count()
        else:
            msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
            msg_co = msg.count()
        if request.method=='POST':
            sear = request.POST.get('sear')

        lst = Requests.objects.filter(Q(vnum__icontains=sear) | Q(requesterid__icontains=sear) |
                                      Q(created_at__icontains=sear)).order_by('-created_at')[:23]
        context = {
            'role':role,
            'msg':msg,
            'msg_co':msg_co,
            'lst':lst,
            'user_p':user_p

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
    today = datetime.datetime.now() # This is to generate the date today.
    template_name = "report.html" # This is the template to generate pdf

    # This is for the request
    logs = activityReport.objects.filter(created_at__year=today.year, created_at__month=today.month).order_by("ftype", "-created_at")

    # Report on transaction per request.
    damount = activityReport.objects.\
        filter(created_at__year=today.year, created_at__month=today.month).\
        values('ftype').annotate(asum = Sum('totalamount'), lt=Sum('litre'))

    usr = request.user.username

    # Report on book Balance
    books = CouponBatch.objects.all().annotate(quan=Count(Subquery(
        fueldump.objects.filter(book_id=OuterRef('bookref')).values('book_id').filter(used=0)[:1])),
        fmin=Min(Subquery(
            fueldump.objects.filter(book_id=OuterRef('bookref')).values('lnum').filter(used=0)[0:1])),
    ).filter(bdel=0, hide=0)

    # This is the monthly fuel consumption by vehicle report for PDF generator.
    vamount = activityReport.objects. \
        filter(created_at__year=today.year, created_at__month=today.month, ftype="Diesel"). \
        values('vnum').order_by('vnum').annotate(lt=Sum('litre'), asum=Sum('totalamount'), consum = Avg('fconsumption'))

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
            diesel += d+1
            dieselam += da
        elif i['quan'] == 1 and i['ftype'] == 'Petrol':
            p = int(i['serial_end']) - i['minlnum']
            pa = i['dim'] * (p + 1)
            petrol += p+1
            petrolam += pa

    return render_to_pdf(
        template_name,
        {
            "logs": logs,
            "usr": usr,
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
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.get(requesterid=uname)
        # if msg.status != 3:
        #     popmsg = msg

    context = {
            'popmsg': msg
    }
    return render(request,'nav.html', context)

@login_required(login_url='login')
def requestEdit(request, pk):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    if request.method == 'POST':
        rid = request.POST.get('rid')
        mread = request.POST.get('mread')
        vnum = request.POST.get('vnum')
        tankcat = request.POST.get('tankcat')
        comm = request.POST.get('comm')

        stats = Requests.objects.values_list('status', flat=True).filter(Q(vnum=vnum), Q(ret=1),  ~Q(rid=rid) | Q(ret=0), Q(vnum=vnum),  ~Q(rid=rid)
                                                                         ).last()
        mileage = Requests.objects.values_list('mread', flat=True).filter(Q(vnum=vnum), Q(ret=1), ~Q(rid=rid) | Q(ret=0),
                                                                          Q(vnum=vnum),  ~Q(rid=rid)
                                                                          ).last()
        inmileage = Vehicle.objects.values_list('imile', flat=True).filter(vnum=vnum)[0]
        if stats == 3 or stats == None:

            if stats == 3 and int(mileage) < int(mread) or \
                    stats == None and int(inmileage) < int(mread):

                if tankcat == 'empty':
                    tank = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    Requests.objects.filter(status=1, requesterid=current_user, ret=1, rid=rid).update(mread=mread,
                                                                                              tankcat=tankcat,
                                                                                              amount=float(tank),
                                                                                              comm=comm, ret=0)

                elif tankcat == 'quarter':
                    t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    tankmath = float(t) / 4
                    tank = t - tankmath
                    Requests.objects.filter(status=1, requesterid=current_user, ret=1, rid=rid).update(mread=mread,
                                                                                              tankcat=tankcat,
                                                                                              amount=tank,
                                                                                              comm=comm, ret=0)

                elif tankcat == 'half':
                    t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    tankmath = float(t) / 2
                    tank = t - tankmath
                    Requests.objects.filter(status=1, requesterid=current_user, ret=1, rid=rid).update(mread=mread,
                                                                                              tankcat=tankcat,
                                                                                              amount=tank,
                                                                                              comm=comm, ret=0)

                elif tankcat == '3quarter':
                    t = Vehicle.objects.values_list('tankcap', flat=True).filter(vnum=vnum)[0]
                    s = 3 / 4
                    tankmath = float(s) * float(t)
                    tank = t - tankmath
                    Requests.objects.filter(status=1, requesterid=current_user, ret=1, rid=rid).update(mread=mread,
                                                                                              tankcat=tankcat, amount=tank,
                                                                                              comm=comm, ret=0)

                emial_group = Profile.objects.values_list('email', flat=True).filter(
                            Q(role='Admin') | Q(role='Approver') | Q(role='Issuer'), status='active').distinct()
                recipients = list(i for i in emial_group if bool(i))
                subject, from_email, to = 'Request for Coupon was returned by ' + current_user, 'service.gm@undp.org', recipients
                text_content = 'This is an important message.'
                html_content = '<p>Coupon request for <strong>' + vnum + '</strong> go to the link below.' \
                                                                                         '<br>' \
                                                                                         f'<a href="http://127.0.0.1:8000/approvalflow/{rid}">Request Item</a></p>' \
                                                                                         '<br> ' \
                                                                                         '<p> Thank you 😊 </p>'
                msgs = EmailMultiAlternatives(subject, text_content, from_email, to)
                msgs.attach_alternative(html_content, "text/html")
                msgs.send(fail_silently=True)

        return redirect('approvalflow', rid)


    else:
        rq = Requests.objects.get(rid=pk)
        context = {
            'rq':rq,
            'role': role[0],
            'user_p': user_p,
            'msg': msg,
            'msg_co': msg_co

        }
        return render(request, 'requester_edit.html', context)

@login_required(login_url='login')
def activityreport(request):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()
    logs = activityReport.objects.all().order_by("-created_at")
    casham = activityReport.objects.aggregate(Sum('totalamount'))

    context = {
        'role': role[0],
        'logs': logs,
        'casham': casham,
        'user_p': user_p,
        'msg': msg,
        'msg_co': msg_co

    }
    return render(request, 'activityreport.html', context)

@login_required(login_url='login')
def vehicle_detail(request, pk):
    current_user_id = request.user.id
    current_user = request.user.username
    role = Profile.objects.values_list('role', flat=True).filter(user=current_user_id)
    user_p = Profile.objects.get(user=current_user_id)
    if role[0] == "Driver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), requesterid=current_user, ret=0)
        msg_co = msg.filter().count()
    elif role[0] == "Approver":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=1).count()
    elif role[0] == "Issuer":
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.filter(status=2).count()
    else:
        msg = Requests.objects.filter(Q(status=1) | Q(status=2), ret=0)
        msg_co = msg.count()


    context = {
            'role': role[0],
            'user_p': user_p,
            'msg': msg,
            'msg_co': msg_co

        }
    return render(request, 'vehicle_detail.html', context)