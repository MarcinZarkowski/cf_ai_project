import os
import boto3
import json
from dotenv import load_dotenv

load_dotenv()

AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_ACCESS_KEY = os.environ["AWS_ACCESS_KEY"]
region = "us-east-2"

bedrock = boto3.client(
    'bedrock-runtime',
    region_name=region,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def get_embedding(text: str) -> list[float]:
    """Fetches a 256-dimensional embedding from Amazon Bedrock's Titan Text Embeddings V2 model."""

    payload = {
        "inputText": text,
        "dimensions": 256,  
        "embeddingTypes": ["float"]  
    }

    try:
        # Invoke the model
        response = bedrock.invoke_model(
            body=json.dumps(payload),
            contentType='application/json',
            modelId='amazon.titan-embed-text-v2:0'
        )
        
        result = json.loads(response['body'].read())
        embedding = result.get('embedding', None)
        print("EMBEDDING:", embedding)
        if embedding is None:
            raise ValueError("Embedding not found in the response.")

        return embedding

    except Exception as e:
        print("error getting embedding: ", e)
        raise
    
from chonkie import RecursiveChunker, RecursiveRules, RecursiveLevel

CHAR_CHUNK_SIZE = 1500
rules = RecursiveRules(
    levels=[
        RecursiveLevel(delimiters=["\n\n", "\n", "\r\n"]),
        RecursiveLevel(delimiters=[".?!;:"]),
        RecursiveLevel(),  # fallback
    ]
)
chunker = RecursiveChunker(
    tokenizer="character",
    chunk_size=CHAR_CHUNK_SIZE,
    rules=rules,
    min_characters_per_chunk=24
)

def chunk_text(text: str):
    """
    Chunk text and return a list of dicts:
    {
        "text": chunk_text,
        "start": start_index,
        "end": end_index
    }
    """
    chunks = chunker(text)
    start_idx = 0
    chunk_info = []

    for chunk in chunks:
        end_idx = start_idx + len(chunk.text)
        chunk_info.append({
            "text": chunk.text,
            "start": start_idx,
            "end": end_idx
        })
        start_idx = end_idx 

    return chunk_info

def reconstruct_text(chunks: list[str]) -> str:
    return "".join(chunks)

