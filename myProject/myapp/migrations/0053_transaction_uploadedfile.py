# Generated by Django 3.2.5 on 2022-02-17 19:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0052_transaction_sign'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='uploadedFile',
            field=models.FileField(default=0, upload_to='Uploaded Files/'),
            preserve_default=False,
        ),
    ]
