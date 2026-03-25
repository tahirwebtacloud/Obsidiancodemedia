import os
import json
import argparse

def draft_dm(target_name, context):
    """
    Drafts a personalized LinkedIn DM.
    """
    print(f"Drafting DM for {target_name} with context: {context}")
    
    # Mock drafting logic using the 'street-smart' voice
    message = (
        f"Hey {target_name.split()[0]}, saw your post about {context} 🤔\n\n"
        "Actually loved the point you made about efficiency.\n"
        "I'm digging into similar workflows myself right now.\n\n"
        "No pitch, just wanted to say that was a solid take. Keep it up! 😂"
    )
    
    result = {
        "to": target_name,
        "message": message,
        "status": "DRAFTED"
    }
    
    output_path = ".tmp/dm_drafts.json"
    os.makedirs(".tmp", exist_ok=True)
    
    try:
        from execution.file_locker import FileLock
    except ImportError:
        try:
            from file_locker import FileLock
        except ImportError:
            FileLock = None

    def _do_append():
        drafts = []
        if os.path.exists(output_path):
            with open(output_path, "r") as f:
                drafts = json.load(f)
        
        drafts.append(result)
        
        with open(output_path, "w") as f:
            json.dump(drafts, f, indent=4)

    if FileLock:
        try:
            with FileLock(output_path):
                _do_append()
        except Exception as e:
            print(f"[DM] Lock error: {e}")
            _do_append()
    else:
        _do_append()
    
    print(f"DM draft saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Draft personalized LinkedIn DMs.")
    parser.add_argument("--name", required=True, help="Target profile name.")
    parser.add_argument("--context", required=True, help="Context for the message.")
    
    args = parser.parse_args()
    draft_dm(args.name, args.context)
