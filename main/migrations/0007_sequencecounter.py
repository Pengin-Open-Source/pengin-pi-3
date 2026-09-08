from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_alter_slughistory_snapshot_changed_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='SequenceCounter',
            fields=[
                ('name', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('last_value', models.PositiveIntegerField(default=0)),
            ],
        ),
    ]
