# Generated migration for UserProfile model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('admin', 'Admin'), ('user', 'User')],
                    default='user',
                    help_text='User role: Admin has full access, User has limited access',
                    max_length=20
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Whether this user account is active'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'User Profile',
                'verbose_name_plural': 'User Profiles',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='userprofile',
            index=models.Index(fields=['role'], name='auth_userpr_role_idx'),
        ),
        migrations.AddIndex(
            model_name='userprofile',
            index=models.Index(fields=['is_active'], name='auth_userpr_is_act_idx'),
        ),
    ]
