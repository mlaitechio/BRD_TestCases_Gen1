# Generated migration for RAG system fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_alter_projectasset_connector_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentoutput',
            name='is_indexed',
            field=models.BooleanField(default=False, help_text='Whether this output has been indexed to the RAG knowledge base'),
        ),
        migrations.AddField(
            model_name='agentoutput',
            name='rag_chunk_count',
            field=models.IntegerField(blank=True, default=0, help_text='Number of chunks stored in ChromaDB for this output', null=True),
        ),
        migrations.AddField(
            model_name='agentoutput',
            name='rag_indexed_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp when this output was indexed to RAG', null=True),
        ),
    ]
