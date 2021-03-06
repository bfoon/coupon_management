# Generated by Django 3.2.5 on 2021-09-20 16:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0025_auto_20210901_1053'),
    ]

    operations = [
        migrations.CreateModel(
            name='CouponBatch',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('book_id', models.CharField(max_length=1000)),
                ('serial_start', models.PositiveIntegerField()),
                ('serial_end', models.PositiveIntegerField()),
                ('used', models.PositiveIntegerField()),
                ('dim', models.PositiveIntegerField()),
                ('totalAmount', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('datemodified', models.DateField(auto_now=True)),
            ],
        ),
    ]
