# Generated migration for RAG app

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='RAGDocument',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Document title/name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Document description')),
                ('source', models.CharField(choices=[('admin', 'Admin Upload'), ('insight_attachment', 'Insight Attachment')], default='admin', help_text='Whether doc is from admin or user upload', max_length=50)),
                ('file', models.FileField(help_text='Uploaded document file', upload_to='rag_documents/%Y/%m/%d/')),
                ('file_type', models.CharField(choices=[('pdf', 'PDF'), ('docx', 'DOCX'), ('txt', 'Text')], help_text='File type/extension', max_length=10)),
                ('file_size_bytes', models.PositiveIntegerField(help_text='File size in bytes')),
                ('status', models.CharField(choices=[('pending', 'Pending Indexing'), ('indexing', 'Indexing in Progress'), ('indexed', 'Indexed'), ('failed', 'Indexing Failed')], default='pending', help_text='Indexing status', max_length=20)),
                ('chunk_count', models.PositiveIntegerField(default=0, help_text='Number of chunks created during indexing')),
                ('indexed_at', models.DateTimeField(blank=True, help_text='When the document was indexed', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if indexing failed')),
                ('category', models.CharField(blank=True, help_text='Document category (e.g., Salesforce, ServiceNow, General)', max_length=100)),
                ('tags', models.CharField(blank=True, help_text='Comma-separated tags for filtering', max_length=500)),
                ('created_by', models.CharField(blank=True, help_text='Username or email of uploader', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'RAG Document',
                'verbose_name_plural': 'RAG Documents',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RAGIndexingLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('operation', models.CharField(choices=[('index', 'Index'), ('reindex', 'Re-index'), ('delete', 'Delete')], max_length=50)),
                ('status', models.CharField(choices=[('success', 'Success'), ('failed', 'Failed')], max_length=20)),
                ('chunks_created', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('duration_seconds', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indexing_logs', to='rag.ragdocument')),
            ],
            options={
                'verbose_name': 'RAG Indexing Log',
                'verbose_name_plural': 'RAG Indexing Logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='ragdocument',
            index=models.Index(fields=['status', 'created_at'], name='rag_ragdocu_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='ragdocument',
            index=models.Index(fields=['source'], name='rag_ragdocu_source_idx'),
        ),
    ]
