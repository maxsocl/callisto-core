# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-07 19:06
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wizard_builder', '0018_choice_extra_info_text'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChoiceOption',
            fields=[
                ('id',
                 models.AutoField(
                     auto_created=True,
                     primary_key=True,
                     serialize=False,
                     verbose_name='ID')),
                ('text',
                 models.TextField()),
                ('question',
                 models.ForeignKey(
                     on_delete=django.db.models.deletion.CASCADE,
                     to='wizard_builder.Choice')),
            ],
        ),
    ]
