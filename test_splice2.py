orig = "Google Stitch killed the blank canvas.\n\nThe infinite canvas runs on Gemini 2.5 Pro.\nYou feed it text or images.\n\nWe tested this."
selected_text = "The infinite canvas runs on Gemini 2.5 Pro.\nYou feed it text or images."

# Simulate frontend sending a selected text with different whitespace
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
        norm_chars.append(orig[i])  # Wait, appending \n to norm_chars breaks the `norm_sel` finding!
        norm_to_orig.append(i)
        in_ws = False
    else:
        norm_chars.append(orig[i])
        norm_to_orig.append(i)
        in_ws = False
    i += 1
norm_full = ''.join(norm_chars)
print("norm_full:")
print(repr(norm_full))
print("norm_sel:")
print(repr(norm_sel))
norm_idx = norm_full.find(norm_sel)
print("norm_idx:", norm_idx)
