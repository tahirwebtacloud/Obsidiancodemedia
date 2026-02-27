import json
import re
import sys
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from lingua import Language, LanguageDetectorBuilder

class YouTubeScraper:
    def __init__(self):
        # Initialize language detector with all languages for best accuracy
        # This might take a moment to load
        self.detector = LanguageDetectorBuilder.from_all_languages().build()

    def search_videos(self, query, limit=3):
        """
        Search for videos using yt-dlp.
        Handles both search queries and channel/playlist URLs.
        """
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'playlistend': limit,
            'ignoreerrors': True,
        }

        # If it's not a URL, treat it as a search query
        if not re.match(r'^https?://', query):
            query = f"ytsearch{limit}:{query}"

        print(f"Searching for: {query}...", file=sys.stderr)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query, download=False)

        if 'entries' in result:
            return result['entries'][:limit]
        return [result] if result else []

    def get_full_metadata(self, video_url):
        """
        Fetch detailed metadata for a single video.
        """
        ydl_opts = {
            'quiet': True,
            'ignoreerrors': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(video_url, download=False)

    def get_transcript(self, video_id):
        """
        Retrieve transcript using youtube-transcript-api.
        Tries manual captions first, then auto-generated.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to get manually created transcript first
            try:
                transcript = transcript_list.find_manually_created_transcript()
            except:
                # Fallback to generated
                try:
                    transcript = transcript_list.find_generated_transcript()
                except:
                    return None
            
            return transcript.fetch()
        except Exception as e:
            # print(f"Could not fetch transcript: {e}", file=sys.stderr)
            return None

    def extract_links(self, text):
        """
        Extract URLs from text.
        """
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
        return re.findall(url_pattern, text)

    def analyze_language(self, text):
        """
        Perform advanced language detection on the text.
        """
        if not text or len(text.strip()) < 10:
             return {
                "detected_language": None,
                "confidence_score": 0,
                "is_mixed_language": False,
                "primary_language": None,
                "secondary_languages": []
            }

        # Detect multiple languages with confidence
        confidence_values = self.detector.compute_language_confidence_values(text)
        
        # Filter out very low confidence results to reduce noise
        relevant_languages = [
            (cv.language, cv.value) for cv in confidence_values if cv.value > 0.1
        ]
        
        if not relevant_languages:
             return {
                "detected_language": None,
                "confidence_score": 0,
                "is_mixed_language": False,
                "primary_language": None,
                "secondary_languages": []
            }

        primary_lang_obj, primary_score = relevant_languages[0]
        
        # ISO-639-1 code (2 letters)
        primary_code = primary_lang_obj.iso_code_639_1.name.lower()

        secondary_langs = []
        is_mixed = False
        
        # Check for mixed content (if 2nd language has significant confidence)
        if len(relevant_languages) > 1:
            second_lang_obj, second_score = relevant_languages[1]
            if second_score > 0.2: # Threshold for mixed content
                is_mixed = True
            
            for lang_obj, score in relevant_languages[1:]:
                secondary_langs.append({
                    "language": lang_obj.iso_code_639_1.name.lower(),
                    "confidence": round(score * 100, 2)
                })

        return {
            "detected_language": primary_code,
            "confidence_score": round(primary_score * 100, 2),
            "is_mixed_language": is_mixed,
            "primary_language": primary_code,
            "secondary_languages": secondary_langs
        }

    def process(self, query):
        videos = self.search_videos(query)
        results = []

        for video in videos:
            if not video: continue
            
            video_id = video.get('id')
            title = video.get('title')
            webpage_url = video.get('webpage_url') or video.get('url') # 'url' is sometimes used in extracting flat
            
            if not webpage_url and video_id:
                webpage_url = f"https://www.youtube.com/watch?v={video_id}"

            # Get enriched metadata
            print(f"Processing: {title}...", file=sys.stderr)
            full_meta = self.get_full_metadata(webpage_url)
            
            if not full_meta:
                full_meta = video # Fallback

            description = full_meta.get('description', '')
            
            # Transcript
            transcript_data = self.get_transcript(video_id)
            full_transcript_text = ""
            if transcript_data:
                full_transcript_text = " ".join([t['text'] for t in transcript_data])
            
            # Language Analysis
            lang_analysis = self.analyze_language(full_transcript_text)

            # Resources
            resources = self.extract_links(description)

            video_data = {
                "title": title,
                "thumbnail": full_meta.get('thumbnail'),
                "description": description,
                "full_transcription": full_transcript_text,
                "detected_language": lang_analysis['detected_language'],
                "language_confidence": lang_analysis['confidence_score'],
                "is_mixed_language": lang_analysis['is_mixed_language'],
                "secondary_languages": lang_analysis['secondary_languages'],
                "resources_mentioned": resources,
                "stats": {
                    "views": full_meta.get('view_count'),
                    "likes": full_meta.get('like_count'),
                    "comment_count": full_meta.get('comment_count'),
                    "upload_date": full_meta.get('upload_date'),
                    "duration_seconds": full_meta.get('duration')
                },
                "url": webpage_url
            }
            results.append(video_data)
        
        return results

def main():
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <query_or_url>")
        sys.exit(1)
    
    query = sys.argv[1]
    scraper = YouTubeScraper()
    data = scraper.process(query)
    
    # Output JSON to stdout
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
