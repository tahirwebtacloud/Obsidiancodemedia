import pandas as pd
import os
import re

# Base path for data files - resolves relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


def _load_csv(filepath, skip_header_scan=False, header_keyword="First Name"):
    """Load a CSV file with optional header row detection.

    Some LinkedIn exports (Connections.csv) have note lines before the actual header.
    This function scans for the real header row when skip_header_scan is False.
    """
    if not os.path.exists(filepath):
        return pd.DataFrame()

    try:
        if not skip_header_scan:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f):
                    if i > 10:
                        break
                    if header_keyword in line:
                        return pd.read_csv(filepath, skiprows=i, encoding='utf-8', on_bad_lines='skip')
        return pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
    except Exception as e:
        print(f"  Warning: Could not load {os.path.basename(filepath)}: {e}")
        return pd.DataFrame()


def _clean_columns(df):
    """Strip whitespace from column names."""
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
    return df


def load_connections():
    """Load Connections.csv (~1,803 rows).
    Columns: First Name, Last Name, URL, Email Address, Company, Position, Connected On
    """
    df = _load_csv(os.path.join(RAW_DIR, "Connections.csv"), skip_header_scan=False)
    df = _clean_columns(df)
    if not df.empty and 'Connected On' in df.columns:
        df['Connected On'] = pd.to_datetime(df['Connected On'], format='mixed', dayfirst=True, errors='coerce')
    return df


def load_messages():
    """Load messages.csv (~4,469 rows).
    Columns: CONVERSATION ID, CONVERSATION TITLE, FROM, SENDER PROFILE URL, TO,
             RECIPIENT PROFILE URLS, DATE, SUBJECT, CONTENT, FOLDER, ATTACHMENTS
    """
    df = _load_csv(os.path.join(RAW_DIR, "messages.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    if not df.empty and 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE'], format='mixed', utc=True, errors='coerce')
    return df


def load_endorsements_received():
    """Load Endorsement_Received_Info.csv (~760 rows).
    Columns: Endorsement Date, Skill Name, Endorser First Name, Endorser Last Name,
             Endorser Public Url, Endorsement Status
    """
    df = _load_csv(os.path.join(RAW_DIR, "Endorsement_Received_Info.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    return df


def load_endorsements_given():
    """Load Endorsement_Given_Info.csv.
    Columns: Endorsement Date, Skill Name, Endorsee First Name, Endorsee Last Name,
             Endorsee Public Url, Endorsement Status
    """
    df = _load_csv(os.path.join(RAW_DIR, "Endorsement_Given_Info.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    return df


def load_recommendations_received():
    """Load Recommendations_Received.csv.
    Columns: First Name, Last Name, Status, ...
    """
    df = _load_csv(os.path.join(RAW_DIR, "Recommendations_Received.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    return df


def load_recommendations_given():
    """Load Recommendations_Given.csv.
    Columns: First Name, Last Name, Status, ...
    """
    df = _load_csv(os.path.join(RAW_DIR, "Recommendations_Given.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    return df


def load_invitations():
    """Load Invitations.csv (~130 rows).
    Columns: From, To, Sent At, Message, Direction, inviterProfileUrl, inviteeProfileUrl
    """
    df = _load_csv(os.path.join(RAW_DIR, "Invitations.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    if not df.empty and 'Sent At' in df.columns:
        df['Sent At'] = pd.to_datetime(df['Sent At'], format='mixed', errors='coerce')
    return df


def load_reactions():
    """Load Reactions.csv (~1,448 rows). These are YOUR reactions to others' posts.
    Columns: Date, Type, Link
    """
    df = _load_csv(os.path.join(RAW_DIR, "Reactions.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    if not df.empty and 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], format='mixed', utc=True, errors='coerce')
    return df


def load_comments():
    """Load Comments.csv (~216 rows). These are YOUR comments on others' posts.
    Columns: Date, Link, Message
    """
    df = _load_csv(os.path.join(RAW_DIR, "Comments.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    if not df.empty and 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], format='mixed', utc=True, errors='coerce')
    return df


def load_company_follows():
    """Load Company Follows.csv.
    Columns: Organization, Followed On
    """
    df = _load_csv(os.path.join(RAW_DIR, "Company Follows.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    return df


def load_member_follows():
    """Load Member_Follows.csv.
    Columns: Date, Status, FullName
    """
    df = _load_csv(os.path.join(RAW_DIR, "Member_Follows.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    return df


def load_search_queries():
    """Load SearchQueries.csv.
    Columns: Time, Search Query
    """
    df = _load_csv(os.path.join(RAW_DIR, "SearchQueries.csv"), skip_header_scan=True)
    df = _clean_columns(df)
    return df


def load_surveillance_report():
    """Parse SURVEILLANCE_REPORT.md for reactor profile URLs.
    Returns a set of LinkedIn profile URLs that reacted to your posts.
    """
    report_path = os.path.join(REPORTS_DIR, "SURVEILLANCE_REPORT.md")
    urls = set()
    if not os.path.exists(report_path):
        return urls

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Extract LinkedIn profile URLs
        url_pattern = r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-]+'
        urls = set(re.findall(url_pattern, content))
    except Exception as e:
        print(f"  Warning: Could not parse surveillance report: {e}")

    return urls


def load_all():
    """Load all data sources. Returns a dict of DataFrames/sets.
    This is the main entry point for the orchestrator.
    """
    print("Loading data sources...")

    data = {}

    loaders = [
        ("connections", load_connections),
        ("messages", load_messages),
        ("endorsements_received", load_endorsements_received),
        ("endorsements_given", load_endorsements_given),
        ("recommendations_received", load_recommendations_received),
        ("recommendations_given", load_recommendations_given),
        ("invitations", load_invitations),
        ("reactions", load_reactions),
        ("comments", load_comments),
        ("company_follows", load_company_follows),
        ("member_follows", load_member_follows),
        ("search_queries", load_search_queries),
    ]

    for name, loader_fn in loaders:
        df = loader_fn()
        data[name] = df
        row_count = len(df) if not isinstance(df, set) else len(df)
        print(f"  {name}: {row_count} rows")

    # Surveillance report is a set, not a DataFrame
    data["surveillance_urls"] = load_surveillance_report()
    print(f"  surveillance_urls: {len(data['surveillance_urls'])} URLs")

    return data
