# Generated by Django 3.2.5 on 2021-10-03 22:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0042_auto_20211003_2238'),
    ]

    operations = [
        migrations.AddField(
            model_name='fueldump',
            name='book',
            field=models.CharField(default=1, max_length=100),
            preserve_default=False,
        ),
    ]
