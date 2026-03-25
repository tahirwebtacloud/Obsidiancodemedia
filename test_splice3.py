orig = "Google Stitch killed the blank canvas.\n\nThe infinite canvas runs on Gemini 2.5 Pro.\nYou feed it text or images.\n\nWe tested this."
selected_text = "The infinite canvas runs on Gemini 2.5 Pro.\nYou feed it text or images."

# In Javascript, sel.toString() might not include the newline.
# Let's say frontend sends: "The infinite canvas runs on Gemini 2.5 Pro. You feed it text or images."
# which has length ~73.

norm_sel = ' '.join(selected_text.split())
norm_chars = []
norm_to_orig = []
i = 0
in_ws = False
while i < len(orig):
    if orig[i] in ' \t':
        if not in_ws and norm_chars:
            norm_chars.append(' ')
            norm_to_orig.append(i)
        in_ws = True
    elif orig[i] in '\n\r':
        # IN SERVER.PY THIS IS:
        norm_chars.append(orig[i])
        norm_to_orig.append(i)
        in_ws = False
    else:
        norm_chars.append(orig[i])
        norm_to_orig.append(i)
        in_ws = False
    i += 1
norm_full = ''.join(norm_chars)
norm_idx = norm_full.find(norm_sel)
print("norm_idx:", norm_idx)
