# Generated by Django 3.2.5 on 2021-08-08 16:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0005_transaction_note'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='cdimension',
            field=models.FloatField(blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='quantity',
            field=models.FloatField(blank=True),
        ),
    ]
