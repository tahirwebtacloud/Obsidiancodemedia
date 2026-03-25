orig = "Google Stitch killed the blank canvas."
selected_text = "The infinite"

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
        norm_chars.append(' ')  # Wait, in the server code it appends orig[i] directly!
        norm_to_orig.append(i)
        in_ws = False
    else:
        norm_chars.append(orig[i])
        norm_to_orig.append(i)
        in_ws = False
    i += 1
norm_full = ''.join(norm_chars)
print(norm_full.find(norm_sel))
