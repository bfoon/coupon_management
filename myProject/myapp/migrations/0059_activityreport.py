# Generated by Django 3.2.5 on 2022-02-22 11:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0058_alter_transaction_uploadedfile'),
    ]

    operations = [
        migrations.CreateModel(
            name='activityReport',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('requesterid', models.CharField(max_length=100)),
                ('serial_start', models.CharField(max_length=100)),
                ('serial_end', models.CharField(max_length=100)),
                ('vnum', models.CharField(max_length=100)),
                ('mread', models.PositiveIntegerField(max_length=1000000)),
                ('totalamount', models.FloatField(blank=True)),
                ('unit', models.CharField(max_length=1000)),
            ],
        ),
    ]
