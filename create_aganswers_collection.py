#!/usr/bin/env python3
"""
Script to create the 'aganswers' collection in Qdrant.
This resolves the 404 error when trying to upload documents.
"""

import os
from qdrant_client import QdrantClient, models

def create_aganswers_collection():
    """Create the aganswers collection in Qdrant with proper configuration."""
    
    # Connect to Qdrant instance (Docker container)
    qdrant_client = QdrantClient(
        url="http://localhost:6333",
        # No API key needed for local Docker instance
    )
    
    collection_name = "aganswers"
    
    try:
        # Check if collection already exists
        collection_info = qdrant_client.get_collection(collection_name=collection_name)
        print(f"✅ Collection '{collection_name}' already exists.")
        print(f"Vector size: {collection_info.config.params.vectors.size}")
        print(f"Distance metric: {collection_info.config.params.vectors.distance}")
        return
    except Exception as e:
        print(f"Collection '{collection_name}' does not exist. Creating it now...")
    
    try:
        # Create the collection with OpenAI embedding dimensions (1536)
        # Based on the codebase, they use OpenAI text-embedding-ada-002 which has 1536 dimensions
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=1536,  # OpenAI text-embedding-ada-002 dimension
                distance=models.Distance.COSINE,
                on_disk=True  # Store vectors on disk for better memory usage
            ),
            # Optimize for better performance with large datasets
            hnsw_config=models.HnswConfigDiff(on_disk=True),
            # Enable payload indexing for better filtering performance
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=1000  # Start indexing after 1000 points
            )
        )
        
        print(f"✅ Successfully created collection '{collection_name}'!")
        print("Configuration:")
        print(f"  - Vector size: 1536 (OpenAI text-embedding-ada-002)")
        print(f"  - Distance metric: COSINE")
        print(f"  - Storage: On-disk for better memory usage")
        print(f"  - HNSW index: On-disk")
        
        # Verify the collection was created
        collection_info = qdrant_client.get_collection(collection_name=collection_name)
        print(f"✅ Collection verified. Current point count: {collection_info.points_count}")
        
    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        raise

if __name__ == "__main__":
    print("Creating 'aganswers' collection in Qdrant...")
    print("Make sure your Qdrant instance is running on localhost:6333")
    print()
    
    create_aganswers_collection()
    
    print()
    print("🎉 Done! You can now ingest documents without the 404 error.")
    print("The collection is ready to receive embeddings from your application.") 