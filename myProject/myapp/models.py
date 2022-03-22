from django.db import models
import uuid
from django.contrib.auth.models import User
# Create your models here.
from datetime import datetime
# User table
from django.forms import UUIDField


class Profile(models.Model):
    # userid = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    fname = models.CharField(max_length= 100)
    lname = models.CharField(max_length=100)
    unit = models.CharField(max_length= 100)
    role = models.CharField(max_length= 100)
    email = models.EmailField(max_length=254)
    status = models.CharField(max_length=100, default='pending')
    # password = models.CharField(max_length= 100)
    # vnum = models.IntegerField(default=0)
    # last_login = models.CharField(max_length= 100)
    pic = models.FileField(upload_to='uploads/', default='uploads/default-avatar.png', null= True )
    created_at = models.DateTimeField(auto_now_add=True)
    datemodified = models.DateField(auto_now=True)
    def __str__(self):
        return f"{self.user.username}"

# Vehicle table
class Vehicle(models.Model):
    vid = models.BigAutoField(primary_key=True)
    vnum = models.CharField(max_length=100)
    vtype = models.CharField(max_length= 100)
    imile = models.PositiveIntegerField()
    asunit = models.CharField(max_length= 100)
    driver = models.ForeignKey(Profile, on_delete=models.CASCADE)
    ftype = models.CharField(max_length= 100)
    tankcap = models.FloatField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    datemodified = models.DateField(auto_now=True)

# Unit table
class Unit(models.Model):
    uid = models.BigAutoField(primary_key=True)
    uname = models.CharField(max_length= 100)
    uhead = models.CharField(max_length=100)
    capprover = models.CharField(max_length= 100)
    aptype = models.CharField(max_length= 100)
    created_at = models.DateTimeField(auto_now_add=True)
    datemodified = models.DateField(auto_now=True)


# User Groups
class UserGroup(models.Model):
    id = models.BigAutoField(primary_key=True)
    groupname = models.CharField(max_length=1000)
    desc = models.TextField(max_length=400)
    created_at = models.DateTimeField(auto_now_add=True)
    datemodified = models.DateField(auto_now=True)

# Coupons stock table
class Coupons(models.Model):
    cid = models.BigAutoField(primary_key=True)
    cdimension = models.PositiveIntegerField()
    ftype = models.CharField(max_length=100)
    camount = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    stockopen = models.PositiveIntegerField()
    transamount = models.PositiveIntegerField()
    unit = models.CharField(max_length= 100)
    book_id = models.CharField(max_length= 100)
    created_at = models.DateTimeField(auto_now_add=True)
    datemodified = models.DateField(auto_now=True)


    # For Requests
class Requests(models.Model):
    rid = models.BigAutoField(primary_key=True)
    vnum = models.CharField(max_length=100)
    ftype = models.CharField(max_length=100)
    requesterid = models.CharField(max_length=100)
    amount = models.PositiveIntegerField()
    comm = models.CharField(max_length= 1000)
    status = models.PositiveIntegerField()
    mread = models.PositiveIntegerField()
    ret = models.PositiveIntegerField()
    approverid = models.CharField(max_length=1000)
    issueid = models.CharField(max_length=1000)
    retid = models.CharField(max_length=1000)
    tankcat = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    datemodified = models.DateField(auto_now=True)

# Stock transaction table
class Transaction(models.Model):
    sid = models.BigAutoField(primary_key=True)
    tid = models.ForeignKey(Requests, on_delete=models.CASCADE)
    cdimension = models.FloatField(blank=True)  # coupon dimension
    ftype = models.CharField(max_length=100)  # The fuel type
    quantity = models.FloatField(blank=True)  # The quantity in litres
    cnumber = models.PositiveIntegerField()  # The number of coupons used
    rate = models.FloatField(blank=True)  # The Coupon rate per litre of fuel in dalasi
    marketrate = models.FloatField(blank=True)  # The Market rate per litre of fuel in dalasi
    totalamount = models.FloatField(blank=True)  # The total price of litres in dalasi
    unit = models.CharField(max_length=100)
    note = models.CharField(max_length=100)
    serialno = models .CharField(max_length=100) # Max serial number on the leave
    maxserialno = models.CharField(max_length=100) # Max serial number on the leave
    sign = models.CharField(max_length=100) # This is if the user signed the receipt or not 1 or 0
    uploadedFile = models.FileField(upload_to="Uploaded Files/", null=True, blank=True, default="0") # Upload receipts to the Request.
    created_at = models.DateTimeField(auto_now_add=True)
    datemodified = models.DateField(auto_now=True)

    # def save(self, *args, **kwargs):
    #     self.totalamount = self.cdimension * self.cnumber
    #     self.quantity = self.totalamount / self.rate
    #     return super(Transaction, self).save(*args, **kwargs)



# Logs for reporting on the startus of the books and more because the join statements don't work.
class TransactionLogs(models.Model):
    id = models.BigAutoField(primary_key= True)
    tnum = models.CharField(max_length=100)
    transdetail = models.CharField(max_length=1000) # this is flow status
    transamount = models.CharField(max_length=100)
    transtatus = models.CharField(max_length=100) # This is deleted or return status
    created_user = models.CharField(max_length=100) # This is the user who created the item
    actioned_user = models.CharField(max_length=100) # This is the user who acted on the item
    created_at = models.DateTimeField(auto_now_add=True)



