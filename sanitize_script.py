import re
import os

filepath = r"c:\Users\Hp\Desktop\Docs\Backup Files\LinkedIn Post Generator v1.1 main\frontend\script.js"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add sanitize helper at the top
helper_code = """// DOMPurify Sanitization Helper
window.sanitizeStr = (str) => {
    if (typeof str !== 'string') return str;
    return typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(str, { ALLOWED_TAGS: [] }) : str.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
};

"""
if "window.sanitizeStr" not in content:
    content = helper_code + content

# 2. Patch createResearchCard (around line 1230-1240)
content = content.replace(
    "const fullText = item.text || \"\";\n        const textPreview = fullText.length > 150 ? fullText.substring(0, 150).trim() + '…' : fullText;",
    "const fullText = item.text || \"\";\n        const textPreview = window.sanitizeStr(fullText.length > 150 ? fullText.substring(0, 150).trim() + '…' : fullText);"
)
content = content.replace(
    "const authorName = item.author_name || 'Unknown';",
    "const authorName = window.sanitizeStr(item.author_name || 'Unknown');"
)
content = content.replace(
    "<div class=\"yt-title\">${item.title || item.url || 'Post'}</div>",
    "<div class=\"yt-title\">${window.sanitizeStr(item.title || item.url || 'Post')}</div>"
)

# 3. Patch renderResearchInConsole (inside competitor block, parsing item text - around line 1113)
content = content.replace(
    "const textPreview = fullText.length > 130 ? fullText.substring(0, 130).trim() + '…' : fullText;",
    "const textPreview = window.sanitizeStr(fullText.length > 130 ? fullText.substring(0, 130).trim() + '…' : fullText);"
)
content = content.replace(
    "${item.author_name || 'Anonymous'}",
    "${window.sanitizeStr(item.author_name || 'Anonymous')}"
)
content = content.replace(
    "${item.title || 'LinkedIn Post'}",
    "${window.sanitizeStr(item.title || 'LinkedIn Post')}"
)

# 4. Patch openFullPostModal (carousel / header metadata)
content = content.replace(
    "${item.document_title}",
    "${window.sanitizeStr(item.document_title)}"
)
content = content.replace(
    "${item.document_title || 'Carousel Document'}",
    "${window.sanitizeStr(item.document_title || 'Carousel Document')}"
)
content = content.replace(
    "modalPostTitle.textContent = item.title || \"Full LinkedIn Post\";",
    "modalPostTitle.textContent = window.sanitizeStr(item.title || \"Full LinkedIn Post\");"
)
content = content.replace(
    "${item.author_name || 'Unknown'}",
    "${window.sanitizeStr(item.author_name || 'Unknown')}"
)

# 5. Patch createYoutubeCard
content = content.replace(
    "${item.title}",
    "${window.sanitizeStr(item.title)}"
)
content = content.replace(
    "${item.channelName || 'Unknown'}",
    "${window.sanitizeStr(item.channelName || 'Unknown')}"
)
content = content.replace(
    "${item.description || 'No description.'}",
    "${window.sanitizeStr(item.description || 'No description.')}"
)
content = content.replace(
    "${item.transcript || 'No transcript.'}",
    "${window.sanitizeStr(item.transcript || 'No transcript.')}"
)

# 6. Patch loadHistory
content = content.replace(
    "<td title=\"${entry.topic}\" style=\"padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.9rem; font-weight: 500; color: var(--text-primary); max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;\">${entry.topic}</td>",
    "<td title=\"${window.sanitizeStr(entry.topic)}\" style=\"padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.9rem; font-weight: 500; color: var(--text-primary); max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;\">${window.sanitizeStr(entry.topic)}</td>"
)

# 7. Patch _buildSurvCard
content = content.replace(
    "const typeIcon = { poll: 'bar-chart-2', carousel: 'layers', image: 'image', video: 'video', text: 'file-text' }[postType] || 'file-text';",
    "const typeIcon = { poll: 'bar-chart-2', carousel: 'layers', image: 'image', video: 'video', text: 'file-text' }[postType] || 'file-text';\n                            const safeTitle = window.sanitizeStr(item.title || 'LinkedIn Post');"
)
content = content.replace(
    "<h3 class=\"yt-title\" style=\"text-wrap: balance; font-size: 1.05rem; line-height: 1.4; margin:0;\">${item.title || 'LinkedIn Post'}</h3>",
    "<h3 class=\"yt-title\" style=\"text-wrap: balance; font-size: 1.05rem; line-height: 1.4; margin:0;\">${safeTitle}</h3>"
)

# 8. Patch lead rendering (crm row)
content = content.replace(
    "${lead.profile_url ? `<a href=\"${lead.profile_url}\" target=\"_blank\" class=\"crm-lead-name\">${lead.name}</a>` : `<span class=\"crm-lead-name\">${lead.name}</span>`}",
    "${lead.profile_url ? `<a href=\"${lead.profile_url}\" target=\"_blank\" class=\"crm-lead-name\">${window.sanitizeStr(lead.name)}</a>` : `<span class=\"crm-lead-name\">${window.sanitizeStr(lead.name)}</span>`}"
)
content = content.replace(
    "title=\"${lead.headline || ''}\">${lead.headline || 'LinkedIn Member'}",
    "title=\"${window.sanitizeStr(lead.headline || '')}\">${window.sanitizeStr(lead.headline || 'LinkedIn Member')}"
)
content = content.replace(
    "title=\"${lead.text.replace(/\"/g, '&quot;')}\">${lead.text}",
    "title=\"${window.sanitizeStr(lead.text).replace(/\"/g, '&quot;')}\">${window.sanitizeStr(lead.text)}"
)

# 9. Carousel render
content = content.replace(
    "innerHTML = `<strong>Title:</strong> ${slide.title}`",
    "innerHTML = `<strong>Title:</strong> ${window.sanitizeStr(slide.title)}`"
)
content = content.replace(
    "innerHTML = `<strong>Subtitle:</strong> ${slide.subtitle}`",
    "innerHTML = `<strong>Subtitle:</strong> ${window.sanitizeStr(slide.subtitle)}`"
)
content = content.replace(
    "innerHTML = `<strong>Body:</strong> ${slide.body}`",
    "innerHTML = `<strong>Body:</strong> ${window.sanitizeStr(slide.body)}`"
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Sanitization script executed successfully.")
