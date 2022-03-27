from django.contrib import admin
from .models import Profile
from .models import Vehicle
from .models import Unit
from .models import Coupons
from .models import Requests
from .models import comment
from .models import Transaction
from .models import TransactionLogs
from .models import CouponBatch
from .models import fueldump
from .models import UserGroup
from .models import activityReport
from .models import settings
# Register your models here.
admin.site.register(Profile)
admin.site.register(Vehicle)
admin.site.register(Unit)
admin.site.register(Coupons)
admin.site.register(Requests)
admin.site.register(comment)
admin.site.register(Transaction)
admin.site.register(TransactionLogs)
admin.site.register(CouponBatch)
admin.site.register(fueldump)
admin.site.register(UserGroup)
admin.site.register(activityReport)
admin.site.register(settings)