class coupon(models.Model):
    cid = models.BigAutoField(primary_key=True)
    ftype = models.CharField(max_length=100)
    dim = models.PositiveIntegerField()
    serialno = models.CharField(max_length= 1000)
    datecreated = models.DateTimeField(auto_now_add=True)

    # Comment tables
class comment(models.Model):
    id = models.BigAutoField(primary_key=True)
    rid = models.PositiveIntegerField()
    username = models.CharField(max_length=100)
    message = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    # Individual coupon book record
class CouponBatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    book_id = models.PositiveIntegerField() # This is the book number
    serial_start = models.CharField(max_length=100) # This is the first serial number on the first page
    serial_end = models.CharField(max_length=100) # This is the last serial number on the last page
    used = models.PositiveIntegerField() # Status of coupon if used is 1 not used is 0
    dim = models.PositiveIntegerField() # This is the dimension of the coupon
    ftype = models.CharField(max_length=1000)  # This is the fuel
    unit = models.CharField(max_length=1000) # This is for different units
    totalAmount = models.PositiveIntegerField() # This is the amount in cash
    creator = models.CharField(max_length=1000) # This is the user who created the book
    bookref = models.CharField(max_length=1000) # This is the id for reference on fuel dump
    bdel = models.CharField(max_length=1000) # This is for soft deleting the book 1 is delete 0 is not delete
    hide = models.CharField(max_length=1000) # This is for hiding or showing the book from the stock
    rbal = models.PositiveIntegerField() # This is for the remaining balance
    status = models.PositiveIntegerField() # This is if the book is empty 1 not empty 0
    created_at = models.DateTimeField(auto_now_add=True) # This is the date it was created
    datemodified = models.DateField(auto_now=True)
    def __str__(self):
        return f"{self.serial_start} - {self.serial_end}"

class fueldump(models.Model):
    id = models.BigAutoField(primary_key=True)
    lnum= models.PositiveIntegerField()  # This is the leave number
    ftype = models.CharField(max_length=100)  # This is the ftype
    dim = models.PositiveIntegerField() # This is dimension of coupon
    used = models.PositiveIntegerField()  # Status of coupon leave if used is 1 not used is 0
    book_id = models.CharField(max_length=1000)  # This is the book id this id is from bookref
    trans_id = models.PositiveIntegerField()  # This is handling the stock issued problem not transactions.
    unit = models.CharField(max_length=100)  # This is the unit
    book = models.CharField(max_length=100)  # This is book
    transac = models.PositiveIntegerField()  # This is what will handle the transaction record for this transaction.
    issuer = models.CharField(max_length=100)  # This is the issuer of this leave
    # ldel = models.CharField(max_length=100)  # This is soft deleting of this leave
    created_at = models.DateTimeField(auto_now_add=True)  # This is the date it was created
    datemodified = models.DateField(auto_now=True) # This is the modified date

    # class Meta:
    #     abstract = True
    def __str__(self):
        return f"{self.lnum} - {self.book_id}"

class activityReport(models.Model):
    id = models.BigAutoField(primary_key=True)
    requesterid = models.CharField(max_length=100)
    tid = models.CharField(max_length=100)
    serial_start = models.CharField(max_length=100)  # This is the first serial number on the first page
    serial_end = models.CharField(max_length=100)  # This is the last serial number on the last page
    vnum = models.CharField(max_length=100)
    litre = models.FloatField(blank=True)
    mread = models.PositiveIntegerField()
    totalamount = models.FloatField(blank=True)  # The total price of litres in dalasi
    unit = models.CharField(max_length=1000)  # This is for different units
    approverid = models.CharField(max_length=1000)
    issueid = models.CharField(max_length=1000)
    ftype = models.CharField(max_length=100)  # This is the ftype
    retid = models.CharField(max_length=1000)
    note = models.CharField(max_length=100)
    comm = models.CharField(max_length=100) # This is to see whether there is comment or not. Yes / No
    bookref = models.CharField(max_length=1000)  # This is the id for reference on fuel dump for the Last serial end
    bookref_s = models.CharField(max_length=1000)  # This is the id for reference on fuel dump for the Start serial end
    cdimension = models.FloatField(blank=True)  # coupon dimension
    fconsumption = models.FloatField(blank=True)  # This is a fuel consumption per transaction.
    sign = models.CharField(max_length=100)  # This is if the user signed the receipt or not 1 or 0
    created_at = models.DateTimeField(auto_now_add=True)  # This is the date it was created
    datemodified = models.DateField(auto_now=True)
    def __str__(self):
        return f"{self.vnum}"

    def save(self, *args, **kwargs):
        if self.sign and self.datemodified is None:
            self.datemodified = datetime.now()
        elif not self.sign and self.datemodified is not None:
            self.datemodified = None
        super(activityReport, self).save(*args, **kwargs)



