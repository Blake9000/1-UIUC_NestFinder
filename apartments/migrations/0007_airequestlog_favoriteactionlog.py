from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("apartments", "0006_apartment_latitude_apartment_longitude"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIRequestLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("mode", models.CharField(blank=True, max_length=20)),
                ("model_name", models.CharField(blank=True, max_length=120)),
                ("request_text", models.TextField()),
                ("normalized_request", models.TextField(blank=True)),
                ("response_text", models.TextField(blank=True)),
                ("normalized_response", models.TextField(blank=True)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("success", models.BooleanField(default=True)),
                ("error_message", models.TextField(blank=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_request_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FavoriteActionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "action",
                    models.CharField(
                        choices=[("push", "Push"), ("unpush", "Unpush")],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                (
                    "apartment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="favorite_action_logs",
                        to="apartments.apartment",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="favorite_action_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
