# Generated by Django 5.1.1 on 2024-09-23 16:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('impairment', '0003_project_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
