# Generated by Django 3.2.5 on 2022-03-27 01:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0070_couponbatch_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='settings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Country', models.CharField(max_length=100)),
                ('city', models.CharField(max_length=100)),
                ('company', models.CharField(max_length=100)),
                ('currency', models.CharField(max_length=100)),
                ('address', models.CharField(max_length=100)),
                ('phone', models.CharField(max_length=100)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='')),
            ],
        ),
    ]
