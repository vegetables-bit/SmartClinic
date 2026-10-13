from django.db import migrations


def add_gender_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = [
            row[1]
            for row in cursor.execute("PRAGMA table_info('clinic_patient')").fetchall()
        ]
        if "gender" in columns:
            return
        cursor.execute(
            "ALTER TABLE clinic_patient ADD COLUMN gender varchar(20) NOT NULL DEFAULT 'prefer_not_to_say'"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("clinic", "0002_patient_clinic_patient_name_nonempty_and_more"),
    ]

    operations = [
        migrations.RunPython(add_gender_if_missing, migrations.RunPython.noop),
    ]
