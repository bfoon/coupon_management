# Generated by Django 3.2.5 on 2021-10-25 14:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0050_alter_couponbatch_book_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fueldump',
            name='ldel',
        ),
    ]
