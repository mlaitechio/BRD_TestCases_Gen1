# Generated migration for AI Chat models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatConversation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(blank=True, help_text='Conversation title (auto-generated or user-set)', max_length=255)),
                ('is_active', models.BooleanField(default=True, help_text='Whether conversation is archived or active')),
                ('model_used', models.CharField(default='gpt-4', help_text='OpenAI model used (gpt-4, gpt-3.5-turbo, etc)', max_length=100)),
                ('total_tokens_used', models.PositiveIntegerField(default=0, help_text='Total tokens used in this conversation')),
                ('message_count', models.PositiveIntegerField(default=0, help_text='Number of messages in conversation')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_message_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_conversations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-last_message_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('user', 'User'), ('assistant', 'Assistant'), ('system', 'System')], help_text='Who sent the message', max_length=20)),
                ('content', models.TextField(help_text='Message content/text')),
                ('tokens_used', models.PositiveIntegerField(default=0, help_text='Tokens used for this message')),
                ('file', models.FileField(blank=True, help_text='Optional file attachment', null=True, upload_to='ai_chat/attachments/%Y/%m/%d/')),
                ('file_type', models.CharField(blank=True, help_text='File type: pdf, txt, code, image, etc', max_length=20)),
                ('file_size_bytes', models.PositiveIntegerField(blank=True, null=True)),
                ('is_streaming_complete', models.BooleanField(default=True, help_text='Whether streaming response completed')),
                ('error_message', models.TextField(blank=True, help_text='Error message if request failed')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='ai_chat.chatconversation')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='ChatSessionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('message_sent', 'Message Sent'), ('response_received', 'Response Received'), ('streaming_started', 'Streaming Started'), ('streaming_ended', 'Streaming Ended'), ('file_uploaded', 'File Uploaded'), ('error_occurred', 'Error Occurred')], max_length=50)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('error_message', models.TextField(blank=True)),
                ('response_time_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('tokens_used', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_logs', to='ai_chat.chatconversation')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_session_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['conversation', 'created_at'], name='ai_chat_cha_conver_idx'),
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['role'], name='ai_chat_cha_role_idx'),
        ),
        migrations.AddIndex(
            model_name='chatsessionlog',
            index=models.Index(fields=['user', '-created_at'], name='ai_chat_log_user_idx'),
        ),
        migrations.AddIndex(
            model_name='chatsessionlog',
            index=models.Index(fields=['event_type'], name='ai_chat_log_event_idx'),
        ),
        migrations.AddIndex(
            model_name='chatconversation',
            index=models.Index(fields=['user', '-created_at'], name='ai_chat_conv_user_idx'),
        ),
        migrations.AddIndex(
            model_name='chatconversation',
            index=models.Index(fields=['is_active'], name='ai_chat_cha_is_act_idx'),
        ),
    ]
