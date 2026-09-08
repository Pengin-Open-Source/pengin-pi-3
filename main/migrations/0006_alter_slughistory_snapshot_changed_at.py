from django.db import migrations, models

import util.utils


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_robotsrule_slug_updated_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slughistory',
            name='snapshot',
            field=models.JSONField(blank=True, default=dict, encoder=util.utils.UUIDEncoder, null=True),
        ),
        migrations.AlterField(
            model_name='slughistory',
            name='changed_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
