from django.urls import path
from . import views
from .dash_plotly import dashboard

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('stock', views.stock, name='stock'),
    path('creditStock/<str:pk>', views.creditStock, name='creditStock'),
    path('requestlist', views.requestlist, name='requestlist'),
    path('inbox', views.inbox, name='inbox'),
    path('delete/<str:pk>', views.delete, name='delete'),
    path('requester', views.requester, name='requester'),
    path('register', views.register, name='register'),
    path('approve/<str:pk>', views.approve, name='approve'),
    path('ret/<str:pk>', views.ret, name='ret'),
    path('approvalflow/<int:pk>', views.approvalflow, name='approvalflow'),
    path('login', views.login, name='login'),
    path('requests', views.requests, name='requests'),
    path('nav', views.nav, name='nav'),
    path('perm', views.perm, name='404'),
    path('login404', views.login404, name='404login'),
    path('comments', views.comments, name='comments'),
    path('itemcomment/<str:pk>', views.itemcomment, name='itemcomment'),
    path('vehicles', views.vehicles, name='vehicles'),
    path('vehedit/<str:pk>', views.vehedit, name='vehedit'),
    path('vehdel/<str:pk>', views.vehdel, name='vehdel'),
    path('delstock', views.delstock, name='delstock'),
    path('delst/<str:pk>', views.delst, name='delst'),
    path('unit', views.unit, name='unit'),
    path('unitedit/<str:pk>', views.unitedit, name='unitedit'),
    path('unitdel/<str:pk>', views.unitdel, name='unitdel'),
    path('groupdel/<str:pk>', views.groupdel, name='groupdel'),
    path('groupedit/<str:pk>', views.groupedit, name='groupedit'),
    path('invoice/<str:pk>', views.invoice, name='invoice'),
    path('profile', views.profile, name='profile'),
    path('passwordreset/<str:pk>', views.passwordreset, name='passwordreset'),
    path('user_profile/<str:pk>', views.user_profile, name='user_profile'),
    path('user_pic/<str:pk>', views.user_pic, name='user_pic'),
    path('transac/<str:pk>', views.transac, name='transac'),
    path('translog', views.translog, name='translog'),
    path('getfile', views.getfile, name='getfile'),
    path('bookreport/<str:pk>', views.bookreport, name='bookreport'),
    path('hidebook/<str:pk>', views.hidebook, name='hidebook'),
    path('couponBatch', views.couponBatch, name='couponBatch'),
    path('userGroup', views.userGroup, name='userGroup'),
    path('search', views.search, name='search'),
    path('approvalflow/search', views.search, name='search'),
    path('coupondetail/search', views.search, name='search'),
    path('coupondetail/<str:pk>', views.coupondetail, name='coupondetail'),
    path('bookreport/<str:pk>', views.bookreport, name='bookreport'),
    path('deletebook/<str:pk>', views.deletebook, name='deletebook'),
    path('couponbooksreport', views.couponbooksreport, name='couponbooksreport'),
    path('reportpdf', views.reportpdf, name='reportpdf'),
    path('activityreport', views.activityreport, name='activityreport'),
    path('activityDetail/<str:pk>', views.activityDetail, name='activityDetail'),
    path('signed', views.signed, name='signed'),
    path('msgtop', views.msgtop, name='msgtop'),
    path('email_stock/<str:pk>', views.email_stock, name='email_stock'),
    path('setupconfig', views.setupconfig, name='setupconfig'),
    path('vehicle_detail/<str:pk>', views.vehicle_detail, name='vehicle_detail'),
    path('requestEdit/<str:pk>', views.requestEdit, name='requestEdit'),
    path('fuelconsreport', views.fuelconsreport, name='fuelconsreport'),
    path('logout', views.logout, name='logout')



]
