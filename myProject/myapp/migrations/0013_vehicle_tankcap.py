# Generated by Django 3.2.5 on 2021-08-11 16:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0012_vehicle_driver'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='tankcap',
            field=models.FloatField(blank=True, default=0),
            preserve_default=False,
        ),
    ]
