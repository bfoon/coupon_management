# Generated by Django 3.2.5 on 2021-10-23 17:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0048_alter_fueldump_datemodified'),
    ]

    operations = [
        migrations.AddField(
            model_name='couponbatch',
            name='hide',
            field=models.CharField(default=0, max_length=1000),
            preserve_default=False,
        ),
    ]
