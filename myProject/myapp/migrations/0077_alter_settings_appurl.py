# Generated by Django 3.2.5 on 2022-04-10 01:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0076_settings_appurl'),
    ]

    operations = [
        migrations.AlterField(
            model_name='settings',
            name='appurl',
            field=models.ImageField(blank=True, default='http://127.0.0.1:8000/', null=True, upload_to=''),
        ),
    ]
