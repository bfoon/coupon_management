# Generated by Django 3.2.5 on 2022-03-22 19:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0069_couponbatch_rbal'),
    ]

    operations = [
        migrations.AddField(
            model_name='couponbatch',
            name='status',
            field=models.PositiveIntegerField(default=0),
            preserve_default=False,
        ),
    ]