"""
RAG Serializers - API request/response handlers
"""

from rest_framework import serializers
from .models import RAGDocument, RAGIndexingLog


class RAGDocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing documents"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = RAGDocument
        fields = [
            'id', 'title', 'source', 'source_display', 'status', 'status_display',
            'file_type', 'file_size_bytes', 'chunk_count', 'category', 'tags',
            'created_at', 'indexed_at'
        ]


class RAGDocumentDetailSerializer(serializers.ModelSerializer):
    """Full serializer with all fields"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = RAGDocument
        fields = [
            'id', 'title', 'description', 'source', 'source_display',
            'file', 'file_url', 'file_type', 'file_size_bytes',
            'status', 'status_display', 'chunk_count', 'indexed_at',
            'error_message', 'category', 'tags', 'created_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'file_url', 'chunk_count', 'indexed_at', 'error_message',
            'created_at', 'updated_at'
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None


class RAGDocumentUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading new documents"""

    class Meta:
        model = RAGDocument
        fields = ['title', 'description', 'file', 'category', 'tags', 'created_by']

    def validate_file(self, value):
        """Validate uploaded file"""
        max_size = 100 * 1024 * 1024  # 100MB
        if value.size > max_size:
            raise serializers.ValidationError('File size exceeds 100MB limit')

        # Check file type
        allowed_extensions = ['.pdf', '.docx', '.txt', '.xlsx', '.xls', '.csv']
        file_name = value.name.lower()
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError(
                f'Only PDF, DOCX, TXT, XLSX, XLS, and CSV files allowed. Got: {value.name}'
            )

        return value

    def create(self, validated_data):
        """Create document with metadata"""
        file_obj = validated_data['file']

        # Extract file type from extension
        file_name = file_obj.name.lower()
        if file_name.endswith('.pdf'):
            file_type = 'pdf'
        elif file_name.endswith('.docx'):
            file_type = 'docx'
        else:
            file_type = 'txt'

        # Set defaults
        validated_data['file_type'] = file_type
        validated_data['file_size_bytes'] = file_obj.size
        validated_data['source'] = 'admin'  # Default source for API uploads
        validated_data['status'] = 'pending'

        return super().create(validated_data)


class RAGIndexingLogSerializer(serializers.ModelSerializer):
    """Serializer for indexing audit logs"""

    operation_display = serializers.CharField(source='get_operation_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = RAGIndexingLog
        fields = [
            'id', 'document', 'operation', 'operation_display', 'status', 'status_display',
            'chunks_created', 'error_message', 'duration_seconds', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class RAGSearchResultSerializer(serializers.Serializer):
    """Serializer for RAG search results"""

    document_id = serializers.CharField()
    title = serializers.CharField()
    content = serializers.CharField()
    similarity_score = serializers.FloatField()
    category = serializers.CharField()
    section = serializers.CharField(required=False)
    source = serializers.CharField()
