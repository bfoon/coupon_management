# Generated by Django 3.2.5 on 2021-10-17 02:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0045_usergroup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fueldump',
            name='datemodified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
