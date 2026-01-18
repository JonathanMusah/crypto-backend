from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FeatureBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=150)),
                ("subtitle", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField()),
                ("icon", models.CharField(default="Sparkles", max_length=80)),
                ("accent_color", models.CharField(default="#38bdf8", max_length=30)),
                ("emphasis", models.CharField(blank=True, max_length=120)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["order", "id"],
                "verbose_name": "Feature highlight",
                "verbose_name_plural": "Feature highlights",
            },
        ),
        migrations.CreateModel(
            name="PolicyPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slug", models.SlugField(unique=True)),
                ("title", models.CharField(max_length=150)),
                ("summary", models.TextField()),
                ("sections", models.JSONField(blank=True, default=list)),
                ("last_updated", models.DateField()),
                ("hero_badge", models.CharField(blank=True, max_length=80)),
            ],
            options={
                "ordering": ["slug"],
                "verbose_name": "Policy page",
                "verbose_name_plural": "Policy pages",
            },
        ),
        migrations.CreateModel(
            name="SecurityHighlight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=150)),
                ("description", models.TextField()),
                ("badge", models.CharField(blank=True, max_length=60)),
                ("icon", models.CharField(default="Shield", max_length=80)),
                ("status", models.CharField(blank=True, max_length=60)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["order", "id"],
                "verbose_name": "Security highlight",
                "verbose_name_plural": "Security highlights",
            },
        ),
        migrations.CreateModel(
            name="SupportedAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("symbol", models.CharField(max_length=20)),
                ("network", models.CharField(blank=True, max_length=80)),
                ("segment", models.CharField(blank=True, max_length=80)),
                ("liquidity_rank", models.PositiveIntegerField(default=0)),
                ("is_featured", models.BooleanField(default=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["order", "liquidity_rank", "symbol"],
                "verbose_name": "Supported asset",
                "verbose_name_plural": "Supported assets",
            },
        ),
        migrations.CreateModel(
            name="Testimonial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author_name", models.CharField(max_length=120)),
                ("role", models.CharField(blank=True, max_length=120)),
                ("company", models.CharField(blank=True, max_length=120)),
                ("quote", models.TextField()),
                ("avatar_url", models.URLField(blank=True)),
                ("rating", models.DecimalField(decimal_places=1, default=5.0, max_digits=2)),
                ("highlight", models.CharField(blank=True, max_length=120)),
                ("is_featured", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["order", "-rating", "author_name"],
                "verbose_name": "Customer testimonial",
                "verbose_name_plural": "Customer testimonials",
            },
        ),
        migrations.AddConstraint(
            model_name="supportedasset",
            constraint=models.UniqueConstraint(fields=("symbol", "network"), name="marketing_supportedasset_symbol_network_uniq"),
        ),
    ]

