"""
RAG Manager Module
Handles vector storage and similarity search for Voice Engine using Supabase pgvector.
"""

import os
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class VoiceChunk:
    """A chunk of voice data for vector storage."""
    content: str
    source_type: str  # 'profile', 'position', 'share', 'custom'
    metadata: Dict
    embedding: Optional[List[float]] = None
    similarity_score: Optional[float] = None


class RAGManager:
    """Manage Retrieval-Augmented Generation with Supabase pgvector."""
    
    def __init__(self):
        """Initialize RAG manager with Supabase connection."""
        self.supabase = None
        self.embedding_dim = int(os.getenv("VOICE_EMBEDDING_DIM", "3072"))
        self.embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
        self._init_client()

    def _normalize_embedding(self, embedding: List[float]) -> List[float]:
        """Normalize embedding length to match configured vector dimension."""
        if not embedding:
            return [0.0] * self.embedding_dim

        vector = [float(v) for v in embedding]
        if len(vector) > self.embedding_dim:
            return vector[:self.embedding_dim]
        if len(vector) < self.embedding_dim:
            return vector + ([0.0] * (self.embedding_dim - len(vector)))
        return vector
    
    def _init_client(self):
        """Initialize Supabase client."""
        try:
            from supabase import create_client
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if url and key:
                self.supabase = create_client(url, key)
        except Exception as e:
            print(f"[RAGManager] Supabase init error: {e}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using Gemini.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        try:
            from google import genai
            from google.genai import types
            
            api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_GEMINI_API_KEY not set")
            
            client = genai.Client(api_key=api_key)
            
            # Use Gemini's embedding model
            result = client.models.embed_content(
                model=self.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY")
            )
            
            values = result.embeddings[0].values if result.embeddings else []
            return self._normalize_embedding(values)
            
        except Exception as e:
            print(f"[RAGManager] Embedding error: {e}")
            # Return simple fallback embedding (sparse)
            return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """Simple fallback embedding using basic text features."""
        # Create a simple vector based on text characteristics
        # This is NOT a semantic embedding, just a placeholder
        words = text.lower().split()
        vector = [0.0] * self.embedding_dim
        
        # Hash words to positions
        for word in words[:50]:  # Limit to first 50 words
            for char in word[:5]:  # First 5 chars
                idx = ord(char) % self.embedding_dim
                vector[idx] += 1.0
        
        # Normalize
        import math
        magnitude = math.sqrt(sum(x**2 for x in vector))
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return self._normalize_embedding(vector)
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks for vector storage.
        
        Args:
            text: Text to chunk
            chunk_size: Maximum chunk size in characters
            overlap: Overlap between chunks in characters
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text] if text.strip() else []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending
                for i in range(min(end, len(text) - 1), start + chunk_size // 2, -1):
                    if text[i] in '.!?' and i + 1 < len(text) and text[i + 1].isspace():
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    def store_voice_chunks(self, user_id: str, chunks: List[VoiceChunk]) -> bool:
        """
        Store voice chunks with embeddings in Supabase.
        
        Args:
            user_id: User ID
            chunks: List of VoiceChunk objects
            
        Returns:
            True if successful
        """
        if not self.supabase:
            print("[RAGManager] Supabase not available, storing locally")
            return self._store_local(user_id, chunks)
        
        try:
            rows = []
            for chunk in chunks:
                # Generate embedding
                embedding = chunk.embedding or self._get_embedding(chunk.content)
                embedding = self._normalize_embedding(embedding)
                
                row = {
                    "user_id": user_id,
                    "content": chunk.content,
                    "source_type": chunk.source_type,
                    "metadata": chunk.metadata,
                    "embedding": embedding
                }
                rows.append(row)
            
            # Insert in batches
            batch_size = 50
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                self.supabase.table("voice_chunks").upsert(batch).execute()
            
            print(f"[RAGManager] Stored {len(chunks)} chunks for user {user_id}")
            return True
            
        except Exception as e:
            print(f"[RAGManager] Store error: {e}")
            return self._store_local(user_id, chunks)
    
    def _store_local(self, user_id: str, chunks: List[VoiceChunk]) -> bool:
        """Fallback local storage."""
        import json
        import os
        
        try:
            data = {
                "user_id": user_id,
                "chunks": [
                    {
                        "content": c.content,
                        "source_type": c.source_type,
                        "metadata": c.metadata
                    }
                    for c in chunks
                ]
            }
            
            filename = f".tmp/voice_chunks_{user_id}.json"
            os.makedirs(".tmp", exist_ok=True)
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"[RAGManager] Local store error: {e}")
            return False
    
    def search_similar(self, user_id: str, query: str, top_k: int = 5, threshold: float = 0.6) -> List[VoiceChunk]:
        """
        Search for similar voice chunks using vector similarity.
        
        Args:
            user_id: User ID
            query: Search query
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of VoiceChunk objects with similarity scores
        """
        if not self.supabase:
            print("[RAGManager] Supabase not available, using local search")
            return self._search_local(user_id, query, top_k)
        
        try:
            # Generate query embedding
            query_embedding = self._normalize_embedding(self._get_embedding(query))
            
            # Use Supabase RPC for vector search
            result = self.supabase.rpc(
                "match_voice_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": top_k,
                    "user_id_filter": user_id
                }
            ).execute()
            
            chunks = []
            for row in result.data:
                chunk = VoiceChunk(
                    content=row["content"],
                    source_type=row["source_type"],
                    metadata=row.get("metadata", {}),
                    similarity_score=row.get("similarity", 0)
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            print(f"[RAGManager] Search error: {e}")
            return self._search_local(user_id, query, top_k)
    
    def _search_local(self, user_id: str, query: str, top_k: int) -> List[VoiceChunk]:
        """Fallback local search using simple keyword matching."""
        import json
        import os
        
        filename = f".tmp/voice_chunks_{user_id}.json"
        if not os.path.exists(filename):
            return []
        
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            query_words = set(query.lower().split())
            scored_chunks = []
            
            for chunk_data in data.get("chunks", []):
                content = chunk_data["content"].lower()
                score = sum(1 for word in query_words if word in content)
                
                if score > 0:
                    scored_chunks.append((score, chunk_data))
            
            # Sort by score and take top_k
            scored_chunks.sort(key=lambda x: x[0], reverse=True)
            
            results = []
            for score, chunk_data in scored_chunks[:top_k]:
                # Normalize score to 0-1 range
                normalized_score = min(score / len(query_words), 1.0) if query_words else 0
                
                chunk = VoiceChunk(
                    content=chunk_data["content"],
                    source_type=chunk_data["source_type"],
                    metadata=chunk_data.get("metadata", {}),
                    similarity_score=normalized_score
                )
                results.append(chunk)
            
            return results
            
        except Exception as e:
            print(f"[RAGManager] Local search error: {e}")
            return []
    
    def process_linkedin_data(
        self,
        user_id: str,
        linkedin_data: Dict,
        knowledge_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """
        Process LinkedIn data and store as voice chunks.
        
        Args:
            user_id: User ID
            linkedin_data: Parsed LinkedIn data
            
        Returns:
            Number of chunks stored
        """
        chunks = []
        
        # Process profile
        profile = linkedin_data.get("profile")
        if profile:
            profile_text = f"""
            {getattr(profile, 'full_name', '')} - {getattr(profile, 'headline', '')}
            Industry: {getattr(profile, 'industry', '')}
            Location: {getattr(profile, 'location', '')}
            Summary: {getattr(profile, 'summary', '')}
            """
            
            for chunk in self.chunk_text(profile_text, chunk_size=300):
                chunks.append(VoiceChunk(
                    content=chunk,
                    source_type="profile",
                    metadata={"section": "profile_summary"}
                ))
        
        # Process positions
        positions = linkedin_data.get("positions", [])
        for pos in positions:
            pos_text = f"""
            Role: {getattr(pos, 'title', '')} at {getattr(pos, 'company', '')}
            Duration: {getattr(pos, 'start_date', '')} to {getattr(pos, 'end_date', 'Present')}
            Description: {getattr(pos, 'description', '')}
            """
            
            for chunk in self.chunk_text(pos_text, chunk_size=400):
                chunks.append(VoiceChunk(
                    content=chunk,
                    source_type="position",
                    metadata={
                        "company": getattr(pos, 'company', ''),
                        "title": getattr(pos, 'title', ''),
                        "is_current": getattr(pos, 'is_current', False)
                    }
                ))
        
        # Process shares (posts)
        shares = linkedin_data.get("shares", [])
        for share in shares:
            content = getattr(share, 'content', '')
            if content and len(content) > 100:
                chunks.append(VoiceChunk(
                    content=content[:1000],  # Keep posts as single chunks (max 1000 chars)
                    source_type="share",
                    metadata={
                        "date": getattr(share, 'date', ''),
                        "engagement": getattr(share, 'engagement_count', 0)
                    }
                ))
        
        # Process structured knowledge chunks
        for knowledge in knowledge_chunks or []:
            if not isinstance(knowledge, dict):
                continue
            content = str(knowledge.get("content", "") or "").strip()
            if not content:
                continue
            title = str(knowledge.get("title", "") or "").strip()
            category = str(knowledge.get("category", "") or "structured").strip()
            source = str(knowledge.get("source", "") or "structured").strip()
            source_type = category if category else "structured"

            combined = f"{title}\n{content}".strip() if title else content
            for chunk in self.chunk_text(combined, chunk_size=420, overlap=60):
                chunks.append(VoiceChunk(
                    content=chunk,
                    source_type=source_type,
                    metadata={
                        "section": category,
                        "title": title,
                        "source": source,
                        "structured": True
                    }
                ))

        # Store chunks
        if chunks:
            success = self.store_voice_chunks(user_id, chunks)
            if success:
                print(f"[RAGManager] Processed {len(chunks)} chunks for user {user_id}")
                return len(chunks)
        
        return 0
    
    def get_personal_context(self, user_id: str, topic: str) -> str:
        """
        Get relevant personal context for a topic.
        
        Args:
            user_id: User ID
            topic: Topic to find context for
            
        Returns:
            String with relevant personal anecdotes/experiences
        """
        chunks = self.search_similar(user_id, topic, top_k=3, threshold=0.5)
        
        if not chunks:
            return ""
        
        context_parts = []
        for chunk in chunks:
            if chunk.similarity_score and chunk.similarity_score >= 0.5:
                context_parts.append(chunk.content)
        
        return "\n\n".join(context_parts) if context_parts else ""


def embed_user_knowledge(user_id: str, profile: Optional[Dict] = None, brand: Optional[Dict] = None) -> int:
    """
    Embed structured user profile and brand data into the vector DB.
    Each category is stored as a separate chunk with a descriptive source_type
    so retrieval can filter by category.

    Args:
        user_id: Authenticated user ID
        profile: Dict from get_user_profile() (persona, skills, experiences, etc.)
        brand: Dict from get_user_brand() (brand_name, products_services, etc.)

    Returns:
        Number of chunks stored
    """
    if not user_id or user_id == "default":
        return 0

    rag = RAGManager()
    chunks: List[VoiceChunk] = []

    # ── Profile chunks ──────────────────────────────────────────
    if profile and isinstance(profile, dict):
        # Summary / bio
        persona = profile.get("persona") or {}
        bio = persona.get("professional_bio") or profile.get("professional_bio") or ""
        if bio:
            chunks.append(VoiceChunk(
                content=f"Professional summary: {bio}",
                source_type="profile_summary",
                metadata={"section": "summary", "source": "user_profile"}
            ))

        # Skills
        skills = persona.get("core_skills") or profile.get("core_skills") or []
        if skills:
            skills_text = ", ".join(skills) if isinstance(skills, list) else str(skills)
            chunks.append(VoiceChunk(
                content=f"Core skills: {skills_text}",
                source_type="profile_skills",
                metadata={"section": "skills", "source": "user_profile"}
            ))

        # Expertise areas
        expertise = persona.get("expertise_areas") or profile.get("expertise_areas") or []
        if expertise:
            exp_text = ", ".join(expertise) if isinstance(expertise, list) else str(expertise)
            chunks.append(VoiceChunk(
                content=f"Expertise areas: {exp_text}",
                source_type="profile_expertise",
                metadata={"section": "expertise", "source": "user_profile"}
            ))

        # Writing style rules
        style_rules = persona.get("writing_style_rules") or profile.get("writing_style_rules") or []
        if style_rules:
            rules_text = ". ".join(style_rules) if isinstance(style_rules, list) else str(style_rules)
            chunks.append(VoiceChunk(
                content=f"Writing style rules: {rules_text}",
                source_type="profile_writing_style",
                metadata={"section": "writing_style", "source": "user_profile"}
            ))

        # Target ICP
        icp = persona.get("target_icp") or profile.get("target_icp") or ""
        if icp:
            chunks.append(VoiceChunk(
                content=f"Target audience (ICP): {icp}",
                source_type="profile_icp",
                metadata={"section": "icp", "source": "user_profile"}
            ))

        # Tone of voice (from profile level)
        tone = persona.get("tone_of_voice") or profile.get("tone_of_voice") or ""
        if tone:
            chunks.append(VoiceChunk(
                content=f"Tone of voice: {tone}",
                source_type="profile_tone",
                metadata={"section": "tone", "source": "user_profile"}
            ))

    # ── Brand chunks ────────────────────────────────────────────
    if brand and isinstance(brand, dict):
        # Brand overview (name + tagline + description)
        brand_parts = []
        if brand.get("brand_name"):
            brand_parts.append(f"Brand: {brand['brand_name']}")
        if brand.get("tagline"):
            brand_parts.append(f"Tagline: {brand['tagline']}")
        if brand.get("description"):
            brand_parts.append(f"Description: {brand['description']}")
        if brand_parts:
            chunks.append(VoiceChunk(
                content=". ".join(brand_parts),
                source_type="brand_overview",
                metadata={"section": "brand_overview", "source": "brand_assets"}
            ))

        # Visual identity
        visual_parts = []
        if brand.get("primary_color"):
            visual_parts.append(f"Primary color: {brand['primary_color']}")
        if brand.get("secondary_color"):
            visual_parts.append(f"Secondary color: {brand['secondary_color']}")
        if brand.get("accent_color"):
            visual_parts.append(f"Accent color: {brand['accent_color']}")
        if brand.get("font_family"):
            visual_parts.append(f"Font: {brand['font_family']}")
        if brand.get("visual_style"):
            visual_parts.append(f"Visual style: {brand['visual_style']}")
        if visual_parts:
            chunks.append(VoiceChunk(
                content=". ".join(visual_parts),
                source_type="brand_visual",
                metadata={"section": "visual_identity", "source": "brand_assets"}
            ))

        # Tone of voice (brand level)
        brand_tone = brand.get("tone_of_voice") or ""
        if brand_tone:
            chunks.append(VoiceChunk(
                content=f"Brand tone of voice: {brand_tone}",
                source_type="brand_tone",
                metadata={"section": "tone", "source": "brand_assets"}
            ))

        # Products and services (one chunk per product for granular retrieval)
        products = brand.get("products_services") or []
        if isinstance(products, list):
            for prod in products:
                if isinstance(prod, dict):
                    name = prod.get("name") or prod.get("title") or ""
                    desc = prod.get("description") or ""
                    if name:
                        prod_text = f"Product/Service: {name}"
                        if desc:
                            prod_text += f". {desc}"
                        chunks.append(VoiceChunk(
                            content=prod_text,
                            source_type="brand_product",
                            metadata={"section": "products_services", "source": "brand_assets", "product_name": name}
                        ))
                elif isinstance(prod, str) and prod.strip():
                    chunks.append(VoiceChunk(
                        content=f"Product/Service: {prod}",
                        source_type="brand_product",
                        metadata={"section": "products_services", "source": "brand_assets"}
                    ))

    if not chunks:
        return 0

    # Wipe old profile/brand knowledge chunks before inserting fresh ones
    _source_types_to_wipe = [
        "profile_summary", "profile_skills", "profile_expertise",
        "profile_writing_style", "profile_icp", "profile_tone",
        "brand_overview", "brand_visual", "brand_tone", "brand_product",
    ]
    try:
        if rag.supabase:
            for st in _source_types_to_wipe:
                rag.supabase.table("voice_chunks").delete().eq("user_id", user_id).eq("source_type", st).execute()
    except Exception as e:
        print(f"[embed_user_knowledge] Wipe warning: {e}")

    success = rag.store_voice_chunks(user_id, chunks)
    stored = len(chunks) if success else 0
    print(f"[embed_user_knowledge] Stored {stored} structured chunks for user {user_id}")
    return stored


def search_voice_context(user_id: str, topic: str, api_key: Optional[str] = None) -> Tuple[str, float]:
    """
    Convenience function to search voice context for a topic.
    
    Args:
        user_id: User ID
        topic: Topic to search
        api_key: Optional API key
        
    Returns:
        Tuple of (context_string, max_similarity_score)
    """
    try:
        rag = RAGManager()
        chunks = rag.search_similar(user_id, topic, top_k=3, threshold=0.6)
        
        if not chunks:
            return ("", 0.0)
        
        context = "\n\n".join([c.content for c in chunks])
        max_score = max([c.similarity_score or 0 for c in chunks])
        
        return (context, max_score)
        
    except Exception as e:
        print(f"[search_voice_context] Error: {e}")
        return ("", 0.0)


if __name__ == "__main__":
    print("[RAGManager] Module loaded successfully")
