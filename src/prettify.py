def generate_heading(string):
    print(string)
    print("-"*len(string))

def keys_values(pairs):
    for pair in pairs:
        print(f"{pair}: {pairs[pair]}")
