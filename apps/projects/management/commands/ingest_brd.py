import os
import glob
import tiktoken
from django.core.management.base import BaseCommand
from utils.search import kb_instance
from utils.file_extractor import extract_text_from_file
from agents.relevance_agent import evaluate_document_relevance

class Command(BaseCommand):
    help = 'Ingests existing BRDs from a directory or file into the Global Knowledge Base'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='Path to a file or directory containing BRDs')

    def handle(self, *args, **options):
        path = options['path']
        if not os.path.exists(path):
            self.stdout.write(self.style.ERROR(f"Path does not exist: {path}"))
            return

        files_to_process = []
        if os.path.isfile(path):
            files_to_process.append(path)
        else:
            for ext in ('*.pdf', '*.docx', '*.doc', '*.txt', '*.xlsx', '*.xls'):
                files_to_process.extend(glob.glob(os.path.join(path, '**', ext), recursive=True))

        if not files_to_process:
            self.stdout.write(self.style.WARNING(f"No supported files found in {path}"))
            return

        encoder = tiktoken.get_encoding("cl100k_base")
        chunk_size = 500

        for file_path in files_to_process:
            self.stdout.write(f"Processing {file_path}...")
            text = extract_text_from_file(file_path)
            if not text:
                self.stdout.write(self.style.WARNING(f"Failed to extract text from {file_path}"))
                continue

            self.stdout.write("Evaluating document relevance via AI...")
            sample_text = text[:4000]
            try:
                relevance_result = evaluate_document_relevance(sample_text)
                if not relevance_result.get("is_relevant", False):
                    reason = relevance_result.get("reason", "Unknown reason.")
                    self.stdout.write(self.style.WARNING(f"Skipping {os.path.basename(file_path)}: AI determined irrelevant. Reason: {reason}"))
                    continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to evaluate relevance for {file_path}: {e}"))
                continue

            paragraphs = text.split('\n\n')
            chunks = []
            current_chunk = []
            current_tokens = 0

            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                encoded_p = encoder.encode(p)
                tokens = len(encoded_p)
                
                if tokens > chunk_size:
                    if current_chunk:
                        chunks.append("\n\n".join(current_chunk))
                        current_chunk = []
                        current_tokens = 0
                        
                    # Split the massive paragraph into exactly chunk_size pieces
                    for i in range(0, tokens, chunk_size):
                        sub_text = encoder.decode(encoded_p[i:i+chunk_size])
                        chunks.append(sub_text)
                else:
                    if current_tokens + tokens > chunk_size and current_chunk:
                        chunks.append("\n\n".join(current_chunk))
                        current_chunk = [p]
                        current_tokens = tokens
                    else:
                        current_chunk.append(p)
                        current_tokens += tokens
            
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))

            filename = os.path.basename(file_path)
            chunk_dicts = []
            for i, chunk_text in enumerate(chunks):
                chunk_dicts.append({
                    'id': f"{filename}_chunk_{i}",
                    'text': chunk_text,
                    'metadata': {
                        'source': filename,
                        'section': 'General'
                    }
                })

            kb_instance.add_document_chunks(filename, chunk_dicts)
            self.stdout.write(self.style.SUCCESS(f"Ingested {len(chunks)} chunks for {filename}"))
